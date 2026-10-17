#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch220: 榨干 token 自动续跑 + x86_64 proot 移植 + workspace native 引用核对（warn-only）

① 榨干 token（#5，确认的半成品）：
   batch162 自己写着「ChatService 续跑逻辑在下一批处理」，那个下一批从未出现 —— 开关
   能出现能拨动，但没有任何逻辑消费它。本批补上：在 ChatService.sendMessage 的正常完成点
   (handleMessageComplete 返回 + _generationDoneFlow.emit 之后) 加同 job 内的续跑循环：
   每轮 存一条「继续」用户消息 → 再跑 handleMessageComplete → 复查会话级开关。
   停止条件：关开关（每轮现读）/ 用户点停止（job 取消）/ 达上限 100 轮 / 抛异常（外层 catch）。
   刻意不递归调 sendMessage —— 它会 cancel 当前 job（自己），必须同 job 循环。
   锚点用结构定位：if (answer && !routedHandled) { → 其后 8 行内找 emit 行，插在其后。

② x86_64 proot（#9a）：与 batch219 同法下载到 workspace/src/main/jniLibs/x86_64/，
   尺寸校验 + 回报实际 git blob sha（供日后固化；arm64 才是 APK 实际打包的 ABI）。

③ native 引用核对（#9b）：扫描 fork 剩余 workspace 文件是否出现 loadLibrary/
   System.load/externalNativeBuild（判断上游 cpp/PTY 是否真的不需要），结果走 ::warning。

五查: import 零新增(碎片全 FQN+已用符号); 同文件冲突(锚点在 sendMessage 尾部,
batch70/95 只在顶部, 不重叠); 作用域(appScope.launch 内); 括号配平(脚本断言);
签名不改。
Python 三查: r 原始串内无三连单引号/无反斜杠; 无 f-string/join/walrus; helper 先定义。
warn-only；每阶段独立 try/except；幂等 marker；末尾一行汇总。
'''
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch220'
SQ_MARK = 'rhSqueezeWire'

CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'

X64 = (
    ('libproot_exec.so', 246408),
    ('libproot_loader.so', 18352),
)
X64_DIR = 'workspace/src/main/jniLibs/x86_64'
X64_SRC_RAW = 'https://raw.githubusercontent.com/AAAelina/rikkahub-agent/master/workspace/src/main/jniLibs/x86_64/'
X64_SRC_API = 'https://api.github.com/repos/AAAelina/rikkahub-agent/contents/workspace/src/main/jniLibs/x86_64/'

NATIVE_SCAN = (
    ('bg', 'workspace/src/main/java/me/rerere/workspace/WorkspaceBackgroundProcesses.kt'),
    ('fs', 'workspace/src/main/java/me/rerere/workspace/WorkspaceFileSystem.kt'),
    ('ws', 'workspace/src/main/java/me/rerere/workspace/Workspace.kt'),
    ('sr', 'workspace/src/main/java/me/rerere/workspace/WorkspaceShellRunner.kt'),
)

SQUEEZE_BLOCK = r'''
                // [batch220] 榨干 token 自动续跑（会话级，与酒馆同一 Store）：
                // 正常完成后每轮存一条「继续」用户消息并再跑一次生成，直到关开关/停止/达上限。
                // 刻意不调 sendMessage：它会 cancel 当前 job（自己），必须在同一 job 内循环。
                val rhSqueezeMaxRounds = 100
                var rhSqueezeRounds = 0
                while (answer && !routedHandled && rhSqueezeRounds < rhSqueezeMaxRounds &&
                    me.rerere.rikkahub.data.datastore.TavernModeStore.isSqueezeTokenEnabled(
                        context, conversationId.toString()
                    )
                ) {
                    rhSqueezeRounds++
                    val rhSqueezeConv = session.state.value
                    saveConversation(
                        conversationId,
                        rhSqueezeConv.copy(
                            messageNodes = rhSqueezeConv.messageNodes + UIMessage(
                                role = MessageRole.USER,
                                parts = listOf(UIMessagePart.Text("继续")),
                            ).toMessageNode(),
                        ),
                    )
                    handleMessageComplete(conversationId)
                }
                if (rhSqueezeRounds > 0) {
                    _generationDoneFlow.emit(conversationId)
                }'''

applied = []
skipped = []
extra = []


def joinlist(items):
    t = ''
    for i, s in enumerate(items):
        if i > 0:
            t += ','
        t += s
    return t


def ok(tag):
    if tag not in applied:
        applied.append(tag)


def skip(tag, why):
    skipped.append(tag + '<' + str(why)[:80] + '>')


def safe(name, fn):
    try:
        fn()
    except Exception as exc:
        skip(name, 'crash:' + str(exc)[:60])


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def concat(lines):
    t = ''
    for i, ln in enumerate(lines):
        if i > 0:
            t += NL
        t += ln
    return t


def git_blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\x00' + data).hexdigest()


def read(path):
    p = ROOT / path
    if not p.exists():
        return None
    try:
        return p.read_text(encoding='utf-8')
    except Exception:
        return None


def read_bytes(path):
    p = ROOT / path
    if not p.exists():
        return None
    try:
        return p.read_bytes()
    except Exception:
        return None


def write(path, text):
    p = ROOT / path
    if not p.parent.exists():
        p.parent.mkdir(parents=True)
    p.write_text(text, encoding='utf-8')


def fetch(url, raw_accept=False):
    req = urllib.request.Request(url, headers={'User-Agent': 'rikkahub-batch220/1.0'})
    if raw_accept:
        req.add_header('Accept', 'application/vnd.github.raw')
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


# ============================================================
# ① ChatService: 榨干 token 自动续跑
# ============================================================
def phase_squeeze():
    src = read(CS)
    if src is None:
        skip('squeeze', 'missing')
        return
    if SQ_MARK in src:
        ok('squeeze-exists')
        return
    lines = src.split(NL)
    bal0 = balance(src)

    emit_line = '_generationDoneFlow.emit(conversationId)'
    insert_at = -1
    for i, ln in enumerate(lines):
        if ln.strip() == 'if (answer && !routedHandled) {':
            for j in range(i + 1, min(i + 9, len(lines))):
                if lines[j].strip() == emit_line:
                    insert_at = j
                    break
            break
    if insert_at < 0:
        hits = [i for i, ln in enumerate(lines) if ln.strip() == emit_line]
        if len(hits) == 1:
            insert_at = hits[0]
        else:
            skip('squeeze', 'anchor-hits=' + str(len(hits)))
            return

    block = SQUEEZE_BLOCK.split(NL)
    lines[insert_at + 1:insert_at + 1] = block
    out = concat(lines)
    if balance(out) != bal0:
        skip('squeeze', 'balance')
        return
    for need in ('rhSqueezeMaxRounds', 'isSqueezeTokenEnabled', SQ_MARK):
        if need not in out:
            skip('squeeze', 'selfcheck:' + need)
            return
    write(CS, out)
    ok('squeeze')


# ============================================================
# ② x86_64 proot（尺寸校验 + 回报 sha）
# ============================================================
def phase_x64():
    dest = ROOT / X64_DIR
    dest.mkdir(parents=True, exist_ok=True)
    for name, size in X64:
        target = dest / name
        if target.exists():
            data = read_bytes(X64_DIR + '/' + name)
            if data is not None and len(data) == size:
                ok('x64-exists:' + name)
                extra.append(name + ':' + git_blob_sha(data)[:12])
                continue
        data = None
        err = ''
        for src_url, ra in ((X64_SRC_RAW + name, False), (X64_SRC_API + name + '?ref=master', True)):
            try:
                data = fetch(src_url, ra)
                break
            except Exception as exc:
                err = str(exc)[:60]
        if data is None:
            skip('x64:' + name, 'download:' + err)
            continue
        if len(data) != size:
            skip('x64:' + name, 'size=' + str(len(data)))
            continue
        (dest / name).write_bytes(data)
        ok('x64:' + name)
        extra.append(name + '=' + git_blob_sha(data))


# ============================================================
# ③ 剩余 workspace 文件 native 引用扫描
# ============================================================
def phase_scan():
    parts = []
    for label, path in NATIVE_SCAN:
        src = read(path)
        if src is None:
            parts.append(label + '=miss')
            continue
        n = src.count('loadLibrary') + src.count('System.load') + src.count('externalNativeBuild')
        parts.append(label + '=' + str(n))
    extra.append('nativeScan[' + ' '.join(parts) + ']')


def main():
    safe('squeeze', phase_squeeze)
    safe('x64', phase_x64)
    safe('scan', phase_scan)
    print('::warning::' + BATCH + ' applied=[' + joinlist(applied) + '] skipped=[' + joinlist(skipped) + '] ' + ' '.join(extra)[:900])


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::warning::' + BATCH + ' crashed: ' + str(exc)[:400])
    sys.exit(0)
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch215: run402 装机反馈修复（warn-only）—— Rootfs 安装崩溃 + 合并无加载提示 + 榨干 token 诊断

反馈 → 根因 → 修法:
  A. Rootfs 安装报 "Rootfs entry path is blank":
     RootfsInstaller.extractTar 里, 每个 tar 条目的 name 先过 blank 检查再 safeResolve。
     但 Alpine minirootfs 的第一个条目是 "./"(包根目录自身), 规范化后变成空串,
     落在 safeResolve 内部的 normalizeTarPath 里 require(blank) 崩溃。
     修法: 把 blank 检查换成"规范化后为空白"检查(根目录条目直接跳过), 并加 isBlankRootEntry 辅助。
  B1. 合并加载过程无提示(看起来像失败):
     batch158 只给 AwaitingDecision 挂了差异确认弹窗, Preparing(下载+扫描)/Applying(写入)
     两个状态什么都没渲染。修法: BackupPage 给这两个状态补一个 AlertDialog 进度提示。
  C. 榨干 token 开关不见(诊断, 不改):
     batch162/164/167 的 CI annotation 全部无 warning(自称成功), 但用户看不到开关。
     本阶段只 dump 四个文件的真实形态(各 marker 计数 + ReasoningPicker 开关区)到 annotation,
     供下一批精准修, 不改任何行为。

warn-only: 任何锚点失败只 ::warning + 跳过, 不阻塞构建; 每阶段独立 try/except; 末尾正常退出。

五查:
 1. import: A 零新增(纯 java/io 自带); B1 需 AlertDialog/Text(用 ensure-import 模式, 缺才加,
    锚 batch158 的 import 行); C 只读不写
 2. 同文件冲突: RootfsInstaller.kt 无在链脚本碰过(workspace 模块独立); BackupPage.kt 只被
    batch158 碰过(锚点就是它注入的 mergeState 行, 零重叠); C 涉及文件只读
 3. 作用域: A 的 helper 在类内、isBlankRootEntry 在 extractTar 内调用同类私有方法;
    B1 的 dialog 插在原 AwaitingDecision 块之后(同为 composable 作用域)
 4. 括号配对: 每个编辑文件写入前断言 balance 不变
 5. 函数签名: 不改任何既有签名(纯新增 helper / 纯新增 UI 块)
Python 三查: 引号变量构造(含反斜杠的 helper 用 r 原始串)/NL 手写 concat/helper 先定义后用。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch215'
MARK_A = 'isBlankRootEntry'
MARK_B = 'rhMergeLoadingTip'

RI = 'workspace/src/main/java/me/rerere/workspace/RootfsInstaller.kt'
BP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/backup/BackupPage.kt'

applied = []
skipped = []


def ok(tag):
    if tag not in applied:
        applied.append(tag)


def skip(tag, why):
    skipped.append(tag + '<' + str(why)[:80] + '>')


def safe(name, fn, default=None):
    try:
        return fn()
    except Exception as exc:
        skip(name, 'crash:' + str(exc)[:60])
        return default


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def concat(lines):
    t = ''
    for i, ln in enumerate(lines):
        if i > 0:
            t += NL
        t += ln
    return t


def joinlist(items):
    t = ''
    for i, s in enumerate(items):
        if i > 0:
            t += ','
        t += s
    return t


def read(path):
    p = ROOT / path
    if not p.exists():
        return None
    try:
        return p.read_text(encoding='utf-8')
    except Exception:
        return None


def write(path, text):
    p = ROOT / path
    if not p.parent.exists():
        p.parent.mkdir(parents=True)
    p.write_text(text, encoding='utf-8')


def ensure_import(lines, want, anchor):
    '''缺才加 import(行级 strip 全等判断), 插在 anchor import 行后。返回 True=已有或已加。'''
    for ln in lines:
        if ln.strip() == want:
            return True
    hi = -1
    for i, ln in enumerate(lines):
        if ln.strip() == anchor:
            hi = i
            break
    if hi < 0:
        return False
    lines.insert(hi + 1, want)
    return True


# ============================================================
# 阶段 A: RootfsInstaller.kt —— 根目录条目跳过而非崩溃
# ============================================================
ROOTFS_HELPER = r'''    /** [batch215] 根目录条目("./")规范化后为空白——这类 tar 条目是包根自身, 应跳过而非崩溃。 */
    private fun isBlankRootEntry(name: String): Boolean {
        var n = name.replace('\\', '/').trim().trimStart('/')
        while (n.startsWith("./")) n = n.removePrefix("./")
        return n.isBlank()
    }

'''


def phase_rootfs():
    src = read(RI)
    if src is None:
        skip('rootfs', 'missing')
        return
    if MARK_A in src:
        ok('rootfs-exists')
        return
    lines = src.split(NL)
    bal0 = balance(src)

    # A1: blank 检查换成"规范化后为空白"检查
    cond = 'if (header.name.isBlank()) {'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == cond]
    if len(hits) != 1:
        skip('rootfs.cond', 'anchor=' + str(len(hits)))
        return
    ci = hits[0]
    d = ind(lines[ci])
    lines[ci] = d + 'if (header.name.isBlank() || isBlankRootEntry(header.name)) { // ' + MARK_A + ' (batch215)'

    # A2: helper 插在 normalizeTarPath 定义前
    fn = 'private fun normalizeTarPath(path: String): String {'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == fn]
    if len(hits) != 1:
        skip('rootfs.helper', 'anchor=' + str(len(hits)))
        return
    hi = hits[0]
    lines[hi:hi] = ROOTFS_HELPER.rstrip(chr(10)).split(NL)

    out = concat(lines)
    if balance(out) != bal0:
        skip('rootfs', 'balance')
        return
    if 'isBlankRootEntry' not in out or 'if (header.name.isBlank() || isBlankRootEntry(header.name))' not in out:
        skip('rootfs', 'selfcheck')
        return
    write(RI, out)
    ok('rootfs')


# ============================================================
# 阶段 B1: BackupPage.kt —— Preparing/Applying 进度提示
# ============================================================
def phase_merge_loading():
    src = read(BP)
    if src is None:
        skip('merge-loading', 'missing')
        return
    if MARK_B in src:
        ok('merge-loading-exists')
        return
    lines = src.split(NL)
    bal0 = balance(src)

    # import 补齐(缺才加, 锚 batch158 注入的 import 行)
    imp_anchor = 'import me.rerere.rikkahub.ui.pages.backup.components.BackupDialog'
    ok_imp = True
    for want in (
        'import androidx.compose.material3.AlertDialog',
        'import androidx.compose.material3.Text',
    ):
        if not ensure_import(lines, want, imp_anchor):
            ok_imp = False
    if not ok_imp:
        skip('merge-loading', 'import-anchor')
        return

    # 插在 AwaitingDecision 块之后(batch158 注入文本, 深度扫描找闭合)
    anchor = '(mergeState as? BackupVM.MergeUiState.AwaitingDecision)?.let { state ->'
    hits = [i for i, ln in enumerate(lines) if anchor in ln]
    if len(hits) != 1:
        skip('merge-loading', 'anchor=' + str(len(hits)))
        return
    ai = hits[0]
    depth = 0
    end = -1
    for j in range(ai, len(lines)):
        depth += lines[j].count('{') - lines[j].count('}')
        if depth == 0 and j > ai:
            end = j
            break
    if end < 0:
        skip('merge-loading', 'no-close')
        return
    d = ind(lines[ai])
    block = [
        '',
        d + '// ' + MARK_B + ' (batch215): 合并扫描/应用中的进度提示(此前两状态无 UI, 看起来像卡死)',
        d + 'if (mergeState is BackupVM.MergeUiState.Preparing || mergeState is BackupVM.MergeUiState.Applying) {',
        d + '    AlertDialog(',
        d + '        onDismissRequest = { },',
        d + '        title = { Text(if (mergeState is BackupVM.MergeUiState.Applying) "正在应用合并…" else "正在扫描备份差异…") },',
        d + '        text = { Text("请稍候，正在处理备份文件，备份较大时需要几秒钟") },',
        d + '        confirmButton = { },',
        d + '    )',
        d + '}',
    ]
    lines[end + 1:end + 1] = block

    out = concat(lines)
    if balance(out) != bal0:
        skip('merge-loading', 'balance')
        return
    if MARK_B not in out or 'MergeUiState.Preparing' not in out:
        skip('merge-loading', 'selfcheck')
        return
    write(BP, out)
    ok('merge-loading')


# ============================================================
# 阶段 C: 榨干 token 诊断(只读, 不改)
# ============================================================
def phase_diag():
    parts = []
    targets = (
        ('ReasoningPicker', 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ReasoningPicker.kt'),
        ('ChatInput', 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ChatInput.kt'),
        ('ChatVM', 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatVM.kt'),
        ('ChatInputState', 'app/src/main/java/me/rerere/rikkahub/ui/hooks/ChatInputState.kt'),
    )
    for name, path in targets:
        txt = read(path)
        if txt is None:
            parts.append(name + '=missing')
            continue
        sq = txt.count('rhSqueezeToken')
        wire = txt.count('rhSqueezeWire')
        cb = txt.count('onUpdateSqueezeToken')
        parts.append(name + '[sq=' + str(sq) + ',wire=' + str(wire) + ',cb=' + str(cb) + ']')
    # ReasoningPicker 开关区 dump
    rp = read('app/src/main/java/me/rerere/rikkahub/ui/components/ai/ReasoningPicker.kt')
    if rp is not None:
        rlines = rp.split(NL)
        dump = []
        for i, ln in enumerate(rlines):
            if 'onUpdateSqueezeToken' in ln or 'squeezeTokenEnabled' in ln or 'rhSqueezeToken' in ln:
                dump.append('L' + str(i + 1) + ':' + ln.strip()[:60])
        if dump:
            parts.append('RPlines=' + ' ;; '.join(dump[:6]))
    print('::warning::' + BATCH + '-diag ' + ' '.join(parts)[:1300])


def main():
    safe('rootfs', phase_rootfs)
    safe('merge-loading', phase_merge_loading)
    safe('diag', phase_diag)
    print('::warning::' + BATCH + ' applied=[' + joinlist(applied) + '] skipped=[' + joinlist(skipped) + ']')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::warning::' + BATCH + ' crashed: ' + str(exc)[:400])
    sys.exit(0)
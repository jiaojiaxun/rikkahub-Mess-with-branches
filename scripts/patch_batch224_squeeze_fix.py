#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch224: 榨干 token 自动续跑（修 batch220 未落地）—— 锚点改稳 + 单行 ::error 报告

batch221 全量验证: squeeze220=MISS —— batch220 的锚点(if 行+8 行窗口找 emit)没中, 被
warn-only 静默跳过。疑因: _generationDoneFlow.emit(conversationId) 在 CI 形态出现 >1 次
(sendMessage + retry/regenerate 等路径), batch220 的回退(count==1)失败; 或 if 行形态不同。

本批锚点改为「emit 行 且 其前 4 行内含 handleMessageComplete(conversationId)」——
这是 sendMessage 独有的结构(emit 紧跟在生成调用之后), 与 retry/regenerate 的 emit 区分。
恰好 1 个匹配才插入, 否则只报告 ::error(单行, 不占 warning 配额)。

幂等 marker: rhSqueezeWire(与 batch220 同标记, batch221 的验证会转绿)。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch224'
SQ_MARK = 'rhSqueezeWire'
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
EMIT = '_generationDoneFlow.emit(conversationId)'
GEN = 'handleMessageComplete(conversationId)'

SQUEEZE_BLOCK = r'''
                // [batch224] rhSqueezeWire: 榨干 token 自动续跑（会话级，与酒馆同一 Store）
                // 正常完成后每轮存一条「继续」用户消息并再跑生成，直到关开关/停止/达上限。
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


def joinlist(items):
    t = ''
    for i, s in enumerate(items):
        if i > 0:
            t += ','
        t += s
    return t


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def concat(lines):
    t = ''
    for i, ln in enumerate(lines):
        if i > 0:
            t += NL
        t += ln
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


def main():
    src = read(CS)
    if src is None:
        skipped.append('missing')
        print('::error::' + BATCH + ' SKIP missing')
        return
    if SQ_MARK in src:
        applied.append('exists')
        print('::error::' + BATCH + ' OK already')
        return
    lines = src.split(NL)
    bal0 = balance(src)

    emits = [i for i, ln in enumerate(lines) if ln.strip() == EMIT]
    cands = []
    for ei in emits:
        window = concat(lines[max(0, ei - 4):ei])
        if GEN in window:
            cands.append(ei)
    if len(cands) != 1:
        skipped.append('anchor emits=' + str(len(emits)) + ' cands=' + str(len(cands)))
        print('::error::' + BATCH + ' SKIP emits=' + str(len(emits)) + ' cands=' + str(len(cands)))
        return
    insert_at = cands[0]

    block = SQUEEZE_BLOCK.split(NL)
    lines[insert_at + 1:insert_at + 1] = block
    out = concat(lines)
    if balance(out) != bal0:
        skipped.append('balance')
        print('::error::' + BATCH + ' SKIP balance')
        return
    for need in ('rhSqueezeMaxRounds', 'isSqueezeTokenEnabled', SQ_MARK):
        if need not in out:
            skipped.append('selfcheck:' + need)
            print('::error::' + BATCH + ' SKIP selfcheck ' + need)
            return
    write(CS, out)
    applied.append('squeeze')
    print('::error::' + BATCH + ' OK applied squeeze, emits=' + str(len(emits)) + ' cands=' + str(len(cands)))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::error::' + BATCH + ' crashed: ' + str(exc)[:300])
    sys.exit(0)
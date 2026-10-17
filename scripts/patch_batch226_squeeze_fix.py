#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch226: 榨干 token 自动续跑（修 batch220/224 连续未落地）—— 锚点改用 sendMessage 独有的 routedHandled

三连挂根因：
  batch220 锚 `if (answer && !routedHandled) {` MISS（strip 精确匹配没对上 CI 形态）；
  batch224 锚「emit 行前 4 行内含 handleMessageComplete」SKIP（emits=3 cands=2，
  sendMessage 和 retry/regenerate 都有这个结构，歧义）。

本批锚点改为 `val routedHandled = if (answer)`（fast-path 路由变量，只在 sendMessage 声明），
  从该行起向后扫第一个 `_generationDoneFlow.emit(conversationId)`（≤20 行），插在其后。
  宽松匹配（startswith），不挑剔缩进。
  若仍不中，::error 打印全部 emit/routedHandled 行号+上下文，供下批精准修。

幂等 marker: rhSqueezeWire(与 batch220/224 同标记, batch221 验证转绿)。warn-only。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch226'
SQ_MARK = 'rhSqueezeWire'
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
EMIT = '_generationDoneFlow.emit(conversationId)'

SQUEEZE_BLOCK = r'''
                // [batch226] rhSqueezeWire: 榨干 token 自动续跑（会话级，与酒馆同一 Store）
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

    emits = [i + 1 for i, ln in enumerate(lines) if ln.strip() == EMIT]
    routed = [i + 1 for i, ln in enumerate(lines)
              if ln.strip().startswith('val routedHandled') or ('routedHandled' in ln and 'if (answer' in ln)]
    diag = 'emits@' + ','.join(str(e) for e in emits) + ' routed@' + ','.join(str(r) for r in routed)

    insert_at = -1
    anchor_line = -1
    for i, ln in enumerate(lines):
        if ln.strip().startswith('val routedHandled'):
            anchor_line = i
            break
    if anchor_line >= 0:
        for j in range(anchor_line, min(anchor_line + 20, len(lines))):
            if lines[j].strip() == EMIT:
                insert_at = j
                break
    if insert_at < 0:
        skipped.append('anchor ' + diag)
        print('::error::' + BATCH + ' SKIP ' + diag)
        return

    block = SQUEEZE_BLOCK.split(NL)
    lines[insert_at + 1:insert_at + 1] = block
    out = concat(lines)
    if balance(out) != bal0:
        skipped.append('balance ' + diag)
        print('::error::' + BATCH + ' SKIP balance ' + diag)
        return
    for need in ('rhSqueezeMaxRounds', 'isSqueezeTokenEnabled', SQ_MARK):
        if need not in out:
            skipped.append('selfcheck:' + need)
            print('::error::' + BATCH + ' SKIP selfcheck ' + need + ' ' + diag)
            return
    write(CS, out)
    applied.append('squeeze')
    print('::error::' + BATCH + ' OK applied squeeze @L' + str(insert_at + 1) + ' | ' + diag)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::error::' + BATCH + ' crashed: ' + str(exc)[:300])
    sys.exit(0)
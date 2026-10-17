#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch223: 榨干续跑落点诊断 —— dump ChatService.sendMessage 的尾部区域（只读，走 ::error）

背景: batch221 全量验证显示 squeeze220=MISS（batch220 的续跑编辑没落地，锚点没对上被
      warn-only 跳过）。batch220 的锚点是 if (answer && !routedHandled) { → 其后 8 行找
      emit。要看 CI 真形态才知道它为什么没中。

本批只 dump 不修改：
  1. 找 fun sendMessage( 行号, 从其函数体头起 dump ~90 行进 ::error(分行打印)
  2. 统计 _generationDoneFlow.emit(conversationId) 与 if (answer && !routedHandled) 出现次数
     (判断锚点歧义 vs 不存在)
  3. 列出全部 emit 行号 + 每行前 3 行上下文(判断哪个 emit 属于 sendMessage)

通道 ::error(warning 已满额)。exit 0。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch223'
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
EMIT = '_generationDoneFlow.emit(conversationId)'
IFLINE = 'if (answer && !routedHandled) {'


def main():
    p = ROOT / CS
    if not p.exists():
        print('::error::' + BATCH + ' missing ChatService.kt')
        return
    lines = p.read_text(encoding='utf-8').split(NL)
    total = len(lines)

    emit_hits = [i for i, ln in enumerate(lines) if ln.strip() == EMIT]
    if_hits = [i for i, ln in enumerate(lines) if ln.strip() == IFLINE]
    send_hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('fun sendMessage(')]

    # 摘要行
    summary = (BATCH + ' emitCount=' + str(len(emit_hits))
               + ' ifCount=' + str(len(if_hits))
               + ' sendCount=' + str(len(send_hits))
               + ' emitLines=' + ','.join(str(i + 1) for i in emit_hits)
               + ' ifLines=' + ','.join(str(i + 1) for i in if_hits)
               + ' sendLines=' + ','.join(str(i + 1) for i in send_hits))
    print('::error::' + summary)

    # 每个 emit 行的前 3 行上下文
    for ei in emit_hits:
        ctx = []
        for j in range(max(0, ei - 3), ei + 1):
            ctx.append('L' + str(j + 1) + ':' + lines[j].strip()[:70])
        print('::error::' + BATCH + '-emitCtx L' + str(ei + 1) + ' <- ' + ' ;; '.join(ctx))

    # sendMessage 区域 dump（找第一个 fun sendMessage, dump 其后 90 行）
    if send_hits:
        s = send_hits[0]
        for j in range(s, min(s + 90, total)):
            print('::error::' + BATCH + '-dump L' + str(j + 1) + ': ' + lines[j].rstrip()[:120])


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::error::' + BATCH + ' crashed: ' + str(exc)[:300])
    sys.exit(0)
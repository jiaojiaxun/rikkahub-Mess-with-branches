#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
batch86b v3 — 【纯诊断】dump CI 形态真值,不做任何修改

为什么不再直接修:
  #237 证据显示我的「配平找参数列表闭合」在真实 CI 形态上失效 ——
  ChatMessage.kt:186 报 "onChangeAvatar on receiver of type 'Modifier'",
  说明插入行落进了 Modifier 链中间(即 close 指向了 modifier = Modifier.weight(1f)
  这类行,而不是参数列表的 `)`)。
  我的自检只验「行存在 + 全文配平相等」,抓不到「插错位置但语法配平」→ 必须拿真值。

本脚本:定位 5 个关键锚点,逐个 dump 现场行(带行号 + repr 显示真实空白),
        最后 ::error 退出,让 dump 出现在 CI annotation 里。
        【绝不修改任何文件】—— 因此这一轮 3 秒结束,零风险。

目标锚点:
  A. ChatMessage.kt   `fun ChatMessage(`        -> 参数区 40 行
  B. ChatMessage.kt   `ChatMessageUserAvatar(`  -> 调用区 12 行
  C. ChatList.kt      `fun ChatList(`           -> 参数区 40 行
  D. ChatList.kt      `private fun ChatListNormal(` -> 参数区 40 行
  E. ChatList.kt      `ChatListNormal(` 调用     -> 调用区 12 行
  F. ChatList.kt      `ChatMessage(` 调用        -> 调用区 12 行
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'


def dump_anchor(path, anchor, before, after, label):
    p = ROOT / path
    if not p.exists():
        print('  [' + label + '] FILE MISSING: ' + path)
        return
    lines = p.read_text(encoding='utf-8').split(NL)
    hits = [i for i, ln in enumerate(lines) if ln.strip() == anchor]
    print('  [' + label + '] anchor=' + repr(anchor) + ' hits=' + str(len(hits)) + ' total_lines=' + str(len(lines)))
    for h in hits:
        lo = max(0, h - before)
        hi = min(len(lines), h + after)
        for i in range(lo, hi):
            mark = '>>' if i == h else '  '
            print('    ' + mark + ' L' + str(i + 1) + ': ' + repr(lines[i]))


def main():
    print('==== batch86b v3 DIAGNOSTIC DUMP (no file is modified) ====')
    dump_anchor(CM, 'fun ChatMessage(', 3, 45, 'A ChatMessage sig')
    dump_anchor(CM, 'ChatMessageUserAvatar(', 3, 14, 'B ChatMessageUserAvatar call')
    dump_anchor(CL, 'fun ChatList(', 3, 45, 'C ChatList sig')
    dump_anchor(CL, 'private fun ChatListNormal(', 3, 45, 'D ChatListNormal sig')
    dump_anchor(CL, 'ChatListNormal(', 3, 14, 'E ChatListNormal call')
    dump_anchor(CL, 'ChatMessage(', 3, 14, 'F ChatMessage call')
    print('==== END DUMP ====')
    print('::error file=scripts/patch_batch86b.py::batch86b v3 diagnostic complete — see dump above')


main()

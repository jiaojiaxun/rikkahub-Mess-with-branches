#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch171: 修复"一松手就往上滑"(warn-only)

现象: 聊天列表滚动后松手,列表自动往上滑(最后一条消息跳到视口顶部)。

根因: ChatListNormal 自动跟随用 state.requestScrollToItem(latestGroupIndex)——
requestScrollToItem(index) 的语义是"把第 index 项滚到视口顶部"(scrollOffset 默认0),
不是"滚到列表末尾"。当 isAtBottom() 仍为 true 时触发,最后一项瞬间跳到视口顶部,
观感就是"一松手就往上滑"。

修法: requestScrollToItem 传 scrollOffset = 可用视口高度——
把最后一项的顶部安排在视口底部之外, LazyList 内部 clamp 到列表末尾,
实现"底部对齐"(长回复/短回复都正确)。

warn-only: 任何锚点失败只 ::warning + 跳过,不阻塞构建(多人协作)。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhScrollBottom171'
F = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'


def warn(msg):
    print('::warning file=' + F + '::batch171 ' + str(msg)[:1200])


def skip(msg):
    warn(msg + ' — skipped (warn-only)')
    sys.stdout.flush()
    sys.exit(0)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


try:
    t = (ROOT / F).read_text(encoding='utf-8')
except Exception as e:
    skip('read failed: ' + str(e))

if MARK in t:
    print('batch171: already applied')
    sys.exit(0)

bal0 = balance(t)
lines = t.split(NL)

# 锚点: state.requestScrollToItem(latestGroupIndex)
hits = [i for i, ln in enumerate(lines) if ln.strip() == 'state.requestScrollToItem(latestGroupIndex)']
if len(hits) != 1:
    skip('requestScrollToItem anchor count=' + str(len(hits)))
hi = hits[0]
d = ind(lines[hi])

new_block = [
    d + '// ' + MARK + ': 滚到列表末尾(不是把最后一项滚到视口顶部)。',
    d + '// requestScrollToItem(index) 默认把该项顶部对齐视口顶部——造成"一松手就往上滑"。',
    d + '// 传 scrollOffset = 可用视口高度: 把该项顶部安排在视口底部之外, LazyList clamp 到末尾。',
    d + 'val rhViewportPx = state.layoutInfo.viewportEndOffset - state.layoutInfo.viewportStartOffset',
    d + 'val rhBottomInsetPx = with(density) { innerPadding.calculateBottomPadding().toPx() }.roundToInt()',
    d + 'val rhScrollOffset = (rhViewportPx - rhBottomInsetPx).coerceAtLeast(1)',
    d + 'state.requestScrollToItem(latestGroupIndex, scrollOffset = rhScrollOffset)',
]
lines[hi:hi + 1] = new_block

out = NL.join(lines)
for need in [MARK, 'scrollOffset = rhScrollOffset', 'rhViewportPx']:
    if need not in out:
        skip('selfcheck missing: ' + need)
if 'state.requestScrollToItem(latestGroupIndex)' + NL in out:
    # 原始无 offset 调用应已消失(被替换)
    pass
if balance(out) != bal0:
    skip('balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

(ROOT / F).write_text(out, encoding='utf-8')
print('::notice::batch171 OK - auto-follow now scrolls to list bottom (was: last item to top)')

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch171 v2: 修复"一松手就往上滑"(warn-only) —— 修正 scrollOffset 方向

v1 死因(自查发现): requestScrollToItem(index, scrollOffset) 的语义是
"item 顶部最终位于 视口起点 + scrollOffset"。
  scrollOffset > 0  => item 下移 => 滚动位置向前(看更早内容)
  scrollOffset < 0  => item 上移 => 滚动位置向后(看更晚内容)
v1 传了正数 => 反而把列表往前推,比原 bug 更糟。

v2 修法: 目标"最后一项底部对齐可用视口底部" =>
  targetOffset = availableHeight - lastItemHeight
  - 项矮 => 正数 => LazyList clamp 到列表末尾(底部对齐)
  - 项高 => 负数 => 向后滚,显示该项底部
拿不到项高时兜底 -rhAvailablePx * 4(向后推 4 屏, clamp 到末尾)。

两种情况兼容:
  A) v1 已应用 => 找到 v1 的 rhScrollOffset 行并替换为 v2 逻辑
  B) v1 未应用 => 用原始锚点直接应用 v2

warn-only: 任何锚点失败只 ::warning + 跳过,不阻塞构建(多人协作)。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhScrollBottom171'
V2MARK = 'rhScrollBottom171v2'
F = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'


def warn(msg):
    print('::warning file=' + F + '::batch171v2 ' + str(msg)[:1200])


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

if V2MARK in t:
    print('batch171v2: already applied')
    sys.exit(0)

bal0 = balance(t)
lines = t.split(NL)

if MARK in t:
    # ---- 情况 A: v1 已应用 -> 就地修正 ----
    old_hits = [i for i, ln in enumerate(lines) if 'val rhScrollOffset = (rhViewportPx - rhBottomInsetPx).coerceAtLeast(1)' in ln]
    if len(old_hits) != 1:
        skip('v1 rhScrollOffset anchor count=' + str(len(old_hits)))
    oi = old_hits[0]
    d = ind(lines[oi])

    new_calc = [
        d + 'val rhAvailablePx = (rhViewportPx - rhBottomInsetPx).coerceAtLeast(1) // ' + V2MARK,
        d + 'val rhLastItemHeight = visibleItemsInfo.firstOrNull { it.index == latestGroupIndex }?.size',
        d + 'val rhTargetOffset = if (rhLastItemHeight != null) {',
        d + '    rhAvailablePx - rhLastItemHeight',
        d + '} else {',
        d + '    -rhAvailablePx * 4',
        d + '}',
    ]
    lines[oi:oi + 1] = new_calc

    # 改调用点的参数名
    call_hits = [i for i, ln in enumerate(lines) if 'scrollOffset = rhScrollOffset' in ln]
    if len(call_hits) != 1:
        skip('v1 call site anchor count=' + str(len(call_hits)))
    lines[call_hits[0]] = lines[call_hits[0]].replace('scrollOffset = rhScrollOffset', 'scrollOffset = rhTargetOffset')
    applied_mode = 'A-fix-v1'
else:
    # ---- 情况 B: v1 未应用 -> 直接用原始锚点 ----
    hits = [i for i, ln in enumerate(lines) if ln.strip() == 'state.requestScrollToItem(latestGroupIndex)']
    if len(hits) != 1:
        skip('requestScrollToItem anchor count=' + str(len(hits)))
    hi = hits[0]
    d = ind(lines[hi])

    new_block = [
        d + '// ' + MARK + ': 滚到列表末尾(最后一项底部对齐可用视口底部),不是把最后一项滚到视口顶部。',
        d + '// requestScrollToItem 的 scrollOffset 语义: item 顶部最终位于 视口起点+scrollOffset。',
        d + '// scrollOffset>0 = item 下移(向前滚); scrollOffset<0 = item 上移(向后滚)。',
        d + '// 目标: item 底部对齐 => targetOffset = availableHeight - itemHeight。',
        d + 'val rhViewportPx = state.layoutInfo.viewportEndOffset - state.layoutInfo.viewportStartOffset',
        d + 'val rhBottomInsetPx = with(density) { innerPadding.calculateBottomPadding().toPx() }.roundToInt()',
        d + 'val rhAvailablePx = (rhViewportPx - rhBottomInsetPx).coerceAtLeast(1) // ' + V2MARK,
        d + 'val rhLastItemHeight = visibleItemsInfo.firstOrNull { it.index == latestGroupIndex }?.size',
        d + 'val rhTargetOffset = if (rhLastItemHeight != null) {',
        d + '    rhAvailablePx - rhLastItemHeight',
        d + '} else {',
        d + '    -rhAvailablePx * 4',
        d + '}',
        d + 'state.requestScrollToItem(latestGroupIndex, scrollOffset = rhTargetOffset)',
    ]
    lines[hi:hi + 1] = new_block
    applied_mode = 'B-fresh'

out = NL.join(lines)
for need in [MARK, V2MARK, 'rhTargetOffset', 'requestScrollToItem(latestGroupIndex, scrollOffset = rhTargetOffset)']:
    if need not in out:
        skip('selfcheck missing: ' + need)
if 'scrollOffset = rhScrollOffset' in out:
    skip('stale v1 offset variable still referenced')
if balance(out) != bal0:
    skip('balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

(ROOT / F).write_text(out, encoding='utf-8')
print('::notice::batch171v2 OK (' + applied_mode + ') - scrollOffset direction corrected')

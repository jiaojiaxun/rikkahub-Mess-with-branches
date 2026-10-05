#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch93: 修复侧边栏会话列表「松手后自动弹回」(ConversationList.kt)

现象(用户):侧边栏会话列表往下滑,滑的时候没事,松手后过 1-2 秒列表自己弹回,
              停在「当前会话」那条附近。

根因(实读 ConversationList.kt):
    var hasScrolledToCurrent by remember(current.id) { mutableStateOf(false) }
    LaunchedEffect(current.id, conversations.itemCount, hasScrolledToCurrent) {
        if (hasScrolledToCurrent) return@LaunchedEffect
        val currentIndex = ...找当前会话...
        if (currentIndex >= 0) { if (!isVisible) listState.scrollToItem(currentIndex); hasScrolledToCurrent = true }
    }
  effect 的 key 含 conversations.itemCount(分页)。抽屉初次打开时数据未加载齐 ->
  currentIndex == -1 -> hasScrolledToCurrent 仍为 false;用户下滑触发加载下一页 ->
  itemCount 变化 -> effect 重跑 -> 这次找到当前会话(已被滑出屏幕)->
  scrollToItem 把列表拽回 = 用户看到的「弹回」。

修法:一旦用户手动滚动,本次就永久放弃自动定位(userDragged 锁存),绝不与手势抢。
      功能保留(不动时仍会定位),只是不再跟手。

五查:
1. import:新增 androidx.compose.runtime.snapshotFlow + kotlinx.coroutines.flow.collect
   (锚 import androidx.compose.runtime.setValue,该行唯一、batch55_4b 未触碰)
2. 同文件冲突:ConversationList.kt 被 batch55_4b 碰过(签名/ConversationItem/import),
   但本批锚点(顶部 LaunchedEffect 区 + setValue import)与那些改动零重叠(已实读在链脚本核对)
3. 作用域:userDragged 声明在 ConversationList 函数体内;effect 里对其赋值合法(state hoisting)
4. 括号配对:插入块自平衡(断言前后括号差值不变)
5. 函数签名:不改任何签名

Python 三查:引号走变量构造 / NL 手写 concat / helper 先定义后用 / 失败显式 exit(1)
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
D = chr(34)
MARK = 'rhDrawerScrollFix'
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ConversationList.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch93 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + '[' + str(len(lines[i]) - len(lines[i].lstrip())) + ']' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + CL + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


def ind_of(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def find_unique(lines, pred, label):
    hits = [i for i, ln in enumerate(lines) if pred(ln)]
    if len(hits) != 1:
        fail(label + ' count=' + str(len(hits)), lines, hits[0] if hits else 0)
    return hits[0]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


t = (ROOT / CL).read_text(encoding='utf-8')
if MARK in t:
    print('batch93: already applied')
    sys.exit(0)

bal0 = balance(t)
lines = t.split(NL)

# 1. import snapshotFlow + collect(锚 setValue,该行唯一且未被在链 patch 触碰)
if not any(ln.strip() == 'import androidx.compose.runtime.snapshotFlow' for ln in lines):
    i = find_unique(lines, lambda ln: ln.strip() == 'import androidx.compose.runtime.setValue', 'setValue import')
    lines.insert(i + 1, 'import androidx.compose.runtime.snapshotFlow')
    lines.insert(i + 2, 'import kotlinx.coroutines.flow.collect')

# 2. userDragged 状态 + 拖动检测 effect(插在 hasScrolledToCurrent 声明之后)
i = find_unique(
    lines,
    lambda ln: ln.strip() == 'var hasScrolledToCurrent by remember(current.id) { mutableStateOf(false) }',
    'hasScrolledToCurrent decl',
)
di = ind_of(lines[i])
block = [
    di + '// ' + MARK + ': 用户手动滚动后,永久放弃本次「自动定位到当前会话」',
    di + 'var userDragged by remember(current.id) { mutableStateOf(false) }',
    di + 'LaunchedEffect(listState, current.id) {',
    di + '    snapshotFlow { listState.isScrollInProgress }',
    di + '        .collect { scrolling -> if (scrolling) userDragged = true }',
    di + '}',
]
lines[i + 1:i + 1] = block

# 3. 原自动定位 effect 的 key 加 userDragged
j = find_unique(
    lines,
    lambda ln: ln.strip() == 'LaunchedEffect(current.id, conversations.itemCount, hasScrolledToCurrent) {',
    'auto-scroll effect',
)
dj = ind_of(lines[j])
lines[j] = dj + 'LaunchedEffect(current.id, conversations.itemCount, hasScrolledToCurrent, userDragged) {'

# 4. 提前返回判断加 userDragged
k = find_unique(
    lines,
    lambda ln: ln.strip() == 'if (hasScrolledToCurrent) return@LaunchedEffect',
    'early-return guard',
)
dk = ind_of(lines[k])
lines[k] = dk + 'if (hasScrolledToCurrent || userDragged) return@LaunchedEffect'

out = NL.join(lines)

for need in [
    'import androidx.compose.runtime.snapshotFlow',
    'import kotlinx.coroutines.flow.collect',
    'var userDragged by remember(current.id) { mutableStateOf(false) }',
    'snapshotFlow { listState.isScrollInProgress }',
    '.collect { scrolling -> if (scrolling) userDragged = true }',
    'LaunchedEffect(current.id, conversations.itemCount, hasScrolledToCurrent, userDragged) {',
    'if (hasScrolledToCurrent || userDragged) return@LaunchedEffect',
]:
    if need not in out:
        fail('selfcheck missing: ' + need)

if balance(out) != bal0:
    fail('bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

(ROOT / CL).write_text(out, encoding='utf-8')
print('batch93: OK (drawer auto-scroll no longer fights the user)')

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch140: 删除侧边栏重复的助手卡片 + batch117 按钮接切换功能

用户反馈(#4): 侧边栏两个助手显示重复。
- 上面一行 = batch117 卡(rhAssistantCard): 地球+助手名+模型名+LookTop钮(onClick空)
- 下面卡片 = batch48 卡(rhDrawer48): 地球+助手名+Greeting+⇆切换钮

用户要求: 让上面一行能切换助手(把下面卡片的⇄功能挪上去),删掉下面卡片。

改动(ChatDrawer.kt 单文件):
1. 删除 batch48 液态玻璃助手卡:
   锚点= '// rhDrawer48: 液态玻璃助手卡' 注释行 → Surface( 配平结束 } 删除整块。
   保留 showAssistantSheet/assistantState 状态(后续 AssistantPickerSheet 需要)。
2. batch117 卡 IconButton onClick: { } -> { showAssistantSheet = true }
   锚点= 'IconButton(onClick = { }) {' + 验证下一行含 'HugeIcons.LookTop'

五查:
1. import: 零新增(showAssistantSheet/assistantState 已由 batch48 NEW1 引入;
   HugeIcons.LookTop 已由 batch117 引入)
2. 同文件冲突: ChatDrawer.kt 被 batch48/74/85/117 碰过——锚点是 batch48/117
   的产物注释和代码,均为在链 patch 的确定性输出,不受后续 patch 影响
3. 作用域: showAssistantSheet 在 ChatDrawerContent 函数体内,batch117 卡同在;✓
4. 括号配对: 删除块自平衡(Surface 配平);onClick 单行替换不影响配平
5. 函数签名: 不改任何签名

Python 三查: 引号 Q=chr(34) 构造;无 f-string;helper 先定义后用;失败显式 exit(1)
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhRemoveDupCard'
CD = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatDrawer.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch140 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:100] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + CD + '::' + body[:1400])
    sys.stdout.flush()
    sys.exit(1)


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


t = (ROOT / CD).read_text(encoding='utf-8')
if MARK in t:
    print('batch140: already applied')
    sys.exit(0)

bal0 = balance(t)
lines = t.split(NL)
changed = 0

# ---- 1. 删除 batch48 液态玻璃助手卡 ----
mark_hits = [i for i, ln in enumerate(lines) if '// rhDrawer48' in ln and '液态玻璃助手卡' in ln]
if len(mark_hits) != 1:
    fail('rhDrawer48 card marker count=' + str(len(mark_hits)), lines, mark_hits[0] if mark_hits else 0)
mark_i = mark_hits[0]

surf_start = -1
for j in range(mark_i, min(mark_i + 3, len(lines))):
    if lines[j].strip() == 'Surface(':
        surf_start = j
        break
if surf_start < 0:
    fail('Surface( not found after rhDrawer48 marker', lines, mark_i)

depth = 0
surf_end = -1
for j in range(surf_start, min(surf_start + 80, len(lines))):
    depth += (lines[j].count('(') - lines[j].count(')')) + (lines[j].count('{') - lines[j].count('}'))
    if depth == 0 and j > surf_start:
        surf_end = j
        break
if surf_end < 0:
    fail('Surface block closing not found', lines, surf_start)

block_text = NL.join(lines[surf_start:surf_end + 1])
for need in ['UIAvatar', 'Greeting']:
    if need not in block_text:
        fail('batch48 card block missing ' + need, lines, surf_start)

del_start = mark_i
if del_start > 0 and lines[del_start - 1].strip() == '':
    del_start -= 1
lines = lines[:del_start] + lines[surf_end + 1:]
changed += 1
print('batch140: batch48 card removed (lines ' + str(del_start) + '..' + str(surf_end) + ')')

# ---- 2. batch117 卡 IconButton onClick 接切换 ----
ib_hits = [i for i, ln in enumerate(lines) if ln.strip() == 'IconButton(onClick = { }) {']
if len(ib_hits) != 1:
    fail('IconButton(onClick={}) count=' + str(len(ib_hits)), lines, ib_hits[0] if ib_hits else 0)
ib_i = ib_hits[0]

if ib_i + 1 >= len(lines) or 'HugeIcons.LookTop' not in lines[ib_i + 1]:
    fail('IconButton next line not LookTop', lines, ib_i)

old_line = lines[ib_i]
d = old_line[:len(old_line) - len(old_line.lstrip())]
lines[ib_i] = d + 'IconButton(onClick = { showAssistantSheet = true }) {  // ' + MARK
changed += 1
print('batch140: batch117 button wired to showAssistantSheet')

# ---- 3. 自检 ----
out = NL.join(lines)
if MARK not in out:
    fail('selfcheck: marker missing')
if '// rhDrawer48' in out and '液态玻璃助手卡' in out:
    fail('selfcheck: batch48 card comment still present')
if 'showAssistantSheet = true' not in out:
    fail('selfcheck: showAssistantSheet assignment missing')
if balance(out) != bal0:
    fail('selfcheck: balance ' + str(bal0) + ' -> ' + str(balance(out)))

(ROOT / CD).write_text(out, encoding='utf-8')
print('::notice::batch140 OK - dup card removed, batch117 button wired, changes=' + str(changed))

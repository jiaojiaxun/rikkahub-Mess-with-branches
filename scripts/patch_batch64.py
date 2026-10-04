#!/usr/bin/env python3
'''batch64: UI-2 消息卡淡入淡出（单文件 ChatList.kt）

老板需求三件套之二：流畅过渡动画——消息卡片进出淡入淡出。

设计（基于 ChatList.kt 实读 14500-21000 段）：
- LazyColumn items(displayGroups, key = { it.id }) 的 item 内容为
  `val node = group.terminalNode` + `Column { ListSelectableItem { ChatMessage } }`
- 给该 Column 加 Modifier.animateItem(fadeInSpec = tween(220),
  fadeOutSpec = tween(220))：新消息出现淡入、删除淡出（有 key 才触发）
- import androidx.compose.animation.core.tween（当前 import 表无，需加）

五查：
1. import 清单：tween 新增；Modifier 已有；animateItem 是 LazyItemScope
   成员（无需 import）；fadeInSpec/fadeOutSpec 为 animateItem 命名参数
2. 同文件冲突：ChatList.kt 前置链（batch2/3 消息渲染、batch53 加载行）
   均不碰 items 循环的 Column 行；锚点用仓库实读形态 + fail 时 dump
3. 作用域：items lambda 内 receiver 为 LazyItemScope，animateItem 可用；
   Modifier 顶层已导入
4. 括号配对：单行替换，替换行括号自平衡（脚本内计数自检）
5. 函数签名：LazyItemScope.animateItem(fadeInSpec: FiniteAnimationSpec<Float>?,
   fadeOutSpec: FiniteAnimationSpec<Float>?)；tween(220) 泛型推断为 Float

Python 三查：无引号字面量（无双引号/撇号）；无未定义引用；无 f-string/walrus/join
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)

FADE = 'animateItem(fadeInSpec = tween(220), fadeOutSpec = tween(220))'
TWEEN_IMPORT = 'import androidx.compose.animation.core.tween'
ANCHOR_PREV = 'val node = group.terminalNode'
ANCHOR_LINE = 'Column {'


def fail(path, msg):
    print('::error file=' + path + '::batch64 ' + str(msg)[:1400])
    raise SystemExit(1)


CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
t = (ROOT / CL).read_text(encoding='utf-8')
lines = t.split(NL)
changed = []

# ---- 1. 主替换：items 循环里 terminalNode 后的 Column { ----
if FADE not in t:
    candidates = []
    for i, ln in enumerate(lines):
        if ln.strip() == ANCHOR_PREV:
            j = i + 1
            while j < len(lines) and lines[j].strip() == '':
                j += 1
            if j < len(lines) and lines[j].strip() == ANCHOR_LINE:
                candidates.append(j)
    if len(candidates) != 1:
        print('batch64: dump candidate lines:')
        for i, ln in enumerate(lines):
            if ANCHOR_PREV in ln:
                print('  >> idx=' + str(i) + ' ' + ln.strip()[:120])
                nxt = lines[i + 1] if i + 1 < len(lines) else ''
                print('     next: ' + nxt.strip()[:120])
        fail(CL, 'terminalNode+Column candidate count=' + str(len(candidates)))
    k = candidates[0]
    old_line = lines[k]
    new_line = old_line.replace('Column {', 'Column(modifier = Modifier.' + FADE + ') {', 1)
    if new_line.count('(') != new_line.count(')'):
        fail(CL, 'paren imbalance after replacement')
    lines[k] = new_line
    changed.append('column-fade')
else:
    print('batch64: fade already applied')

# ---- 2. tween import（独立幂等）----
t2 = NL.join(lines)
if TWEEN_IMPORT not in t2:
    idx = -1
    for i, ln in enumerate(lines):
        if ln.strip() == 'import androidx.compose.animation.fadeIn':
            idx = i
            break
    if idx < 0:
        fail(CL, 'fadeIn import anchor not found for tween import')
    lines = lines[:idx] + [TWEEN_IMPORT] + lines[idx:]
    changed.append('tween-import')
else:
    print('batch64: tween import already present')

# ---- 3. 自检 ----
text = NL.join(lines)
if FADE not in text:
    fail(CL, 'fade marker missing after apply')
if TWEEN_IMPORT not in text:
    fail(CL, 'tween import missing after apply')

if changed:
    (ROOT / CL).write_text(text, encoding='utf-8')
    print('batch64: OK (' + ', '.join(changed) + ')')
else:
    print('batch64: no changes (already applied)')

print('batch64: done')

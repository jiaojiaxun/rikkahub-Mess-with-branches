#!/usr/bin/env python3
'''batch80v6: 顶栏视觉对齐输入框（R4）—— 修 #225 自检假阳性

#225 验尸：v5 自检 `'hazeBlur' in t` 裸子串命中 import 行
`import dev.chrisbanes.haze.blur.hazeBlur`（五查决定保留该 import=仅警告），
误报残留 → patch fail。块删除本身成功（block at 898 删除，TopAppBar 唯一 897）。

v6 = v5 + 残留检查改【调用形态】：
- hazeBlur(  带括号 → import 行不含括号不误伤
- HazeInput.Sources(  同理
- blurRadius(20.dp) 不变（import 行不含此串）
其余逻辑与 v5 完全一致（结构化配平删除 + 同缩进闭合 + Surface 包裹 + 配平断言）。
'''
from pathlib import Path
ROOT = Path.cwd()
NL = chr(10)
M = 'rhTopBarAlignInput'

def fail(p, m):
    print('::error file=' + p + '::batch80v6 ' + str(m)[:1200])
    raise SystemExit(1)

def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]

def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))

def remove_block(lines, start):
    depth = 0
    started = False
    i = start
    while i < len(lines):
        for ch in lines[i]:
            if ch in '({':
                depth += 1
                started = True
            elif ch in ')}':
                depth -= 1
        i += 1
        if started and depth <= 0:
            return lines[:start] + lines[i:]
    return None

CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
t = (ROOT / CP).read_text(encoding='utf-8')
if M in t:
    print('batch80v6: already applied')
else:
    # 0. 展开多行元素
    lines = []
    for ln in t.split(NL):
        if NL in ln:
            lines.extend(ln.split(NL))
        else:
            lines.append(ln)
    bal_before = balance(NL.join(lines))

    # 1. import 新增
    box_idx = [i for i, ln in enumerate(lines) if ln.strip() == 'import androidx.compose.foundation.layout.Box']
    if len(box_idx) != 1:
        fail(CP, 'Box import anchor count=' + str(len(box_idx)))
    need = ['import androidx.compose.foundation.BorderStroke', 'import androidx.compose.foundation.border']
    existing = set(ln.strip() for ln in lines)
    add = [x for x in need if x not in existing]
    for j, imp in enumerate(add):
        lines.insert(box_idx[0] + 1 + j, imp)

    # 2. 结构化删除 hazeBlur 块（循环，guard）
    guard = 0
    while True:
        starts = [i for i, ln in enumerate(lines) if 'hazeBlur(' in ln]
        if not starts:
            break
        guard += 1
        if guard > 5:
            fail(CP, 'too many hazeBlur blocks')
        removed = remove_block(lines, starts[0])
        if removed is None:
            fail(CP, 'hazeBlur block unbalanced at line ' + str(starts[0]))
        lines = removed
        print('batch80v6: removed hazeBlur block at ' + str(starts[0]))
    lines = [ln for ln in lines if 'rhTopBarBlur' not in ln]

    # 3. TopAppBar 锚点
    top_idx = [i for i, ln in enumerate(lines) if 'TopAppBar(' in ln and 'TopAppBarDefaults' not in ln and 'import' not in ln]
    if len(top_idx) != 1:
        print('batch80v6: dump TopAppBar candidates:')
        for i, ln in enumerate(lines):
            if 'TopAppBar' in ln:
                print('  >> line ' + str(i) + ': ' + ln.strip()[:160])
        fail(CP, 'TopAppBar anchor count=' + str(len(top_idx)))
    ti = top_idx[0]
    d = ind(lines[ti])
    print('batch80v6: TopAppBar line=' + str(ti))

    # 4. 闭合：strip==')' 且同缩进
    close = -1
    for i in range(ti + 1, len(lines)):
        if lines[i].strip() == ')' and ind(lines[i]) == d:
            close = i
            break
    if close < 0:
        print('batch80v6: dump after TopAppBar:')
        for i in range(ti, min(ti + 60, len(lines))):
            print('  >> ' + str(i) + ' [' + str(len(ind(lines[i]))) + '] ' + lines[i].strip()[:120])
        fail(CP, 'TopAppBar close paren not found')

    # 5. Surface 包裹
    surf = [
        d + 'Surface( // ' + M,
        d + '    shape = MaterialTheme.shapes.largeIncreased,',
        d + '    color = MaterialTheme.colorScheme.surfaceContainerLow,',
        d + '    border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)),',
        d + '    tonalElevation = 0.dp,',
        d + ') {',
    ]
    for j, b in enumerate(surf):
        lines.insert(ti + j, b)
    close += len(surf)
    lines.insert(close + 1, d + '}')

    t = NL.join(lines)
    # 6. 自检：调用形态残留（带括号，不误伤 import 行）
    for k in ['hazeBlur(', 'HazeInput.Sources(', 'blurRadius(20.dp)', 'HazeBlurStyle {']:
        if k in t:
            fail(CP, 'haze residue (call form): ' + k)
    for need_t in [M, 'MaterialTheme.shapes.largeIncreased', 'surfaceContainerLow', 'BorderStroke(1.dp']:
        if need_t not in t:
            fail(CP, 'selfcheck missing: ' + need_t)
    if balance(t) != bal_before:
        fail(CP, 'bracket balance changed: before=' + str(bal_before) + ' after=' + str(balance(t)))
    (ROOT / CP).write_text(t, encoding='utf-8')
    print('batch80v6: OK (call-form residue check, balance preserved)')

print('batch80v6: done')

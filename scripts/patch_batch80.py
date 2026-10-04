#!/usr/bin/env python3
'''batch80v3: 顶栏视觉对齐输入框（R4）—— 修 #222 ind() 拼写 bug

#222 死因：ind() 写成 len(ln).lstrip()（int.lstrip 崩），
应为 len(ln.lstrip())（先 lstrip 再 len）。

v3 = v2 + ind 函数修正。其余逻辑不变。
'''
from pathlib import Path
ROOT = Path.cwd()
NL = chr(10)
M = 'rhTopBarAlignInput'

def fail(p, m):
    print('::error file=' + p + '::batch80v3 ' + str(m)[:1200])
    raise SystemExit(1)

def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]

CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
t = (ROOT / CP).read_text(encoding='utf-8')
if M in t:
    print('batch80v3: already applied')
else:
    lines = t.split(NL)

    # 1. import
    box_idx = [i for i, ln in enumerate(lines) if ln.strip() == 'import androidx.compose.foundation.layout.Box']
    if len(box_idx) != 1:
        fail(CP, 'Box import anchor count=' + str(len(box_idx)))
    need = [
        'import androidx.compose.foundation.BorderStroke',
        'import androidx.compose.foundation.border',
    ]
    existing = set(ln.strip() for ln in lines)
    add = [x for x in need if x not in existing]
    for j, imp in enumerate(add):
        lines.insert(box_idx[0] + 1 + j, imp)

    # 2. 找 TopAppBar( 调用行
    top_idx = [i for i, ln in enumerate(lines) if 'TopAppBar(' in ln and 'TopAppBarDefaults' not in ln and 'import' not in ln]
    if len(top_idx) != 1:
        print('batch80v3: dump TopAppBar candidates:')
        for i, ln in enumerate(lines):
            if 'TopAppBar' in ln:
                print('  >> line ' + str(i) + ': ' + ln.strip()[:160])
        fail(CP, 'TopAppBar anchor count=' + str(len(top_idx)))
    ti = top_idx[0]

    # 3. 删 hazeBlur 注入行
    kill = [i for i, ln in enumerate(lines) if 'rhTopBarBlur' in ln or 'hazeBlur(' in ln or 'HazeInput.Sources' in ln or 'HazeBlurStyle' in ln]
    for i in sorted(kill, reverse=True):
        del lines[i]

    # 重新定位 ti
    top_idx = [i for i, ln in enumerate(lines) if 'TopAppBar(' in ln and 'TopAppBarDefaults' not in ln and 'import' not in ln]
    if len(top_idx) != 1:
        fail(CP, 'TopAppBar re-anchor count=' + str(len(top_idx)) + ' after hazeBlur removal')
    ti = top_idx[0]
    d = ind(lines[ti])

    # 4. 找 TopAppBar 闭合：strip==')' 且缩进==d
    close = -1
    for i in range(ti + 1, len(lines)):
        if lines[i].strip() == ')' and ind(lines[i]) == d:
            close = i
            break
    if close < 0:
        print('batch80v3: dump lines after TopAppBar (looking for close paren):')
        for i in range(ti, min(ti + 60, len(lines))):
            print('  >> ' + str(i) + ' [' + str(len(ind(lines[i]))) + '] ' + lines[i].strip()[:120])
        fail(CP, 'TopAppBar close paren (same-indent) not found')

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
    for need_t in [M, 'MaterialTheme.shapes.largeIncreased', 'surfaceContainerLow', 'BorderStroke(1.dp']:
        if need_t not in t:
            fail(CP, 'selfcheck missing: ' + need_t)
    (ROOT / CP).write_text(t, encoding='utf-8')
    print('batch80v3: OK (ind fixed, Surface wraps TopAppBar, hazeBlur removed)')

print('batch80v3: done')

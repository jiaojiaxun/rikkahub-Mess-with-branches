#!/usr/bin/env python3
'''batch80v4: 顶栏视觉对齐输入框（R4）—— 修 #223 hazeBlur 残留

#223 死因：batch62 注入的 hazeBlur 是【一个含换行的多行元素】（list 单元素带 NL）。
v3 的 kill 循环按元素匹配，只删了含 hazeBlur( 的整元素，但同一元素里的
blurRadius/HazeBlurStyle 行是元素内文本——实际删了整元素才对……
真实残留：batch62 的 else 分支 `.then(Modifier.hazeBlur(` + blurRadius 是
【另一个】按行插入的 add_line 元素，v3 kill 覆盖了 hazeBlur( 但 add_line
里 blurRadius 单独成行（含 indent）也含 hazeBlur( … 实测仍有 blurRadius 残留。
且 TopAppBar( 行受损（colors Unresolved）。

v4 铁律 19/22：多行构造按 NL 拆成单行再逐行过滤；TopAppBar 锚点 dump 确认。

改法：
1. 先把所有含标记的元素 split(NL) 展开成单行
2. 逐行过滤掉含 hazeBlur/HazeInput/HazeBlurStyle/blurRadius/rhTopBarBlur 的行
3. 过滤后再 dump 找 TopAppBar(，确认唯一且形态完整
4. Surface 包裹（同 v3）
'''
from pathlib import Path
ROOT = Path.cwd()
NL = chr(10)
M = 'rhTopBarAlignInput'
KILL = ['hazeBlur', 'HazeInput', 'HazeBlurStyle', 'blurRadius', 'rhTopBarBlur']

def fail(p, m):
    print('::error file=' + p + '::batch80v4 ' + str(m)[:1200])
    raise SystemExit(1)

def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]

CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
t = (ROOT / CP).read_text(encoding='utf-8')
if M in t:
    print('batch80v4: already applied')
else:
    # 0. 展开所有多行元素 → 单行列表
    raw = t.split(NL)
    lines = []
    for ln in raw:
        if NL in ln:
            lines.extend(ln.split(NL))
        else:
            lines.append(ln)

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

    # 2. 逐行过滤 hazeBlur 系（含多行展开后的所有行）
    before = len(lines)
    lines = [ln for ln in lines if not any(k in ln for k in KILL)]
    print('batch80v4: removed ' + str(before - len(lines)) + ' haze lines')

    # 3. dump 找 TopAppBar( 调用行
    top_idx = [i for i, ln in enumerate(lines) if 'TopAppBar(' in ln and 'TopAppBarDefaults' not in ln and 'import' not in ln]
    if len(top_idx) != 1:
        print('batch80v4: dump TopAppBar candidates:')
        for i, ln in enumerate(lines):
            if 'TopAppBar' in ln:
                print('  >> line ' + str(i) + ': ' + ln.strip()[:160])
        fail(CP, 'TopAppBar anchor count=' + str(len(top_idx)))
    ti = top_idx[0]
    d = ind(lines[ti])
    print('batch80v4: TopAppBar at line ' + str(ti) + ' [' + lines[ti].strip()[:80] + ']')

    # 4. 找闭合：strip==')' 且缩进==d
    close = -1
    for i in range(ti + 1, len(lines)):
        if lines[i].strip() == ')' and ind(lines[i]) == d:
            close = i
            break
    if close < 0:
        print('batch80v4: dump after TopAppBar:')
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
    # 自检：残留归零 + 新增到位
    for k in KILL:
        if k in t and k != 'rhTopBarBlur':
            fail(CP, 'haze residue still present: ' + k)
    for need_t in [M, 'MaterialTheme.shapes.largeIncreased', 'surfaceContainerLow', 'BorderStroke(1.dp']:
        if need_t not in t:
            fail(CP, 'selfcheck missing: ' + need_t)
    (ROOT / CP).write_text(t, encoding='utf-8')
    print('batch80v4: OK')

print('batch80v4: done')

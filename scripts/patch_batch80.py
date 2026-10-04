#!/usr/bin/env python3
'''batch80v5: 顶栏视觉对齐输入框（R4）—— 结构化删除 hazeBlur 块

#223 死因实证 + batch63 源码确认 CI 形态：
batch62 的 blur_line 是单个多行元素，插入在 TopAppBar( 之后：
    modifier = Modifier.hazeBlur(
        input = HazeInput.Sources(hazeState),
        style = HazeBlurStyle {
            blurRadius(20.dp)
        },
    ),
    // rhTopBarBlur
v4 的标记过滤会残留 `},` `),` 两行孤儿（不含标记）→ 语法崩。

v5 改【括号配平结构化删除】（铁律 19 多行构造用配平扫描，不用行标记）：
1. 展开多行元素成单行
2. 找含 hazeBlur( 的行，从该行起删到括号深度归零（消费掉 }, 和 ),）
3. 删 // rhTopBarBlur 注释行
4. dump 找 TopAppBar(，strip==')' 且同缩进 找闭合（铁律 19）
5. Surface 包裹
6. 自检：无 hazeBlur 残留 + 前后括号配平一致（铁律 21）

五查：import（BorderStroke/border 新增，haze 4 个 import 保留=仅警告）/
同文件冲突（batch62/63 形态已实读确认）/作用域（TopBar @Composable 内）/
括号配平（结构化删除+前后配平断言）/签名（TopBar 不改）
Python 三查：无引号字面量/无未定义/无 f-string；ind 函数体 len(ln.lstrip()) 已修正
'''
from pathlib import Path
ROOT = Path.cwd()
NL = chr(10)
M = 'rhTopBarAlignInput'

def fail(p, m):
    print('::error file=' + p + '::batch80v5 ' + str(m)[:1200])
    raise SystemExit(1)

def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]

def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))

def remove_block(lines, start):
    '''从 start 行（含）删除到括号深度归零，返回新列表'''
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
    print('batch80v5: already applied')
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

    # 2. 结构化删除 hazeBlur 块（可能多个，循环直到没有）
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
        print('batch80v5: removed hazeBlur block at ' + str(starts[0]))
    # 删注释行
    lines = [ln for ln in lines if 'rhTopBarBlur' not in ln]

    # 3. TopAppBar 锚点（dump 确认）
    top_idx = [i for i, ln in enumerate(lines) if 'TopAppBar(' in ln and 'TopAppBarDefaults' not in ln and 'import' not in ln]
    if len(top_idx) != 1:
        print('batch80v5: dump TopAppBar candidates:')
        for i, ln in enumerate(lines):
            if 'TopAppBar' in ln:
                print('  >> line ' + str(i) + ': ' + ln.strip()[:160])
        fail(CP, 'TopAppBar anchor count=' + str(len(top_idx)))
    ti = top_idx[0]
    d = ind(lines[ti])
    print('batch80v5: TopAppBar line=' + str(ti) + ' [' + lines[ti].strip()[:70] + ']')

    # 4. 闭合：strip==')' 且同缩进
    close = -1
    for i in range(ti + 1, len(lines)):
        if lines[i].strip() == ')' and ind(lines[i]) == d:
            close = i
            break
    if close < 0:
        print('batch80v5: dump after TopAppBar:')
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
    # 6. 自检
    for k in ['hazeBlur', 'HazeInput.Sources', 'blurRadius(20.dp)']:
        if k in t:
            fail(CP, 'haze residue: ' + k)
    for need_t in [M, 'MaterialTheme.shapes.largeIncreased', 'surfaceContainerLow', 'BorderStroke(1.dp']:
        if need_t not in t:
            fail(CP, 'selfcheck missing: ' + need_t)
    if balance(t) != bal_before:
        fail(CP, 'bracket balance changed: before=' + str(bal_before) + ' after=' + str(balance(t)))
    (ROOT / CP).write_text(t, encoding='utf-8')
    print('batch80v5: OK (balance preserved, haze fully removed)')

print('batch80v5: done')

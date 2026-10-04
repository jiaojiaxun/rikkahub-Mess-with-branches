#!/usr/bin/env python3
'''batch80v2: 顶栏视觉对齐输入框（R4）—— 修 #221 close paren not found

#221 死因：batch80 用 depth 扫描找 TopAppBar 的 ')'，但 TopAppBar 调用里
lambda 的 ( ) 让 depth 提前归零 break，找不到真正的闭合。

v2 修复：不用 depth 计数。改为【行级 strip 精确匹配】找 TopAppBar 调用块的
闭合行 —— 从 ti 往下找第一个 strip == ')' 且缩进 == TopAppBar( 的缩进。
（Kotlin 命名参数调用收尾是独立 ')'，缩进与调用起点一致）

五查：
1. import 清单：BorderStroke + border 两个新符号（Box/Surface/MaterialTheme/dp/Color 已 import）
   ——已核实 ChatPage.kt 现有 import 覆盖其余
2. 同文件冲突：ChatPage.kt 被 batch62/63 碰过——锚点 TopAppBar( 行 + hazeBlur 行不在同区域冲突
3. 作用域：TopBar 函数体内（@Composable）Surface { TopAppBar } 合法
4. 括号配对：Surface { } 一层 + TopAppBar( ) 原样保留；close=strip==')' 且同缩进 → 可靠
5. 函数签名：TopBar 不改签名

Python 三查：无引号字面量 / 无未定义引用 / 无 f-string/walrus/join
'''
from pathlib import Path
ROOT = Path.cwd()
NL = chr(10)
M = 'rhTopBarAlignInput'

def fail(p, m):
    print('::error file=' + p + '::batch80v2 ' + str(m)[:1200])
    raise SystemExit(1)

def ind(ln):
    return ln[:len(ln) - len(ln).lstrip()]

CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
t = (ROOT / CP).read_text(encoding='utf-8')
if M in t:
    print('batch80v2: already applied')
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

    # 2. 找 TopAppBar( 调用行（排除 TopAppBarDefaults）
    top_idx = [i for i, ln in enumerate(lines) if 'TopAppBar(' in ln and 'TopAppBarDefaults' not in ln and 'import' not in ln]
    if len(top_idx) != 1:
        print('batch80v2: dump TopAppBar candidates:')
        for i, ln in enumerate(lines):
            if 'TopAppBar' in ln:
                print('  >> line ' + str(i) + ': ' + ln.strip()[:160])
        fail(CP, 'TopAppBar anchor count=' + str(len(top_idx)))
    ti = top_idx[0]
    d = ind(lines[ti])

    # 3. 删 hazeBlur 注入行（batch62 加的）
    kill = [i for i, ln in enumerate(lines) if 'rhTopBarBlur' in ln or 'hazeBlur(' in ln or 'HazeInput.Sources' in ln or 'HazeBlurStyle' in ln]
    for i in sorted(kill, reverse=True):
        del lines[i]

    # 重新定位 ti（删行后可能位移）
    top_idx = [i for i, ln in enumerate(lines) if 'TopAppBar(' in ln and 'TopAppBarDefaults' not in ln and 'import' not in ln]
    ti = top_idx[0]
    d = ind(lines[ti])

    # 4. 找 TopAppBar 调用的闭合：往下找 strip==')' 且缩进==d
    close = -1
    for i in range(ti + 1, len(lines)):
        if lines[i].strip() == ')' and ind(lines[i]) == d:
            close = i
            break
    if close < 0:
        # dump 现场
        print('batch80v2: dump lines after TopAppBar (looking for close paren):')
        for i in range(ti, min(ti + 60, len(lines))):
            print('  >> ' + str(i) + ' [' + ind(lines[i]) + '] ' + lines[i].strip()[:120])
        fail(CP, 'TopAppBar close paren (same-indent) not found')

    # 5. 在 TopAppBar( 前插 Surface(，在 close 后插 )
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
    # close 索引位移了 surf 长度
    close += len(surf)
    lines.insert(close + 1, d + '}')

    t = NL.join(lines)
    for need_t in [M, 'MaterialTheme.shapes.largeIncreased', 'surfaceContainerLow', 'BorderStroke(1.dp']:
        if need_t not in t:
            fail(CP, 'selfcheck missing: ' + need_t)
    (ROOT / CP).write_text(t, encoding='utf-8')
    print('batch80v2: OK (Surface wraps TopAppBar, hazeBlur removed, close=同缩进)')

print('batch80v2: done')

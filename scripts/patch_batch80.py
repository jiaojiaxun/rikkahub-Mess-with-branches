#!/usr/bin/env python3
'''batch80: 顶栏视觉对齐输入框（R4）

根因（实读确认）：
- 输入框容器 = Surface(shape=MaterialTheme.shapes.largeIncreased,
                     color=MaterialTheme.colorScheme.surfaceContainerLow,
                     border=BorderStroke(1.dp, outlineVariant.copy(alpha=0.5f)),
                     tonalElevation=0.dp)  ← 实心卡片，无真模糊
- 顶栏 = TopAppBar(containerColor=Transparent) + batch62 叠 hazeBlur(20dp)  ← 真模糊，观感撕裂

改法：删除 batch62 注入的 hazeBlur，改为把 TopAppBar 包进与输入框同参数的 Surface。
（这样两者是同一套视觉语言：实心卡片 + 细描边 + largeIncreased 圆角）

五查：
1. import 清单：需加 BorderStroke + BorderStroke 构造（BorderStroke 在 foundation.border 包）
   ——实际需要 import androidx.compose.foundation.border + shape 构造
   ——ChatPage.kt 现有 import 是否够？需加：androidx.compose.foundation.BorderStroke,
   androidx.compose.foundation.border, androidx.compose.foundation.layout.Box
   ——已核：Box 已 import（ChatPage 签名区有 Box），BorderStroke/border 未 import → 新增
2. 同文件冲突：ChatPage.kt 被 batch62/63 碰过——锚点用 TopAppBar( 行，避开 hazeBlur 注入行
3. 作用域：TopBar 函数体内（@Composable），Surface 包 TopAppBar 合法
4. 括号配对：Surface { TopAppBar(...) } 需括号配平——用包一层不嵌套多层 lambda，自平衡
5. 函数签名：TopBar(private fun) 不改签名

Python 三查：无引号字面量 / 无未定义引用 / 无 f-string/walrus/join
'''
from pathlib import Path
ROOT = Path.cwd()
NL = chr(10)
M = 'rhTopBarAlignInput'

def fail(p, m):
    print('::error file=' + p + '::batch80 ' + str(m)[:1200])
    raise SystemExit(1)

def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]

CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
t = (ROOT / CP).read_text(encoding='utf-8')
if M in t:
    print('batch80: already applied')
else:
    lines = t.split(NL)

    # 1. 新增 import（锚点：import androidx.compose.foundation.layout.Box）
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
    # 2. 找 TopAppBar( 调用行（可能带 hazeBlur 注入）
    top_idx = [i for i, ln in enumerate(lines) if 'TopAppBar(' in ln and 'TopAppBarDefaults' not in ln]
    if len(top_idx) != 1:
        print('batch80: dump TopAppBar candidates:')
        for i, ln in enumerate(lines):
            if 'TopAppBar(' in ln:
                print('  >> line ' + str(i) + ': ' + ln.strip()[:160])
        fail(CP, 'TopAppBar anchor count=' + str(len(top_idx)))
    ti = top_idx[0]
    d = ind(lines[ti])
    # 3. 删 batch62 注入的 hazeBlur（若有），找 modifier = Modifier.hazeBlur 或 .then(Modifier.hazeBlur
    remove_from = -1
    for i in range(ti, min(ti + 20, len(lines))):
        s = lines[i].strip()
        if 'hazeBlur(' in s or 'HazeInput.Sources' in s or 'HazeBlurStyle' in s:
            if remove_from < 0:
                remove_from = i
    # 简化：不动 modifier，只包 Surface，把 hazeBlur 留着（不产生额外视觉差异时用户可接受）
    # 但用户明确说顶栏丑 → 需去掉 hazeBlur。找到 modifier = Modifier.hazeBlur(...) 整块删除
    # 采用保守法：找带 MARK(旧 rhTopBarBlur) 的行删除
    kill = [i for i, ln in enumerate(lines) if 'rhTopBarBlur' in ln or 'hazeBlur(' in ln]
    for i in sorted(kill, reverse=True):
        del lines[i]
    # 4. 在 TopAppBar( 前插 Surface 包装
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
    # 找 TopAppBar( 的收尾 ) 在函数内
    close = -1
    depth = 0
    for i in range(ti + len(surf), min(ti + 80, len(lines))):
        for ch in lines[i]:
            if ch == '(':
                depth += 1
            elif ch == ')':
                if depth == 0:
                    close = i
                    break
                depth -= 1
        if close >= 0:
            break
    if close < 0:
        fail(CP, 'TopAppBar close paren not found')
    lines.insert(close + 1, d + '}')
    t = NL.join(lines)
    for need_t in [M, 'MaterialTheme.shapes.largeIncreased', 'surfaceContainerLow', 'BorderStroke(1.dp']:
        if need_t not in t:
            fail(CP, 'selfcheck missing: ' + need_t)
    (ROOT / CP).write_text(t, encoding='utf-8')
    print('batch80: OK (Surface wraps TopAppBar, hazeBlur removed)')

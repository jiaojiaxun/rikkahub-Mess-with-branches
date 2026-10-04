#!/usr/bin/env python3
'''batch74: 新需求 A+B——侧边栏白色亮边 + 底部设置区圆润（ChatDrawer.kt）

A（白色亮边）：ModalDrawerSheet 加 border(1dp, White 20%, modalDrawerShape)
B（底部圆润）：底部 DrawerAction Row 区域包圆角 Surface（RoundedCornerShape 20dp）

五查：
1. import 清单：4 个新 import（border/DrawerDefaults/Color/RoundedCornerShape），
   实读 ChatDrawer.kt imports 确认全部缺失，逐一插入
2. 同文件冲突：ChatDrawer.kt 无在链脚本碰（最近无 batch 修改此文件）
3. 作用域：ModalDrawerSheet 在 ChatDrawerContent 内（实读确认）；
   底部 Row 在 AssistantPicker 之后（实读确认）
4. 括号配对：border 块自平衡；Surface 包裹用锚点定位，不依赖括号计数
5. 函数签名：无签名改动

Python 三查：无引号字面量 / 无未定义引用 / 无 f-string/walrus/join
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhDrawerPolish'


def concat_lines(lines):
    text = ''
    for index, line in enumerate(lines):
        if index > 0:
            text += NL
        text += line
    return text


def fail(path, message):
    print('::error file=' + path + '::batch74 ' + str(message)[:1400])
    raise SystemExit(1)


def indent_of(line):
    return line[:len(line) - len(line.lstrip())]


def insert_import(lines, new_import, anchor_prefix):
    '''在指定前缀的 import 行后插入新 import，返回插入后的行索引'''
    for index, line in enumerate(lines):
        if line.strip().startswith(anchor_prefix):
            lines.insert(index + 1, new_import)
            return index + 1
    return -1


CD = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatDrawer.kt'
t = (ROOT / CD).read_text(encoding='utf-8')
if MARK in t:
    print('batch74: already applied')
else:
    lines = t.split(NL)
    applied = []

    # ============================================================
    # 1. Import 清单（4 个新 import，逐一检查+插入）
    # ============================================================
    NEW_IMPORTS = [
        ('import androidx.compose.foundation.border', 'import androidx.compose.foundation.combinedClickable'),
        ('import androidx.compose.foundation.shape.RoundedCornerShape', 'import androidx.compose.foundation.shape.CircleShape'),
        ('import androidx.compose.material3.DrawerDefaults', 'import androidx.compose.material3.ModalDrawerSheet'),
        ('import androidx.compose.ui.graphics.Color', 'import androidx.compose.ui.graphics.vector.ImageVector'),
    ]
    for new_imp, anchor_prefix in NEW_IMPORTS:
        already = False
        for line in lines:
            if line.strip() == new_imp:
                already = True
                break
        if not already:
            idx = insert_import(lines, new_imp, anchor_prefix)
            if idx < 0:
                fail(CD, 'import anchor not found: ' + anchor_prefix)
            applied.append('import:' + new_imp.split('.')[-1])

    # ============================================================
    # 2. A: ModalDrawerSheet 加白色亮边
    # ============================================================
    # 锚点：modifier = Modifier.width(300.dp) 行（实读确认唯一）
    width_indices = []
    for index, line in enumerate(lines):
        if line.strip() == 'modifier = Modifier.width(300.dp)':
            width_indices.append(index)
    if len(width_indices) != 1:
        fail(CD, 'ModalDrawerSheet width anchor count=' + str(len(width_indices)))
    wi = width_indices[0]
    ind = indent_of(lines[wi])
    lines[wi:wi + 1] = [
        ind + 'modifier = Modifier',
        ind + '    .width(300.dp)',
        ind + '    .border(',
        ind + '        width = 1.dp,',
        ind + '        color = Color.White.copy(alpha = 0.2f), // ' + MARK,
        ind + '        shape = DrawerDefaults.modalDrawerShape,',
        ind + '    )',
    ]
    applied.append('drawer-border')

    # ============================================================
    # 3. B: 底部设置区包圆角 Surface
    # ============================================================
    # 锚点：horizontalArrangement = Arrangement.SpaceAround（实读确认唯一）
    space_indices = []
    for index, line in enumerate(lines):
        if 'horizontalArrangement = Arrangement.SpaceAround' in line:
            space_indices.append(index)
    if len(space_indices) != 1:
        fail(CD, 'SpaceAround anchor count=' + str(len(space_indices)))
    sa = space_indices[0]
    # Row( 在 SpaceAround 的上一行
    if sa < 1 or lines[sa - 1].strip() != 'Row(':
        fail(CD, 'Row( not found above SpaceAround; dump prev=' + lines[sa - 1].strip()[:120])
    row_start = sa - 1
    row_indent = indent_of(lines[row_start])

    # 在 Row( 之前插入 Surface 开始
    lines[row_start:row_start] = [
        row_indent + 'Surface(',
        row_indent + '    shape = RoundedCornerShape(20.dp), // ' + MARK,
        row_indent + '    color = MaterialTheme.colorScheme.surfaceContainerLow,',
        row_indent + '    modifier = Modifier.fillMaxWidth(),',
        row_indent + ') {',
    ]

    # 找底部 Row 的结束：从 navController.navigate(Screen.Setting) 往下找
    # DrawerAction 的 ) 结束行，再找 } 结束 Row，在其后插 Surface 的 }
    setting_indices = []
    for index, line in enumerate(lines):
        if 'navController.navigate(Screen.Setting)' in line and 'Screen.Setting)' in line and 'Search' not in line:
            setting_indices.append(index)
    if len(setting_indices) < 1:
        fail(CD, 'Settings DrawerAction navigate anchor not found')
    # 用最后一个匹配（底部设置按钮在文件后部）
    si = setting_indices[-1]
    # 从 si 往下找 DrawerAction 的 ) 结束行
    drawer_close = -1
    for index in range(si + 1, min(si + 10, len(lines))):
        if lines[index].strip() == ')':
            drawer_close = index
            break
    if drawer_close < 0:
        fail(CD, 'DrawerAction close paren not found after Settings navigate')
    # 再找 Row 的 } 结束行
    row_close = -1
    for index in range(drawer_close + 1, min(drawer_close + 5, len(lines))):
        if lines[index].strip() == '}':
            row_close = index
            break
    if row_close < 0:
        fail(CD, 'Row close brace not found after DrawerAction')
    # 在 Row 结束后插入 Surface 的 }
    lines.insert(row_close + 1, row_indent + '}')
    applied.append('bottom-rounded')

    # ============================================================
    # 4. 自检
    # ============================================================
    text = concat_lines(lines)
    if MARK not in text:
        fail(CD, 'marker missing after apply')
    if 'DrawerDefaults.modalDrawerShape' not in text:
        fail(CD, 'modalDrawerShape reference missing')
    if 'RoundedCornerShape(20.dp)' not in text:
        fail(CD, 'RoundedCornerShape reference missing')
    for new_imp, _ in NEW_IMPORTS:
        if new_imp not in text:
            fail(CD, 'import missing after apply: ' + new_imp)
    (ROOT / CD).write_text(text, encoding='utf-8')
    print('batch74: OK (' + ', '.join(applied) + ')')

print('batch74: done')

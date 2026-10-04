#!/usr/bin/env python3
'''batch74v3: 侧边栏白色亮边 + 底部设置区圆润（ChatDrawer.kt）

#201 第三人称复核结果：
- v2 patch 阶段成功，说明 Settings03 -> 最近 Row( 的定位真实可行
- 编译唯一错误是 DrawerDefaults.modalDrawerShape 不存在，不是定位错误

v3 修复：
- 不依赖版本中不存在的 DrawerDefaults.modalDrawerShape
- 使用本文件已有需求范围内的 RoundedCornerShape(16.dp)
- Settings03 icon 必须唯一，防止最后一个索引误包其他组件

五查：import/冲突/作用域/括号/签名；Python 三查全部脚本内执行。
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
    print('::error file=' + path + '::batch74v3 ' + str(message)[:1400])
    raise SystemExit(1)


def indent_of(line):
    return line[:len(line) - len(line.lstrip())]


def insert_import(lines, new_import, anchor_prefix):
    for index, line in enumerate(lines):
        if line.strip().startswith(anchor_prefix):
            lines.insert(index + 1, new_import)
            return index + 1
    return -1


CD = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatDrawer.kt'
t = (ROOT / CD).read_text(encoding='utf-8')
if MARK in t:
    print('batch74v3: already applied')
else:
    lines = t.split(NL)
    applied = []

    # 1. Import 清单：DrawerDefaults 不再需要；其余 3 个 import 必须精确存在
    NEW_IMPORTS = [
        ('import androidx.compose.foundation.border', 'import androidx.compose.foundation.combinedClickable'),
        ('import androidx.compose.foundation.shape.RoundedCornerShape', 'import androidx.compose.foundation.shape.CircleShape'),
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

    # 若旧版本脚本文件在其他链状态中曾留下 DrawerDefaults import，明确删除它
    lines = [line for line in lines if line.strip() != 'import androidx.compose.material3.DrawerDefaults']

    # 2. A：ModalDrawerSheet 加白色亮边
    width_indices = []
    for index, line in enumerate(lines):
        if line.strip() == 'modifier = Modifier.width(300.dp)':
            width_indices.append(index)
    if len(width_indices) != 1:
        print('batch74v3: dump ModalDrawerSheet area:')
        for index, line in enumerate(lines):
            if 'ModalDrawerSheet' in line or '.width(' in line:
                print('  >> line ' + str(index) + ': ' + line.strip()[:160])
        fail(CD, 'ModalDrawerSheet width anchor count=' + str(len(width_indices)))
    wi = width_indices[0]
    ind = indent_of(lines[wi])
    lines[wi:wi + 1] = [
        ind + 'modifier = Modifier',
        ind + '    .width(300.dp)',
        ind + '    .border(',
        ind + '        width = 1.dp,',
        ind + '        color = Color.White.copy(alpha = 0.2f), // ' + MARK,
        ind + '        shape = RoundedCornerShape(16.dp),',
        ind + '    )',
    ]
    applied.append('drawer-border')

    # 3. B：Settings03 唯一位置 -> 最近 Row( -> 包圆角 Surface
    settings_icons = []
    for index, line in enumerate(lines):
        if 'HugeIcons.Settings03' in line and 'Icon(' in line:
            settings_icons.append(index)
    if len(settings_icons) != 1:
        print('batch74v3: dump all Settings03 lines:')
        for index, line in enumerate(lines):
            if 'Settings03' in line:
                print('  >> line ' + str(index) + ': ' + line.strip()[:160])
        fail(CD, 'Settings03 icon count=' + str(len(settings_icons)))
    settings_idx = settings_icons[0]

    row_start = -1
    for index in range(settings_idx, max(settings_idx - 50, -1), -1):
        if lines[index].strip() == 'Row(':
            row_start = index
            break
    if row_start < 0:
        print('batch74v3: dump area around Settings03 (idx=' + str(settings_idx) + '):')
        for index in range(max(0, settings_idx - 30), min(settings_idx + 10, len(lines))):
            print('  >> line ' + str(index) + ': ' + lines[index].strip()[:160])
        fail(CD, 'Row( not found above Settings03')
    row_indent = indent_of(lines[row_start])

    lines[row_start:row_start] = [
        row_indent + 'Surface(',
        row_indent + '    shape = RoundedCornerShape(20.dp), // ' + MARK,
        row_indent + '    color = MaterialTheme.colorScheme.surfaceContainerLow,',
        row_indent + '    modifier = Modifier.fillMaxWidth(),',
        row_indent + ') {',
    ]
    settings_idx += 5

    drawer_close = -1
    for index in range(settings_idx + 1, min(settings_idx + 15, len(lines))):
        if lines[index].strip() == ')':
            drawer_close = index
            break
    if drawer_close < 0:
        fail(CD, 'DrawerAction close paren not found after Settings03')
    row_close = -1
    for index in range(drawer_close + 1, min(drawer_close + 5, len(lines))):
        if lines[index].strip() == '}':
            row_close = index
            break
    if row_close < 0:
        fail(CD, 'Row close brace not found after DrawerAction')
    lines.insert(row_close + 1, row_indent + '}')
    applied.append('bottom-rounded')

    # 4. 自检：不得残留不可用 API；import 精确行唯一；两个视觉修改均存在
    text = concat_lines(lines)
    if text.count('import androidx.compose.material3.DrawerDefaults') != 0:
        fail(CD, 'DrawerDefaults import unexpectedly remains')
    if 'DrawerDefaults.modalDrawerShape' in text:
        fail(CD, 'DrawerDefaults.modalDrawerShape unexpectedly remains')
    if text.count('import androidx.compose.foundation.border') != 1:
        fail(CD, 'border import count is not one')
    if text.count('import androidx.compose.foundation.shape.RoundedCornerShape') != 1:
        fail(CD, 'RoundedCornerShape import count is not one')
    if text.count('import androidx.compose.ui.graphics.Color') != 1:
        fail(CD, 'Color import count is not one')
    if text.count('RoundedCornerShape(16.dp)') != 1:
        fail(CD, 'drawer border shape count is not one')
    if text.count('RoundedCornerShape(20.dp)') != 1:
        fail(CD, 'bottom surface shape count is not one')
    if MARK not in text:
        fail(CD, 'marker missing after apply')
    (ROOT / CD).write_text(text, encoding='utf-8')
    print('batch74v3: OK (' + ', '.join(applied) + ')')

print('batch74v3: done')

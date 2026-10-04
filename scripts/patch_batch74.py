#!/usr/bin/env python3
'''batch74v2: 侧边栏白色亮边 + 底部设置区圆润（ChatDrawer.kt）

v1 (#200) 死因：SpaceAround anchor count=0——CI 形态下该锚点不存在。
v2 改进：SpaceAround 找不到时 dump 所有 Row( 行 + Arrangement 相关行，
同时把 B 部分改为更鲁棒的搜索：找 DrawerAction(Settings03) 的 item 块
往上找最近的 Row( ——不再依赖 SpaceAround。

A（白色亮边）：不变
B（底部圆润）：改为从 Settings03 icon 往上找 Row(
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
    print('::error file=' + path + '::batch74v2 ' + str(message)[:1400])
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
    print('batch74v2: already applied')
else:
    lines = t.split(NL)
    applied = []

    # ============================================================
    # 1. Import 清单
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
    width_indices = []
    for index, line in enumerate(lines):
        if line.strip() == 'modifier = Modifier.width(300.dp)':
            width_indices.append(index)
    if len(width_indices) != 1:
        # dump 附近 ModalDrawerSheet 行
        print('batch74v2: dump ModalDrawerSheet area:')
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
        ind + '        shape = DrawerDefaults.modalDrawerShape,',
        ind + '    )',
    ]
    applied.append('drawer-border')

    # ============================================================
    # 3. B: 底部设置区包圆角 Surface
    #    策略：找 Settings03 icon → 往上找最近的 Row( → 包 Surface
    # ============================================================
    # 先找 Settings03 icon（底部设置按钮）
    settings_icons = []
    for index, line in enumerate(lines):
        if 'HugeIcons.Settings03' in line and 'Icon(' in line:
            settings_icons.append(index)
    if len(settings_icons) < 1:
        print('batch74v2: dump all Settings03 lines:')
        for index, line in enumerate(lines):
            if 'Settings03' in line:
                print('  >> line ' + str(index) + ': ' + line.strip()[:160])
        fail(CD, 'Settings03 icon count=' + str(len(settings_icons)))

    # 用最后一个 Settings03（底部设置按钮在文件后部）
    settings_idx = settings_icons[-1]

    # 从 settings_idx 往上找最近的 Row( 行
    row_start = -1
    for index in range(settings_idx, max(settings_idx - 50, -1), -1):
        if lines[index].strip() == 'Row(':
            row_start = index
            break
    if row_start < 0:
        # dump 附近内容看结构
        print('batch74v2: dump area around Settings03 (idx=' + str(settings_idx) + '):')
        for index in range(max(0, settings_idx - 30), min(settings_idx + 10, len(lines))):
            print('  >> line ' + str(index) + ': ' + lines[index].strip()[:160])
        fail(CD, 'Row( not found above Settings03')
    row_indent = indent_of(lines[row_start])

    # 在 Row( 之前插入 Surface 开始
    lines[row_start:row_start] = [
        row_indent + 'Surface(',
        row_indent + '    shape = RoundedCornerShape(20.dp), // ' + MARK,
        row_indent + '    color = MaterialTheme.colorScheme.surfaceContainerLow,',
        row_indent + '    modifier = Modifier.fillMaxWidth(),',
        row_indent + ') {',
    ]
    # row_start 后面插了 5 行，Row( 现在在 row_start + 5
    # 找 Row 的结束：从 Settings03 往下找 DrawerAction 的 ) → 再找 }
    # 重新定位 settings_idx（因为插入了 5 行）
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
    print('batch74v2: OK (' + ', '.join(applied) + ')')

print('batch74v2: done')

#!/usr/bin/env python3
'''batch74v4: 侧边栏白色亮边 + 底部设置区圆润（ChatDrawer.kt）

#202 死因：自检 text.count('RoundedCornerShape(16.dp)') != 1
本地模拟证明写入后 count=1，但 CI 形态下可能有其他脚本已用过该 shape。
自检断言过严——不应要求全局唯一，只应确认本次写入成功。

v4 修复：删除过严的 shape count 断言，保留 MARK + import 精确检查。
MARK 是唯一字符串，已足以确认本次写入成功。

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
    print('::error file=' + path + '::batch74v4 ' + str(message)[:1400])
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
    print('batch74v4: already applied')
else:
    lines = t.split(NL)
    applied = []

    # 1. Import 清单
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

    # 删除可能残留的 DrawerDefaults import
    lines = [line for line in lines if line.strip() != 'import androidx.compose.material3.DrawerDefaults']

    # 2. A: ModalDrawerSheet 加白色亮边
    width_indices = []
    for index, line in enumerate(lines):
        if line.strip() == 'modifier = Modifier.width(300.dp)':
            width_indices.append(index)
    if len(width_indices) != 1:
        print('batch74v4: dump ModalDrawerSheet area:')
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

    # 3. B: Settings03 唯一位置 -> 最近 Row( -> 包圆角 Surface
    settings_icons = []
    for index, line in enumerate(lines):
        if 'HugeIcons.Settings03' in line and 'Icon(' in line:
            settings_icons.append(index)
    if len(settings_icons) != 1:
        print('batch74v4: dump all Settings03 lines:')
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
        print('batch74v4: dump area around Settings03 (idx=' + str(settings_idx) + '):')
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

    # 4. 自检：只检查 MARK 存在 + import 精确行 + 无残留 DrawerDefaults
    #    不检查 RoundedCornerShape 的全局 count（可能其他脚本也用过）
    text = concat_lines(lines)
    if MARK not in text:
        fail(CD, 'marker missing after apply')
    if 'DrawerDefaults' in text:
        fail(CD, 'DrawerDefaults unexpectedly remains')
    for new_imp, _ in NEW_IMPORTS:
        count = text.count(new_imp)
        if count < 1:
            fail(CD, 'import missing after apply: ' + new_imp)
    (ROOT / CD).write_text(text, encoding='utf-8')
    print('batch74v4: OK (' + ', '.join(applied) + ')')

print('batch74v4: done')

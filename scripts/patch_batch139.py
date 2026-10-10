#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch139: RP 优化 —— 导航注册 + 设置页入口

改动:
1. RouteActivity.kt:
   a. import 区加 SettingRpOptimizationsPage
   b. Screen sealed interface 加 data object SettingRpOptimizations
   c. entryProvider 加 entry<Screen.SettingRpOptimizations>
2. SettingPreferencesUIPage.kt:
   a. import 区加 Screen / LocalNavController / ArrowRight01
   b. 函数体加 val navController = LocalNavController.current
   c. 在"代码显示设置" CardGroup 前加入口 CardGroup(点击导航到 RP 优化页)

新文件 SettingRpOptimizationsPage.kt 由仓库直接提交(不经 patch)。

五查:
1. import 清单: RouteActivity 加 SettingRpOptimizationsPage import;
   SettingPreferencesUIPage 加 Screen/LocalNavController/ArrowRight01(精确行匹配)
2. 同文件冲突: RouteActivity 无在链 patch 碰过 Screen/entryProvider 区;
   SettingPreferencesUIPage 无在链 patch 碰过
3. 作用域: navController 在函数体顶层;entry 在 entryProvider lambda 内
4. 括号配对: 所有插入块自平衡;全文配平校验
5. 函数签名: 不改

Python 三查: 引号=chr构造(DQ) / NL 手写 concat / 无 f-string/walrus/join / fail-loud
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
DQ = chr(34)
MARK = 'rhRpOpt139'

RA = 'app/src/main/java/me/rerere/rikkahub/RouteActivity.kt'
SP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPreferencesUIPage.kt'


def fail(path, msg, lines=None, around=-1):
    body = 'batch139 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 2)
        hi = min(len(lines), around + 3)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:80] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + path + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


def concat_lines(lines):
    text = ''
    first = True
    for line in lines:
        if not first:
            text += NL
        text += line
        first = False
    return text


def indent_of(line):
    return line[:len(line) - len(line.lstrip())]


def find_unique(lines, needle, label, path):
    hits = []
    for i, ln in enumerate(lines):
        if ln.strip() == needle:
            hits.append(i)
    if len(hits) != 1:
        fail(path, label + ' count=' + str(len(hits)), lines, hits[0] if hits else 0)
    return hits[0]


def find_unique_prefix(lines, prefix, label, path):
    hits = []
    for i, ln in enumerate(lines):
        if ln.strip().startswith(prefix):
            hits.append(i)
    if len(hits) != 1:
        fail(path, label + ' count=' + str(len(hits)), lines, hits[0] if hits else 0)
    return hits[0]


# ============================================================
# 1. RouteActivity.kt
# ============================================================
ra_path = ROOT / RA
ra_text = ra_path.read_text(encoding='utf-8')
if MARK in ra_text:
    print('batch139: RouteActivity already applied')
else:
    lines = ra_text.split(NL)
    applied = []

    # 1a. import 区加 SettingRpOptimizationsPage
    ii = find_unique(lines, 'import me.rerere.rikkahub.ui.pages.setting.SettingPreferencesUIPage', 'SettingPreferencesUIPage import', RA)
    lines.insert(ii + 1, 'import me.rerere.rikkahub.ui.pages.setting.SettingRpOptimizationsPage // ' + MARK)
    applied.append('import')

    # 1b. Screen 定义加 data object SettingRpOptimizations
    si = find_unique(lines, 'data object SettingPreferencesUI : Screen', 'Screen.SettingPreferencesUI', RA)
    sind = indent_of(lines[si])
    lines.insert(si + 1, sind + '@Serializable')
    lines.insert(si + 2, sind + 'data object SettingRpOptimizations : Screen // ' + MARK)
    applied.append('screen')

    # 1c. entryProvider 加 entry
    # 锚点: entry<Screen.SettingPreferencesUI> { 行
    ei = find_unique_prefix(lines, 'entry<Screen.SettingPreferencesUI>', 'entry<SettingPreferencesUI>', RA)
    eind = indent_of(lines[ei])
    # 找这个 entry 块的闭合 } (strip == '}', 缩进同 entry 行)
    close_idx = -1
    for i in range(ei + 1, len(lines)):
        if lines[i].strip() == '}' and indent_of(lines[i]) == eind:
            close_idx = i
            break
    if close_idx < 0:
        fail(RA, 'entry<SettingPreferencesUI> closing brace not found', lines, ei)
    entry_lines = [
        eind + 'entry<Screen.SettingRpOptimizations> { // ' + MARK,
        eind + '    SettingRpOptimizationsPage()',
        eind + '}',
    ]
    for j, b in enumerate(entry_lines):
        lines.insert(close_idx + 1 + j, b)
    applied.append('entry')

    out = concat_lines(lines)
    for need in [
        'import me.rerere.rikkahub.ui.pages.setting.SettingRpOptimizationsPage',
        'data object SettingRpOptimizations : Screen',
        'entry<Screen.SettingRpOptimizations> {',
        'SettingRpOptimizationsPage()',
    ]:
        if need not in out:
            fail(RA, 'selfcheck missing: ' + need, lines, 0)
    if MARK not in out:
        fail(RA, 'marker missing', lines, 0)
    if (ra_text.count('(') - ra_text.count(')')) != (out.count('(') - out.count(')')):
        fail(RA, 'paren balance changed', lines, 0)
    if (ra_text.count('{') - ra_text.count('}')) != (out.count('{') - out.count('}')):
        fail(RA, 'brace balance changed', lines, 0)
    ra_path.write_text(out, encoding='utf-8')
    print('batch139: RouteActivity OK (' + ', '.join(applied) + ')')

# ============================================================
# 2. SettingPreferencesUIPage.kt
# ============================================================
sp_path = ROOT / SP
sp_text = sp_path.read_text(encoding='utf-8')
if MARK in sp_text:
    print('batch139: SettingPreferencesUIPage already applied')
else:
    lines = sp_text.split(NL)
    applied = []

    # 2a. import: Screen
    ii = find_unique(lines, 'import me.rerere.rikkahub.data.datastore.DisplaySetting', 'DisplaySetting import', SP)
    lines.insert(ii, 'import me.rerere.rikkahub.Screen // ' + MARK)
    applied.append('import_screen')

    # 2b. import: LocalNavController
    ii2 = find_unique(lines, 'import me.rerere.rikkahub.ui.context.LocalToaster', 'LocalToaster import', SP)
    lines.insert(ii2, 'import me.rerere.rikkahub.ui.context.LocalNavController // ' + MARK)
    applied.append('import_nav')

    # 2c. import: ArrowRight01
    ii3 = find_unique(lines, 'import me.rerere.hugeicons.stroke.Delete02', 'Delete02 import', SP)
    lines.insert(ii3 + 1, 'import me.rerere.hugeicons.stroke.ArrowRight01 // ' + MARK)
    applied.append('import_icon')

    # 2d. 函数体加 navController
    # 锚点: val toaster = LocalToaster.current
    ti = find_unique(lines, 'val toaster = LocalToaster.current', 'toaster', SP)
    tind = indent_of(lines[ti])
    lines.insert(ti + 1, tind + 'val navController = LocalNavController.current // ' + MARK)
    applied.append('navcontroller')

    # 2e. 在"代码显示设置" CardGroup 前加入口 CardGroup
    # 锚点: title = { Text(stringResource(R.string.setting_page_code_display_settings)) },
    ci = find_unique(lines, 'title = { Text(stringResource(R.string.setting_page_code_display_settings)) },', 'code display title', SP)
    cind = indent_of(lines[ci])
    # 向上找 item { 行 (这个 CardGroup 的容器 item)
    item_idx = -1
    for i in range(ci, max(0, ci - 5), -1):
        if lines[i].strip() == 'item {':
            item_idx = i
            break
    if item_idx < 0:
        fail(SP, 'item { above code display not found', lines, ci)
    item_ind = indent_of(lines[item_idx])
    entry_lines = [
        item_ind + 'item { // ' + MARK,
        item_ind + '    CardGroup(',
        item_ind + '        modifier = Modifier.padding(horizontal = 8.dp),',
        item_ind + '        title = { Text(' + DQ + '文本样式' + DQ + ') },',
        item_ind + '    ) {',
        item_ind + '        item(',
        item_ind + '            onClick = { navController.navigate(Screen.SettingRpOptimizations) },',
        item_ind + '            headlineContent = { Text(' + DQ + 'RP 优化' + DQ + ') },',
        item_ind + '            supportingContent = { Text(' + DQ + '自定义 Markdown 文本颜色' + DQ + ') },',
        item_ind + '            trailingContent = {',
        item_ind + '                Icon(HugeIcons.ArrowRight01, contentDescription = null)',
        item_ind + '            },',
        item_ind + '        )',
        item_ind + '    }',
        item_ind + '}',
    ]
    for j, b in enumerate(entry_lines):
        lines.insert(item_idx + j, b)
    applied.append('entry')

    out = concat_lines(lines)
    for need in [
        'import me.rerere.rikkahub.Screen',
        'import me.rerere.rikkahub.ui.context.LocalNavController',
        'import me.rerere.hugeicons.stroke.ArrowRight01',
        'val navController = LocalNavController.current',
        'Screen.SettingRpOptimizations',
        'HugeIcons.ArrowRight01',
    ]:
        if need not in out:
            fail(SP, 'selfcheck missing: ' + need, lines, 0)
    if MARK not in out:
        fail(SP, 'marker missing', lines, 0)
    if (sp_text.count('(') - sp_text.count(')')) != (out.count('(') - out.count(')')):
        fail(SP, 'paren balance changed', lines, 0)
    if (sp_text.count('{') - sp_text.count('}')) != (out.count('{') - out.count('}')):
        fail(SP, 'brace balance changed', lines, 0)
    sp_path.write_text(out, encoding='utf-8')
    print('batch139: SettingPreferencesUIPage OK (' + ', '.join(applied) + ')')

print('batch139: ALL OK')

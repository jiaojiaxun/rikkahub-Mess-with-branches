#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch136 v2: 酒馆模式开关从标题下移到面板底部(分割线隔开)

v1 死因: selfcheck `out.find('HorizontalDivider')` 找到的是 import 行(文件顶部,
idx_hd=2073),而不是实际调用位置——idx_hd < idx_sl(8153) 被误判为"divider 不在 slider 后"。

v2 修法: `out.find('HorizontalDivider(')` 带左括号,不匹配 import 行。
同时修正 'in out is False' 哑弹为 'not in out'(语义等价,更清晰)。

其余逻辑不变(删除原开关块 + Slider 后插分割线+开关 + 补 import)。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhTavernMove'
OLD_MARK = 'rhTavernMode'
RP = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ReasoningPicker.kt'


def warn(msg):
    print('::warning file=' + RP + '::batch136 ' + str(msg))


def fail(msg):
    print('::error file=' + RP + '::batch136 ' + str(msg))
    sys.stdout.flush()
    sys.exit(1)


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


t = (ROOT / RP).read_text(encoding='utf-8')
if MARK in t:
    print('batch136: already applied')
    sys.exit(0)

if '// ' + OLD_MARK + ': 会话级酒馆模式开关' not in t:
    warn('old tavern switch block marker not found (batch130 not applied?); skip')
    sys.exit(0)

bal0 = balance(t)
lines = t.split(NL)

# ---- 1. 定位原开关块(注释行 → if 块配平结束) ----
mark_i = -1
for i, ln in enumerate(lines):
    if '// ' + OLD_MARK + ': 会话级酒馆模式开关' in ln:
        mark_i = i
        break
if mark_i < 0:
    warn('marker line not found; skip')
    sys.exit(0)

if_i = -1
for j in range(mark_i, min(mark_i + 5, len(lines))):
    if 'if (onUpdateTavernMode != null) {' in lines[j]:
        if_i = j
        break
if if_i < 0:
    warn('if-block after marker not found; skip')
    sys.exit(0)

depth = 0
end_i = -1
for j in range(if_i, min(if_i + 40, len(lines))):
    depth += lines[j].count('{') - lines[j].count('}')
    if depth == 0 and j > if_i:
        end_i = j
        break
if end_i < 0:
    warn('if-block closing brace not found; skip')
    sys.exit(0)

block_start = mark_i
if block_start > 0 and lines[block_start - 1].strip() == '':
    block_start -= 1

# ---- 2. 定位 Slider 块结束(混配平扫描) ----
sl_i = -1
for i, ln in enumerate(lines):
    if ln.strip() == 'Slider(':
        sl_i = i
        break
if sl_i < 0:
    warn('Slider( line not found; skip')
    sys.exit(0)

depth = 0
slider_end = -1
for j in range(sl_i, min(sl_i + 70, len(lines))):
    depth += (lines[j].count('(') - lines[j].count(')')) + (lines[j].count('{') - lines[j].count('}'))
    if depth == 0 and j > sl_i:
        slider_end = j
        break
if slider_end < 0:
    warn('Slider block closing not found; skip')
    sys.exit(0)

if not (end_i < slider_end):
    warn('unexpected order block_end=' + str(end_i) + ' slider_end=' + str(slider_end) + '; skip')
    sys.exit(0)

# ---- 3. 先插入(面板底部) ----
d = '            '
new_block = [
    '',
    d + '// ' + MARK + ': 会话级酒馆模式开关——移到面板底部,与思考深度用分割线隔开',
    d + 'if (onUpdateTavernMode != null) {',
    d + '    HorizontalDivider(modifier = Modifier.fillMaxWidth())',
    d + '    Row(',
    d + '        modifier = Modifier.fillMaxWidth(),',
    d + '        verticalAlignment = Alignment.CenterVertically,',
    d + '        horizontalArrangement = Arrangement.SpaceBetween,',
    d + '    ) {',
    d + '        Column(modifier = Modifier.weight(1f)) {',
    d + '            Text(',
    d + '                text = stringResource(R.string.setting_tavern_mode),',
    d + '                style = MaterialTheme.typography.titleSmall,',
    d + '            )',
    d + '            Text(',
    d + '                text = stringResource(R.string.setting_tavern_mode_desc),',
    d + '                style = MaterialTheme.typography.bodySmall,',
    d + '                color = MaterialTheme.colorScheme.onSurfaceVariant,',
    d + '            )',
    d + '        }',
    d + '        Switch(',
    d + '            checked = tavernMode,',
    d + '            onCheckedChange = { onUpdateTavernMode?.invoke(it) },',
    d + '        )',
    d + '    }',
    d + '}',
]
lines = lines[:slider_end + 1] + new_block + lines[slider_end + 1:]

# ---- 4. 再删除(原位置;删除区在插入区之前,坐标不受插入影响) ----
lines = lines[:block_start] + lines[end_i + 1:]

# ---- 5. 补 import ----
out = NL.join(lines)
if 'import androidx.compose.material3.HorizontalDivider' not in out:
    lines = out.split(NL)
    ip = -1
    for i, ln in enumerate(lines):
        if ln.strip() == 'import androidx.compose.material3.Icon':
            ip = i
            break
    if ip < 0:
        warn('Icon import anchor not found; skip import (really weird); proceeding')
    else:
        lines.insert(ip + 1, 'import androidx.compose.material3.HorizontalDivider')
        out = NL.join(lines)

# ---- 6. 自检 ----
if 'HorizontalDivider' not in out:
    fail('selfcheck: HorizontalDivider missing')
if out.count('if (onUpdateTavernMode != null) {') != 1:
    fail('selfcheck: switch block count=' + str(out.count('if (onUpdateTavernMode != null) {')) + ' (expected 1)')
if '// ' + OLD_MARK + ': 会话级酒馆模式开关' in out:
    fail('selfcheck: old block comment still present')
if '// ' + MARK not in out:
    fail('selfcheck: new marker missing')
idx_hd = out.find('HorizontalDivider(')
idx_sl = out.find('SliderDefaults.Track')
if idx_sl < 0 or idx_hd < idx_sl:
    fail('selfcheck: divider not after slider (idx_hd=' + str(idx_hd) + ' idx_sl=' + str(idx_sl) + ')')
if balance(out) != bal0:
    fail('selfcheck: balance ' + str(bal0) + ' -> ' + str(balance(out)))

(ROOT / RP).write_text(out, encoding='utf-8')
print('::notice::batch136v2 OK - tavern switch moved below slider with divider')

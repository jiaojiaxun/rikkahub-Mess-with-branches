#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch136: 酒馆模式开关从标题下移到面板底部(分割线隔开)

用户反馈(#7): "酒馆模式开关要移到分割线下面"
当前(batch130 后): 标题 Column → [酒馆开关] → 等级图标 → Slider
目标: 标题 Column → 等级图标 → Slider → [分割线] → [酒馆开关]

改动(单文件 ReasoningPicker.kt):
1. 删除 batch130 在原位置(标题 Column 后)插入的开关块(marker rhTavernMode 注释定位)。
2. 在 Slider 块之后(面板底部)插入: HorizontalDivider + 开关块(marker rhTavernMove)。
3. 补 import androidx.compose.material3.HorizontalDivider。

安全设计:
- 全部锚点先找齐再执行;任一找不到 → ::warning + skip(不阻塞构建,一次 run 拿 dump)。
- 先插入(较后位置)再删除(较前位置),行号漂移安全(删除区在插入区之前)。
- 开关块自平衡,全文件 balance 前后一致。

五查:
1. import 清单: HorizontalDivider 新增(精确行匹配);其余符号(Row/Column/Arrangement/
   Alignment/Modifier/fillMaxWidth/Switch/MaterialTheme/Text/stringResource)均为
   batch130 后已有(batch130 已引入 Switch 且三查通过)。
2. 同文件冲突: ReasoningPicker.kt 在链 patch 只有 batch130 触碰(已实读其 D5 插入块),
   本批锚点即 batch130 的产物注释;无其他 patch 记录。
3. 作用域: 插入点在 ModalBottomSheet 内容 Column 内(与 Slider 同级);
   tavernMode/onUpdateTavernMode 是 ReasoningPicker 参数,可见。
4. 括号配对: 删除块自平衡(130 已证),插入块自平衡,H 行净变化=新增 import 单行=0。
5. 函数签名: 零改动。

Python 三查: 引号用 Q=chr(34) 构造;无 f-string;helper 先定义;失败显式 warn+skip 或 exit(1)。
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

# 删除区必须在插入区之前(从上到下: 开关块 → Slider),用于行号漂移安全断言
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
if '// ' + MARK in out is False:
    fail('selfcheck: new marker missing')
idx_hd = out.find('HorizontalDivider')
idx_sl = out.find('SliderDefaults.Track')
if idx_sl < 0 or idx_hd < idx_sl:
    fail('selfcheck: divider not after slider (idx_hd=' + str(idx_hd) + ' idx_sl=' + str(idx_sl) + ')')
if balance(out) != bal0:
    fail('selfcheck: balance ' + str(bal0) + ' -> ' + str(balance(out)))

(ROOT / RP).write_text(out, encoding='utf-8')
print('::notice::batch136 OK - tavern switch moved below slider with divider')

# 附注: 本脚本不阻塞——所有找不到分支均 warn+skip(exit 0)

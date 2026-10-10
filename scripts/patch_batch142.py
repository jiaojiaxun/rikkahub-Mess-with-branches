#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch142 v2: 附件放大——AI 工作区产物文件也改大卡片(对齐 batch120 用户消息附件样式)

v1 死因: balance changed 0 -> -2。两个 bug:
1. find_block_end 只数 {/} 不数 (/) —— Surface( 行 depth=0,下一行就误判结束
2. FlowRow→Column 时没删 horizontalArrangement 参数 —— Column 不接受此参数,会编译错误

v2 修法:
1. find_block_end 同时数 ( { ) } 四种括号(混合配平),depth 从 1 开始(Surface( 的 ( )
2. FlowRow→Column 时同时删除 horizontalArrangement 行

其余逻辑不变(大卡片样式对齐 batch120,onClick 行为不变)。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhAttachCardWorkspace'
EF = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageEditedFiles.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch142v2 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + EF + '::' + body[:1400])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


def find_block_end(lines, start):
    '''v2: 混合配平——同时数 ( { ) } 四种括号'''
    depth = 0
    for i in range(start, len(lines)):
        for ch in lines[i]:
            if ch in '({':
                depth += 1
            elif ch in ')}':
                depth -= 1
        if depth <= 0 and i > start:
            return i
    return -1


t = (ROOT / EF).read_text(encoding='utf-8')
if MARK in t:
    print('batch142v2: already applied')
    sys.exit(0)

bal0 = balance(t)
lines = t.split(NL)
applied = []

# ---- 1. imports ----
imp_hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('import ')]
if not imp_hits:
    fail('no import lines')
last_imp = imp_hits[-1]
need = [
    'import androidx.compose.foundation.layout.fillMaxSize',
    'import androidx.compose.foundation.shape.CircleShape',
    'import me.rerere.hugeicons.stroke.Download01',
]
existing = set(ln.strip() for ln in lines)
missing = [x for x in need if x not in existing]
for j, imp in enumerate(missing):
    lines.insert(last_imp + 1 + j, imp + ' // ' + MARK)
if missing:
    applied.append('imports+' + str(len(missing)))

# ---- 2. FlowRow → Column + 删 horizontalArrangement ----
fr_hits = [i for i, ln in enumerate(lines) if ln.strip() == 'FlowRow(']
if len(fr_hits) != 1:
    fail('FlowRow anchor count=' + str(len(fr_hits)), lines, fr_hits[0] if fr_hits else 0)
fr_i = fr_hits[0]
d = ind(lines[fr_i])
lines[fr_i] = d + 'Column(  // ' + MARK + ': 大卡片需要纵向排列,不再 FlowRow 横排'
# v2: 删除 horizontalArrangement 行(Column 不接受此参数)
ha_hits = [i for i, ln in enumerate(lines) if 'horizontalArrangement = Arrangement.spacedBy(6.dp)' in ln]
if len(ha_hits) == 1:
    del lines[ha_hits[0]]
    applied.append('flowrow-to-column+rm-harr')
else:
    # 找不到就只改 FlowRow→Column,不删 horizontalArrangement(可能已被删或格式不同)
    applied.append('flowrow-to-column')

# ---- 3. 文件 Surface → 大卡片 ----
surf_hits = [i for i, ln in enumerate(lines) if 'onClick = { selectedPath = path }' in ln]
if len(surf_hits) != 1:
    fail('file Surface anchor count=' + str(len(surf_hits)), lines, surf_hits[0] if surf_hits else 0)
si = surf_hits[0]
surf_start = -1
for j in range(si, max(0, si - 3), -1):
    if lines[j].strip() == 'Surface(':
        surf_start = j
        break
if surf_start < 0:
    fail('Surface( start not found above onClick', lines, si)
d = ind(lines[surf_start])
surf_end = find_block_end(lines, surf_start)
if surf_end < 0:
    fail('Surface block end not found', lines, surf_start)

new_card = [
    d + 'Surface(  // ' + MARK + ': 大卡片样式(对齐 batch120 用户消息附件)',
    d + '    onClick = { selectedPath = path },',
    d + '    modifier = Modifier.fillMaxWidth(),',
    d + '    shape = RoundedCornerShape(16.dp),',
    d + '    color = MaterialTheme.colorScheme.surfaceContainerHigh,',
    d + '    tonalElevation = 2.dp,',
    d + ') {',
    d + '    Row(',
    d + '        modifier = Modifier.padding(12.dp),',
    d + '        verticalAlignment = Alignment.CenterVertically,',
    d + '        horizontalArrangement = Arrangement.spacedBy(12.dp),',
    d + '    ) {',
    d + '        Surface(',
    d + '            modifier = Modifier.size(44.dp),',
    d + '            shape = RoundedCornerShape(12.dp),',
    d + '            color = MaterialTheme.colorScheme.surfaceContainerHigh,',
    d + '        ) {',
    d + '            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {',
    d + '                Icon(',
    d + '                    imageVector = HugeIcons.File02,',
    d + '                    contentDescription = null,',
    d + '                    modifier = Modifier.size(24.dp),',
    d + '                )',
    d + '            }',
    d + '        }',
    d + '        Column(modifier = Modifier.weight(1f)) {',
    d + '            Text(',
    d + '                text = fileName,',
    d + '                maxLines = 1,',
    d + '                overflow = TextOverflow.Ellipsis,',
    d + '                style = MaterialTheme.typography.titleSmall,',
    d + '            )',
    d + '            Text(',
    d + '                text = ' + Q + '工作区文件' + Q + ',',
    d + '                maxLines = 1,',
    d + '                overflow = TextOverflow.Ellipsis,',
    d + '                style = MaterialTheme.typography.labelSmall,',
    d + '                color = MaterialTheme.colorScheme.onSurfaceVariant,',
    d + '            )',
    d + '        }',
    d + '        Surface(',
    d + '            modifier = Modifier.size(36.dp),',
    d + '            shape = CircleShape,',
    d + '            color = MaterialTheme.colorScheme.surfaceContainerHigh,',
    d + '        ) {',
    d + '            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {',
    d + '                Icon(',
    d + '                    imageVector = HugeIcons.Download01,',
    d + '                    contentDescription = null,',
    d + '                    modifier = Modifier.size(20.dp),',
    d + '                    tint = MaterialTheme.colorScheme.onSurfaceVariant,',
    d + '                )',
    d + '            }',
    d + '        }',
    d + '    }',
    d + '}',
]
lines[surf_start:surf_end + 1] = new_card
applied.append('file-card')

# ---- 4. "+N" 展开按钮同步改大卡片 ----
exp_hits = [i for i, ln in enumerate(lines) if 'onClick = { expanded = true }' in ln]
if len(exp_hits) != 1:
    fail('expand Surface anchor count=' + str(len(exp_hits)), lines, exp_hits[0] if exp_hits else 0)
ei = exp_hits[0]
exp_start = -1
for j in range(ei, max(0, ei - 3), -1):
    if lines[j].strip() == 'Surface(':
        exp_start = j
        break
if exp_start < 0:
    fail('expand Surface start not found', lines, ei)
d = ind(lines[exp_start])
exp_end = find_block_end(lines, exp_start)
if exp_end < 0:
    fail('expand Surface block end not found', lines, exp_start)
new_exp = [
    d + 'Surface(  // ' + MARK,
    d + '    onClick = { expanded = true },',
    d + '    modifier = Modifier.fillMaxWidth(),',
    d + '    shape = RoundedCornerShape(16.dp),',
    d + '    color = MaterialTheme.colorScheme.surfaceContainerHigh,',
    d + ') {',
    d + '    Row(',
    d + '        modifier = Modifier.padding(12.dp),',
    d + '        verticalAlignment = Alignment.CenterVertically,',
    d + '        horizontalArrangement = Arrangement.Center,',
    d + '    ) {',
    d + '        Text(',
    d + '            text = ' + Q + '+' + Q + ' + (editedFiles.size - DEFAULT_VISIBLE_COUNT).toString() + ' + Q + ' 更多' + Q + ',',
    d + '            style = MaterialTheme.typography.labelMedium,',
    d + '            color = MaterialTheme.colorScheme.onSurfaceVariant,',
    d + '        )',
    d + '    }',
    d + '}',
]
lines[exp_start:exp_end + 1] = new_exp
applied.append('expand-card')

# ---- 5. 自检 ----
out = NL.join(lines)
for need in [MARK, 'fillMaxSize', 'Download01', 'CircleShape', 'Column(']:
    if need not in out:
        fail('selfcheck missing: ' + need)
if 'FlowRow(' in out and MARK + ': 大卡片需要纵向排列' not in out:
    fail('FlowRow still present without comment')
if balance(out) != bal0:
    fail('balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

(ROOT / EF).write_text(out, encoding='utf-8')
print('::notice::batch142v2 OK - ' + ', '.join(applied))

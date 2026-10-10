#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch142 v2: 附件放大——AI 工作区产物文件也改大卡片(对齐 batch120 用户消息附件样式)

v2 修复: find_block_end 只数花括号不数圆括号, 在 'onClick = { selectedPath = path },'
这种同行开关花括号的行 depth 归 0 误停 → 原 Surface 块被截断只删 2 行,
新块 44 行插进去后括号配不平(balance 0 -> -2)。
v2 改法: find_block_end 改为混合扫描圆括号+花括号(Surface(...) { ... } 的结构:
参数圆括号先开,lambda 花括号后开,先关参数后关 lambda,混合 depth 正确配平)。

v1 功能不变: 附件放大——AI 工作区产物文件也改大卡片(对齐 batch120 用户消息附件样式)

用户反馈(#2): "附件放大只对用户消息生效,AI生成产物的附件仍是旧样式"

根因: batch120v2 把 ChatMessage.kt 的 Document/Audio 分支改成了大卡片(fillMaxWidth+
RoundedCornerShape(16)+图标+名字+大小+下载钮),但 AI 工作区产物渲染在
EditedFilesList(ChatMessageEditedFiles.kt)里——还是 FlowRow 小圆片(RoundedCornerShape(50)
+ 小图标+小文字),没被升级。

改动(ChatMessageEditedFiles.kt 单文件):
1. FlowRow → Column(spacedBy 8dp)——大卡片需要纵向排列
2. 每个文件的 Surface 从 RoundedCornerShape(50) 小圆片改为 fillMaxWidth 大卡片
   (RoundedCornerShape(16)+图标44dp+名字+说明+下载钮36dp,对齐 batch120 样式)
3. "+N" 展开按钮同步改大卡片
4. onClick 行为不变(仍打开 ModalBottomSheet 显示导出/删除)

五查:
1. import 清单: 需新增 fillMaxSize/CircleShape/Download01(精确行匹配);
   Surface/Row/Column/Icon/Text/Modifier 等已有
2. 同文件冲突: ChatMessageEditedFiles.kt 无在链 patch 触碰(list_commits 仅初始快照)
3. 作用域: 全部在 EditedFilesList 函数体内;fileName/selectedPath 已有
4. 括号配对: 替换块自平衡;全文件 balance 前后一致;find_block_end 混合扫描
5. 函数签名: 不改

Python 三查: 引号 Q=chr(34) 构造;NL 手写 concat;helper 先定义;失败显式 exit(1)
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhAttachCardWorkspace'
EF = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageEditedFiles.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch142 ' + str(msg)
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
    # v2: 混合扫描圆括号+花括号(原只数花括号, 会在 'onClick = { ... },' 行 depth 归 0 误停)
    # Surface(...) { ... } 的结构: 参数圆括号先开,lambda 花括号后开,先关参数后关 lambda
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
    print('batch142: already applied')
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

# ---- 2. FlowRow → Column ----
fr_hits = [i for i, ln in enumerate(lines) if ln.strip() == 'FlowRow(']
if len(fr_hits) != 1:
    fail('FlowRow anchor count=' + str(len(fr_hits)), lines, fr_hits[0] if fr_hits else 0)
fr_i = fr_hits[0]
d = ind(lines[fr_i])
lines[fr_i] = d + 'Column(  // ' + MARK + ': 大卡片需要纵向排列,不再 FlowRow 横排'
applied.append('flowrow-to-column')

# ---- 3. 文件 Surface → 大卡片 ----
# 锚点: Surface( onClick = { selectedPath = path } 行(文件条目)
surf_hits = [i for i, ln in enumerate(lines) if 'onClick = { selectedPath = path }' in ln]
if len(surf_hits) != 1:
    fail('file Surface anchor count=' + str(len(surf_hits)), lines, surf_hits[0] if surf_hits else 0)
si = surf_hits[0]
# 往上找 Surface( 开始行
surf_start = -1
for j in range(si, max(0, si - 3), -1):
    if lines[j].strip() == 'Surface(':
        surf_start = j
        break
if surf_start < 0:
    fail('Surface( start not found above onClick', lines, si)
d = ind(lines[surf_start])
# 找 Surface 块配平结束
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
# 锚点: Surface( onClick = { expanded = true } 行
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
print('::notice::batch142 v2 OK - ' + ', '.join(applied))

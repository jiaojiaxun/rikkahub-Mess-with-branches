#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch136: 折叠条恢复原地展开(回滚 batch76 的弹窗点击)

用户反馈: 工具调用折叠条点击后弹窗,不像原版那样原地展开,要求改回去。

根因: batch76 把折叠条 onClick 从
    .clickable { userExpanded = !expanded }
  改成
    .clickable { if (onShowSummary != null) onShowSummary() else userExpanded = !expanded }
  导致点击折叠条时优先打开 ModalBottomSheet 弹窗,不再原地展开。

修复: 恢复为原地展开。onShowSummary 参数保留(有默认值 null,不碍事),
弹窗代码(batch76/88)保留为死代码,以后想恢复弹窗只需改回这一行。

只改 1 个文件 1 行,最小改动。

五查:
1. import 清单: 不新增 import,不改 import 区
2. 同文件冲突: ChainOfThought.kt 被 batch76 碰过(onShowSummary 参数+onClick);
   本脚本只改 onClick 那一行,与 batch76 的参数行不重叠
3. 作用域: onClick 在 ChainOfThought 函数体内的折叠条 Row 内
4. 括号配对: 替换前后括号配平不变(同一行内替换)
5. 函数签名: 不改

Python 三查: 无引号字面量 / 无 f-string/walrus/join / fail-loud
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhBatch136'

COT = 'app/src/main/java/me/rerere/rikkahub/ui/components/ui/ChainOfThought.kt'


def fail(path, msg, lines=None, around=-1):
    body = 'batch136 ' + str(msg)
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


cot_path = ROOT / COT
text = cot_path.read_text(encoding='utf-8')
if MARK in text:
    print('batch136: ChainOfThought already applied')
else:
    lines = text.split(NL)

    # 找 batch76 注入的弹窗点击行
    old_click = '.clickable { if (onShowSummary != null) onShowSummary() else userExpanded = !expanded }'
    hits = []
    for i, ln in enumerate(lines):
        if ln.strip().startswith(old_click):
            hits.append(i)
    if len(hits) != 1:
        fail(COT, 'onClick anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)

    idx = hits[0]
    ind = lines[idx][:len(lines[idx]) - len(lines[idx].lstrip())]
    lines[idx] = ind + '.clickable { userExpanded = !expanded } // ' + MARK + ': 恢复原地展开'

    out = concat_lines(lines)
    # 自检: 弹窗点击逻辑已移除,原地展开已恢复
    if 'onShowSummary() else' in out:
        fail(COT, 'onShowSummary onclick still present', lines, idx)
    if 'userExpanded = !expanded' not in out:
        fail(COT, 'userExpanded toggle missing', lines, idx)
    if MARK not in out:
        fail(COT, 'marker missing', lines, idx)
    # 括号配平不变(同一行内替换)
    if (text.count('(') - text.count(')')) != (out.count('(') - out.count(')')):
        fail(COT, 'paren balance changed', lines, idx)
    if (text.count('{') - text.count('}')) != (out.count('{') - out.count('}')):
        fail(COT, 'brace balance changed', lines, idx)
    cot_path.write_text(out, encoding='utf-8')
    print('batch136: ChainOfThought OK')

print('batch136: ALL OK')

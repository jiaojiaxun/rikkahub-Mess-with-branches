#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch145: 工具+思考折叠成一行扁长条

用户反馈(#11): "工具调用+思考全部折叠到一起(长方形扁长,只能一行文字作折叠标题)"

改动(ChatMessage.kt 单文件): ChainOfThought 调用加 collapsedVisibleCount = 0
——折叠时不显示任何步骤,只显示一行控制条。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhCollapseZero'
CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch145 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + CM + '::' + body[:1400])
    sys.stdout.flush()
    sys.exit(1)


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


t = (ROOT / CM).read_text(encoding='utf-8')
if MARK in t:
    print('batch145: already applied')
    sys.exit(0)

bal0 = balance(t)
lines = t.split(NL)

hits = [i for i, ln in enumerate(lines) if ln.strip() == 'steps = block.steps,']
if len(hits) != 1:
    fail('steps anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
si = hits[0]
d = lines[si][:len(lines[si]) - len(lines[si].lstrip())]

lines.insert(si + 1, d + 'collapsedVisibleCount = 0, // ' + MARK + ': 折叠时只显示一行控制条')

out = NL.join(lines)
if MARK not in out:
    fail('marker missing')
if 'collapsedVisibleCount = 0' not in out:
    fail('collapsedVisibleCount missing')
if balance(out) != bal0:
    fail('balance changed')

(ROOT / CM).write_text(out, encoding='utf-8')
print('::notice::batch145 OK - collapsedVisibleCount = 0')

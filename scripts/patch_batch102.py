#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch102: UI fold bar semantic summary

Replace 'show X more steps' with 'operated 3 files · called MCP · generated image'.

A. ChainOfThought.kt: add collapsedLabel: String? = null param, fold text = collapsedLabel ?: original
B. ChatMessage.kt: pass collapsedLabel = ToolSummaryMapper.summarize(block.steps) at call site

Five checks:
1. import: zero new (collapsedLabel is String; ToolSummaryMapper same package, no import)
2. conflict: CO touched by batch67/76 but anchors (forceExpanded param line + show_more_steps string line) not in their regions; CM touched by batch88 but steps=block.steps line not in its region
3. scope: function param / when block
4. brackets: comma-separated additions
5. signature: add param only
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhSemanticSummary'
CO = 'app/src/main/java/me/rerere/rikkahub/ui/components/ui/ChainOfThought.kt'
CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch102 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + CO + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


# A. ChainOfThought.kt
t = (ROOT / CO).read_text(encoding='utf-8')
if MARK in t:
    print('batch102: CO already applied')
else:
    lines = t.split(NL)
    applied = []

    # A1. add param after forceExpanded
    PARAM_ANCHOR = 'forceExpanded: Boolean = false,'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == PARAM_ANCHOR]
    if len(hits) != 1:
        fail('forceExpanded param anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    pi = hits[0]
    d = ind(lines[pi])
    lines.insert(pi + 1, d + 'collapsedLabel: String? = null, // ' + MARK)
    applied.append('param')

    # A2. prepend collapsedLabel ?: before stringResource(show_more_steps)
    sm_hits = [i for i, ln in enumerate(lines) if 'chain_of_thought_show_more_steps' in ln]
    if len(sm_hits) != 1:
        fail('show_more_steps string count=' + str(len(sm_hits)), lines, sm_hits[0] if sm_hits else 0)
    sr_start = -1
    for j in range(sm_hits[0], max(sm_hits[0] - 5, -1), -1):
        if 'stringResource(' in lines[j]:
            sr_start = j
            break
    if sr_start < 0:
        fail('stringResource start not found above show_more_steps', lines, sm_hits[0])
    d = ind(lines[sr_start])
    old_line = lines[sr_start]
    lines[sr_start] = d + 'collapsedLabel ?: ' + old_line.strip() + '  // ' + MARK
    applied.append('label')

    out = NL.join(lines)
    for need in [MARK, 'collapsedLabel']:
        if need not in out:
            fail('CO selfcheck missing: ' + need)

    (ROOT / CO).write_text(out, encoding='utf-8')
    print('batch102 CO: OK (' + ', '.join(applied) + ')')


# B. ChatMessage.kt
t = (ROOT / CM).read_text(encoding='utf-8')
if MARK in t:
    print('batch102: CM already applied')
else:
    lines = t.split(NL)

    STEPS_ANCHOR = 'steps = block.steps,'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == STEPS_ANCHOR]
    if len(hits) != 1:
        fail('steps=block.steps anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    si = hits[0]
    d = ind(lines[si])
    lines.insert(si + 1, d + 'collapsedLabel = ToolSummaryMapper.summarize(block.steps), // ' + MARK)

    out = NL.join(lines)
    for need in [MARK, 'ToolSummaryMapper.summarize']:
        if need not in out:
            fail('CM selfcheck missing: ' + need)

    (ROOT / CM).write_text(out, encoding='utf-8')
    print('batch102 CM: OK')

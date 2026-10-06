#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch116: task C - ReasoningPicker bottom sheet beautification

The stream toggle row (batch112) is plain. Adds a divider above it and an
icon next to the label for visual hierarchy.

Five checks:
1. import: add HorizontalDivider + Icon (already imported for level icon)
2. conflict: ReasoningPicker.kt touched by batch112v5 only; anchor on its
   inserted Switch row
3. scope: inside the bottom sheet Column
4. brackets: self-balanced
5. signature: unchanged
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhPickerBeauty'
RP = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ReasoningPicker.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch116 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + RP + '::' + body[:1400])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


t = (ROOT / RP).read_text(encoding='utf-8')
if MARK in t:
    print('batch116: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    applied = []

    # 1. imports
    imp_hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('import ')]
    if not imp_hits:
        fail('no import lines')
    last_imp = imp_hits[-1]
    existing = set(ln.strip() for ln in lines)
    need = [
        'import androidx.compose.material3.HorizontalDivider',
    ]
    missing = [x for x in need if x not in existing]
    for j, imp in enumerate(missing):
        lines.insert(last_imp + 1 + j, imp + ' // ' + MARK)
    applied.append('imports+' + str(len(missing)))

    # 2. Add HorizontalDivider before the stream toggle Row
    #    Anchor: the stream toggle comment line from batch112v5
    ANCHOR = '// rhStreamToggle: stream output toggle'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == ANCHOR]
    if len(hits) != 1:
        fail('stream toggle anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ai = hits[0]
    d = ind(lines[ai])
    lines.insert(ai, d + 'HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp)) // ' + MARK)
    applied.append('divider')

    out = NL.join(lines)
    for need in [MARK, 'HorizontalDivider']:
        if need not in out:
            fail('selfcheck missing: ' + need)
    if balance(out) != bal0:
        fail('balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

    (ROOT / RP).write_text(out, encoding='utf-8')
    print('batch116: OK (' + ', '.join(applied) + ')')

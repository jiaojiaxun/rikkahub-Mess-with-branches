#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch112 v3: fix - ReasoningButton also needs streamOutput params

v2 only added params to ReasoningPicker, but ChatInput calls ReasoningButton
which doesn't have streamOutput/onUpdateStreamOutput params.

v3 adds params to BOTH ReasoningButton (sign + internal ReasoningPicker call)
AND ReasoningPicker (already done in v2).

Changes to ReasoningPicker.kt:
  A. ReasoningButton signature: add streamOutput + onUpdateStreamOutput
  B. ReasoningButton body: pass them to ReasoningPicker call
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhStreamToggle'
RP = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ReasoningPicker.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch112v3 ' + str(msg)
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


t = (ROOT / RP).read_text(encoding='utf-8')
if 'rhStreamToggleBtn' in t:
    print('batch112v3: already applied')
else:
    lines = t.split(NL)
    applied = []

    # A. ReasoningButton signature: add streamOutput + onUpdateStreamOutput
    #    Anchor: onUpdateReasoningLevel: (ReasoningLevel) -> Unit,
    #    This appears in BOTH ReasoningButton and ReasoningPicker.
    #    We need to add to ReasoningButton only.
    #    ReasoningButton is the FIRST occurrence (fun ReasoningButton comes before fun ReasoningPicker)
    SIG_ANCHOR = 'onUpdateReasoningLevel: (ReasoningLevel) -> Unit,'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == SIG_ANCHOR]
    if len(hits) < 1:
        fail('onUpdateReasoningLevel anchor count=' + str(len(hits)))
    # First occurrence = ReasoningButton
    rb_sig = hits[0]
    d = ind(lines[rb_sig])
    lines.insert(rb_sig + 1, d + 'streamOutput: Boolean = true, // rhStreamToggleBtn')
    lines.insert(rb_sig + 2, d + 'onUpdateStreamOutput: (Boolean) -> Unit = {}, // rhStreamToggleBtn')
    applied.append('btn-sig')

    # B. ReasoningButton body: pass to ReasoningPicker call
    #    Anchor: onUpdateReasoningLevel = onUpdateReasoningLevel
    #    This is inside ReasoningButton's body (the ReasoningPicker call)
    CALL_ANCHOR = 'onUpdateReasoningLevel = onUpdateReasoningLevel'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == CALL_ANCHOR]
    if len(hits) != 1:
        fail('ReasoningPicker call anchor count=' + str(len(hits)))
    ci = hits[0]
    d = ind(lines[ci])
    lines.insert(ci + 1, d + 'streamOutput = streamOutput, // rhStreamToggleBtn')
    lines.insert(ci + 2, d + 'onUpdateStreamOutput = onUpdateStreamOutput, // rhStreamToggleBtn')
    applied.append('btn-call')

    out = NL.join(lines)
    for need in ['rhStreamToggleBtn', 'streamOutput = streamOutput']:
        if need not in out:
            fail('selfcheck missing: ' + need)

    (ROOT / RP).write_text(out, encoding='utf-8')
    print('batch112v3: OK (' + ', '.join(applied) + ')')

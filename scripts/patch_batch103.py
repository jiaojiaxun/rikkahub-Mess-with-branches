#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch103 v5: fully idempotent guards (all 4 parts)

v4 compiled but produced duplicate imports/params because batch80v6 already
touches TopBar. v5 makes every part conditional on absence:
  A. imports - only add if not already present (exact-line check)
  B. hazeState param - only add if not already in signature
  C. TopAppBar modifier - only add if no hazeBlur( call already
  D. call-site arg - only add if hazeState = hazeState not already present
Uses fully-qualified names in C to avoid import ambiguity lint.
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhTopBarBlur'
CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch103v5 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + CP + '::' + body[:1400])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


t = (ROOT / CP).read_text(encoding='utf-8')
if MARK in t:
    print('batch103v5: already applied')
else:
    lines = t.split(NL)
    existing = set(ln.strip() for ln in lines)
    joined = NL.join(lines)
    applied = []

    # A. imports - only add each if absent (exact line)
    need_imports = [
        'import dev.chrisbanes.haze.HazeInput',
        'import dev.chrisbanes.haze.HazeState',
        'import dev.chrisbanes.haze.blur.hazeBlur',
    ]
    missing = [imp for imp in need_imports if imp not in existing]
    if missing:
        anchor = [i for i, ln in enumerate(lines) if ln.strip() == 'import dev.chrisbanes.haze.rememberHazeState']
        if len(anchor) != 1:
            fail('rememberHazeState anchor count=' + str(len(anchor)))
        for j, imp in enumerate(missing):
            lines.insert(anchor[0] + 1 + j, imp)
        applied.append('imports+' + str(len(missing)))

    # B. hazeState param - only add if no such param already
    if 'hazeState: HazeState' not in joined:
        SIG_ANCHOR = 'onImportSharedConversation: () -> Unit,'
        hits = [i for i, ln in enumerate(lines) if ln.strip() == SIG_ANCHOR]
        if len(hits) != 1:
            fail('sig anchor count=' + str(len(hits)))
        d = ind(lines[hits[0]])
        lines.insert(hits[0] + 1, d + 'hazeState: HazeState, // ' + MARK)
        applied.append('signature')
    else:
        applied.append('signature-skip')

    # C. TopAppBar modifier - only add if no hazeBlur( call present
    if 'hazeBlur(' not in joined:
        COLORS_ANCHOR = 'colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.Transparent),'
        hits = [i for i, ln in enumerate(lines) if COLORS_ANCHOR in ln]
        if len(hits) != 1:
            fail('colors anchor count=' + str(len(hits)))
        d = ind(lines[hits[0]])
        lines.insert(hits[0], d + 'modifier = Modifier.hazeBlur(input = HazeInput.Sources(hazeState)), // ' + MARK)
        applied.append('modifier')
    else:
        applied.append('modifier-skip')

    # D. call-site arg - only add if absent
    if 'hazeState = hazeState' not in joined:
        CALL_ANCHOR = 'onImportSharedConversation = {'
        hits = [i for i, ln in enumerate(lines) if ln.strip() == CALL_ANCHOR]
        if len(hits) != 1:
            fail('call-site anchor count=' + str(len(hits)))
        d = ind(lines[hits[0]])
        lines.insert(hits[0], d + 'hazeState = hazeState, // ' + MARK)
        applied.append('callsite')
    else:
        applied.append('callsite-skip')

    out = NL.join(lines)
    if MARK not in out:
        fail('MARK missing')
    if 'hazeBlur(' not in out:
        fail('hazeBlur call missing')
    for imp in need_imports:
        if out.count(imp) > 1:
            fail('duplicate import: ' + imp)

    (ROOT / CP).write_text(out, encoding='utf-8')
    print('batch103v5: OK (' + ', '.join(applied) + ')')

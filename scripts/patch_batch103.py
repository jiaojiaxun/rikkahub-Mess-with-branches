#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch103 v2: fix import anchor - fork ChatPage.kt has no hazeSource import

v1 failed: anchor 'import dev.chrisbanes.haze.hazeSource' does not exist in
fork ChatPage.kt. The fork only imports rememberHazeState (for creating
hazeState); hazeSource is in ChatList.kt instead.

v2: anchor on 'import dev.chrisbanes.haze.rememberHazeState' instead.
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhTopBarBlur'
CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch103v2 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + CP + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


t = (ROOT / CP).read_text(encoding='utf-8')
if MARK in t:
    print('batch103v2: already applied')
else:
    lines = t.split(NL)
    applied = []

    # A. Add imports after existing rememberHazeState import
    IMP_ANCHOR = 'import dev.chrisbanes.haze.rememberHazeState'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == IMP_ANCHOR]
    if len(hits) != 1:
        fail('rememberHazeState import anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ii = hits[0]
    d = ind(lines[ii])
    new_imports = [
        d + 'import dev.chrisbanes.haze.HazeInput // ' + MARK,
        d + 'import dev.chrisbanes.haze.HazeState // ' + MARK,
        d + 'import dev.chrisbanes.haze.blur.hazeBlur // ' + MARK,
    ]
    lines[ii + 1:ii + 1] = new_imports
    applied.append('imports')

    # B. TopBar signature: add hazeState param after onImportSharedConversation
    SIG_ANCHOR = 'onImportSharedConversation: () -> Unit,'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == SIG_ANCHOR]
    if len(hits) != 1:
        fail('TopBar sig anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    si = hits[0]
    d = ind(lines[si])
    lines.insert(si + 1, d + 'hazeState: HazeState, // ' + MARK)
    applied.append('signature')

    # C. TopAppBar: add modifier=hazeBlur before colors line
    COLORS_ANCHOR = 'colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.Transparent),'
    hits = [i for i, ln in enumerate(lines) if COLORS_ANCHOR in ln]
    if len(hits) != 1:
        fail('TopAppBar colors anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ci = hits[0]
    d = ind(lines[ci])
    lines.insert(ci, d + 'modifier = Modifier.hazeBlur(input = HazeInput.Sources(hazeState)), // ' + MARK)
    applied.append('modifier')

    # D. Call site: pass hazeState after onImportSharedConversation arg
    CALL_ANCHOR = 'onImportSharedConversation = { sharedConversationImportLauncher.launch(arrayOf(' + Q + 'text/*' + Q + ', ' + Q + 'application/json' + Q + ')) }'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == CALL_ANCHOR]
    if len(hits) != 1:
        fail('call site anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    di = hits[0]
    d = ind(lines[di])
    lines.insert(di + 1, d + 'hazeState = hazeState, // ' + MARK)
    applied.append('callsite')

    out = NL.join(lines)
    for need in [MARK, 'hazeBlur', 'HazeInput.Sources', 'hazeState: HazeState']:
        if need not in out:
            fail('selfcheck missing: ' + need)

    (ROOT / CP).write_text(out, encoding='utf-8')
    print('batch103v2: OK (' + ', '.join(applied) + ')')

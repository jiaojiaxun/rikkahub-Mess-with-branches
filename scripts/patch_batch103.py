#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch103 v4: fix call-site anchor - fork uses MULTI-LINE lambda format

v1/v2/v3 all failed on D (call site) because the fork formats the TopBar args
as multi-line lambdas:
    onNewChat = {
        navigateToChatPage(navController)
    },
    onImportSharedConversation = {
        sharedConversationImportLauncher.launch(arrayOf("text/*", "application/json"))
    }
v3 anchored on the single-line `onNewChat = { navigateToChatPage(navController) },`
which does not exist in the multi-line form. v4 anchors on the multi-line first
line `onImportSharedConversation = {` (unique; the signature line is
`onImportSharedConversation: () -> Unit,` with a colon, so no collision).

A/B/C were already passing in v2/v3.
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhTopBarBlur'
CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch103v4 ' + str(msg)
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
    print('batch103v4: already applied')
else:
    lines = t.split(NL)
    applied = []

    # A. imports after rememberHazeState
    IMP_ANCHOR = 'import dev.chrisbanes.haze.rememberHazeState'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == IMP_ANCHOR]
    if len(hits) != 1:
        fail('rememberHazeState anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ii = hits[0]
    d = ind(lines[ii])
    lines[ii + 1:ii + 1] = [
        d + 'import dev.chrisbanes.haze.HazeInput // ' + MARK,
        d + 'import dev.chrisbanes.haze.HazeState // ' + MARK,
        d + 'import dev.chrisbanes.haze.blur.hazeBlur // ' + MARK,
    ]
    applied.append('imports')

    # B. TopBar signature: add hazeState after onImportSharedConversation type line
    SIG_ANCHOR = 'onImportSharedConversation: () -> Unit,'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == SIG_ANCHOR]
    if len(hits) != 1:
        fail('sig anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    si = hits[0]
    d = ind(lines[si])
    lines.insert(si + 1, d + 'hazeState: HazeState, // ' + MARK)
    applied.append('signature')

    # C. TopAppBar: add modifier=hazeBlur before colors line
    COLORS_ANCHOR = 'colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.Transparent),'
    hits = [i for i, ln in enumerate(lines) if COLORS_ANCHOR in ln]
    if len(hits) != 1:
        fail('colors anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ci = hits[0]
    d = ind(lines[ci])
    lines.insert(ci, d + 'modifier = Modifier.hazeBlur(input = HazeInput.Sources(hazeState)), // ' + MARK)
    applied.append('modifier')

    # D. Call site: insert hazeState = hazeState, BEFORE the multi-line
    #    `onImportSharedConversation = {` first line (unique: signature has a colon)
    CALL_ANCHOR = 'onImportSharedConversation = {'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == CALL_ANCHOR]
    if len(hits) != 1:
        fail('call site onImportSharedConversation={{ anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    di = hits[0]
    d = ind(lines[di])
    lines.insert(di, d + 'hazeState = hazeState, // ' + MARK)
    applied.append('callsite')

    out = NL.join(lines)
    for need in [MARK, 'hazeBlur', 'HazeInput.Sources', 'hazeState: HazeState', 'hazeState = hazeState,']:
        if need not in out:
            fail('selfcheck missing: ' + need)

    (ROOT / CP).write_text(out, encoding='utf-8')
    print('batch103v4: OK (' + ', '.join(applied) + ')')

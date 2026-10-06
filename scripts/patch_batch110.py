#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch110: fix TopBar glass blur - move hazeBlur to Surface + transparent bg

Root cause: batch80v6 wraps TopAppBar in a Surface with opaque
surfaceContainerLow background, which occludes the hazeBlur added by
batch103v5 on TopAppBar. Blur is invisible behind opaque paint.

Fix (targets CI form: repo + batch80v6 + batch82 + batch103v5):
  A. Delete the hazeBlur modifier line from TopAppBar (batch103v5)
  B. Add modifier = Modifier.hazeBlur(...) to the Surface (batch80v6)
  C. Change Surface color from surfaceContainerLow to Color.Transparent

Five checks:
1. import: zero new (hazeBlur/HazeInput already imported by batch103v5)
2. conflict: ChatPage.kt touched by batch80v6/82/103v5 - anchors match their
   CI-form output exactly (marker lines)
3. scope: TopBar function body
4. brackets: delete single line (delta 0); insert modifier param (comma); edit color value
5. signature: no change
Python three checks: Q/NL/helper/exit(1)
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhTopBarGlassFix'
CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch110 ' + str(msg)
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
    print('batch110: already applied')
else:
    lines = t.split(NL)
    applied = []

    # A. Delete batch103v5's hazeBlur line from TopAppBar
    #    (CI form: modifier = Modifier.hazeBlur(input = HazeInput.Sources(hazeState)), // rhTopBarBlur)
    BLUR_ANCHOR = 'modifier = Modifier.hazeBlur(input = HazeInput.Sources(hazeState)), // rhTopBarBlur'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == BLUR_ANCHOR]
    if len(hits) != 1:
        fail('TopAppBar hazeBlur line count=' + str(len(hits)), lines, hits[0] if hits else 0)
    del lines[hits[0]]
    applied.append('delete-topappbar-blur')

    # B. Add modifier = hazeBlur to batch80v6's Surface (anchor: Surface( // rhTopBarAlignInput)
    SURF_ANCHOR = 'Surface( // rhTopBarAlignInput'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == SURF_ANCHOR]
    if len(hits) != 1:
        fail('Surface rhTopBarAlignInput anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    si = hits[0]
    d = ind(lines[si])
    lines.insert(si + 1, d + '    modifier = Modifier.hazeBlur(input = HazeInput.Sources(hazeState)), // ' + MARK)
    applied.append('surface-blur')

    # C. Change Surface color from surfaceContainerLow to Color.Transparent
    COLOR_ANCHOR = 'color = MaterialTheme.colorScheme.surfaceContainerLow,'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == COLOR_ANCHOR]
    if len(hits) != 1:
        fail('Surface color anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ci = hits[0]
    d = ind(lines[ci])
    lines[ci] = d + 'color = Color.Transparent, // ' + MARK
    applied.append('surface-transparent')

    out = NL.join(lines)
    for need in [MARK, 'Color.Transparent', 'rhTopBarAlignInput']:
        if need not in out:
            fail('selfcheck missing: ' + need)
    # TopAppBar should NOT have hazeBlur modifier anymore
    if BLUR_ANCHOR in out:
        fail('TopAppBar hazeBlur still present after delete')

    (ROOT / CP).write_text(out, encoding='utf-8')
    print('batch110: OK (' + ', '.join(applied) + ')')

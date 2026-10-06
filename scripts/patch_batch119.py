#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch119: hide 'import shared conversation' button when chat is not fresh

User request: when a conversation already has content, the top-bar
'import shared conversation' (FileImport) button should auto-hide.

Location: ChatPage.kt TopBar(), actions block. The import button + its
DropdownMenu are wrapped in a `Box`. We wrap that Box in
`if (conversation.messageNodes.isEmpty()) { ... }`.

Five checks:
1. import: zero new (Box/if already available)
2. conflict: ChatPage.kt touched by batch48/70 etc; this anchor is the
   TopBar actions Box, distinct from those regions
3. scope: inside TopAppBar actions lambda
4. brackets: wrapped block self-balanced
5. signature: unchanged
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhHideImport'
CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch119 ' + str(msg)
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


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


t = (ROOT / CP).read_text(encoding='utf-8')
if MARK in t:
    print('batch119: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)

    # Anchor: the share-menu var declaration inside actions {}
    ANCHOR = 'var showShareMenu by remember { mutableStateOf(false) }'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == ANCHOR]
    if len(hits) != 1:
        fail('showShareMenu anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    vi = hits[0]
    d = ind(lines[vi])

    # Insert an `if (conversation.messageNodes.isEmpty()) {` before this line,
    # and close it after the share Box block ends.
    # Find the Box that wraps the import button + DropdownMenu:
    # it starts at the 'Box {' right after this var, and ends before the next
    # 'IconButton(' (the menu toggle).
    box_idx = -1
    for j in range(vi + 1, min(vi + 5, len(lines))):
        if lines[j].strip() == 'Box {':
            box_idx = j
            break
    if box_idx < 0:
        fail('share Box not found after showShareMenu', lines, vi)
    # find matching close of that Box
    depth = 0
    box_close = -1
    for j in range(box_idx, len(lines)):
        for ch in lines[j]:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
        if depth <= 0 and j > box_idx:
            box_close = j
            break
    if box_close < 0:
        fail('share Box close not found', lines, box_idx)

    # wrap: insert if-open before box_idx, if-close after box_close
    lines.insert(box_idx, ind(lines[box_idx]) + '// ' + MARK + ': hide import button when not a fresh chat')
    lines.insert(box_idx + 1, ind(lines[box_idx]) + 'if (conversation.messageNodes.isEmpty()) {')
    lines.insert(box_close + 2, ind(lines[box_idx]) + '}')

    out = NL.join(lines)
    for need in [MARK, 'conversation.messageNodes.isEmpty()']:
        if need not in out:
            fail('selfcheck missing: ' + need)
    if balance(out) != bal0:
        fail('balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

    (ROOT / CP).write_text(out, encoding='utf-8')
    print('batch119: OK')

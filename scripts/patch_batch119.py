#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch119 v2: hide import button - correct "fresh conversation" definition

v1 used `conversation.messageNodes.isEmpty()`, which is WRONG: an assistant's
preset opening messages (presetMessages) create messageNodes too, so a brand-
new conversation with a preset opener would be misjudged as "has content".

User clarified: fresh = no USER-sent messages (preset assistant openings don't
count as content). So the correct check is: hide when there exists at least one
message with role == USER.

v2: `conversation.messageNodes.none { node -> node.messages.any { it.role ==
me.rerere.ai.core.MessageRole.USER } }` gates the button (show only when fresh).

Five checks:
1. import: uses fully-qualified me.rerere.ai.core.MessageRole (no new import
   needed; avoids uncertain import state)
2. conflict: same TopBar anchor as v1; MARK replaced
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
    body = 'batch119v2 ' + str(msg)
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
    print('batch119v2: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)

    # Anchor: showShareMenu var inside actions {}
    ANCHOR = 'var showShareMenu by remember { mutableStateOf(false) }'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == ANCHOR]
    if len(hits) != 1:
        fail('showShareMenu anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    vi = hits[0]

    # find the wrapping Box after the var
    box_idx = -1
    for j in range(vi + 1, min(vi + 5, len(lines))):
        if lines[j].strip() == 'Box {':
            box_idx = j
            break
    if box_idx < 0:
        fail('share Box not found after showShareMenu', lines, vi)
    # find matching close of that Box via brace depth
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

    di = ind(lines[box_idx])
    # v2: correct fresh-check -> no USER messages
    lines.insert(box_idx, di + '// ' + MARK + ': hide import button when conversation already has user messages')
    lines.insert(box_idx + 1, di + 'val rhHasUserMsg = conversation.messageNodes.any { n -> n.messages.any { it.role == me.rerere.ai.core.MessageRole.USER } }')
    lines.insert(box_idx + 2, di + 'if (!rhHasUserMsg) {')
    lines.insert(box_close + 3, di + '}')

    out = NL.join(lines)
    for need in [MARK, 'rhHasUserMsg', 'MessageRole.USER']:
        if need not in out:
            fail('selfcheck missing: ' + need)
    if balance(out) != bal0:
        fail('balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

    (ROOT / CP).write_text(out, encoding='utf-8')
    print('batch119v2: OK')

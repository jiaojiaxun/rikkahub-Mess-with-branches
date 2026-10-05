#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch104: fix parent_chat_id lost on OFFICIAL/PURE_OFFICIAL backup restore

Root cause: OFFICIAL/PURE_OFFICIAL export rebuilds ConversationEntity per
official v24 schema, dropping fork-only columns. batch89 fixed chat_model_id
by adding ALTER TABLE in the stamp path. parent_chat_id has the same problem
but was never patched.

Fix: add ALTER TABLE for parent_chat_id right after the chat_model_id one.

Five checks:
1. import: zero new
2. conflict: ImportedDatabaseReconciler.kt was directly pushed (batch89),
   not patched by any patch_batch*.py - so repo form == CI form
3. scope: inside reconcileDatabaseFile, between beginTransaction/endTransaction
4. brackets: inserted block is self-balanced
5. signature: no change
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhParentChatId'
IDR = 'app/src/main/java/me/rerere/rikkahub/data/db/ImportedDatabaseReconciler.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch104 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + IDR + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


t = (ROOT / IDR).read_text(encoding='utf-8')
if MARK in t:
    print('batch104: already applied')
else:
    lines = t.split(NL)

    # Anchor: the chat_model_id ALTER TABLE block's closing brace
    # Find the if (!hasColumn(...chat_model_id...)) { block and its closing }
    ANCHOR = 'if (!hasColumn(db, ' + Q + 'ConversationEntity' + Q + ', ' + Q + 'chat_model_id' + Q + ')) {'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == ANCHOR]
    if len(hits) != 1:
        fail('chat_model_id hasColumn anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    start = hits[0]

    # Find matching closing brace
    depth = 0
    end = -1
    for i in range(start, len(lines)):
        for ch in lines[i]:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
        if depth <= 0:
            end = i
            break
    if end < 0:
        fail('chat_model_id block end not found', lines, start)

    d = ind(lines[start])
    insert_block = [
        d + 'if (!hasColumn(db, ' + Q + 'ConversationEntity' + Q + ', ' + Q + 'parent_chat_id' + Q + ')) {',
        d + '    db.execSQL(',
        d + '        ' + Q + 'ALTER TABLE ' + Q + '`ConversationEntity`' + Q + ' ADD COLUMN `parent_chat_id` TEXT' + Q,
        d + '    )',
        d + '} // ' + MARK,
    ]
    lines[end + 1:end + 1] = insert_block

    out = NL.join(lines)
    for need in [MARK, 'parent_chat_id']:
        if need not in out:
            fail('selfcheck missing: ' + need)

    (ROOT / IDR).write_text(out, encoding='utf-8')
    print('batch104: OK (parent_chat_id ALTER TABLE added)')

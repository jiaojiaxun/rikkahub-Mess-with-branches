#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch104 v2: fix triple-literal quote bug in parent_chat_id ALTER TABLE

v1 compiled with error at ImportedDatabaseReconciler.kt L218:
  "Literals must be surrounded by whitespace"
  "Unresolved reference 'ConversationEntity' on receiver of type 'String'"
Root cause: v1 wrote Q + 'ALTER TABLE ' + Q + '`ConversationEntity`' + Q + ' ADD COLUMN...'
which produces THREE separate string literals. Fix: one single literal.
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhParentChatId'
IDR = 'app/src/main/java/me/rerere/rikkahub/data/db/ImportedDatabaseReconciler.kt'


def fail(msg):
    print('::error file=' + IDR + '::batch104v2 ' + str(msg)[:1200])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


t = (ROOT / IDR).read_text(encoding='utf-8')
if MARK in t:
    print('batch104v2: already applied')
else:
    lines = t.split(NL)

    ANCHOR = 'if (!hasColumn(db, ' + Q + 'ConversationEntity' + Q + ', ' + Q + 'chat_model_id' + Q + ')) {'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == ANCHOR]
    if len(hits) != 1:
        fail('chat_model_id anchor count=' + str(len(hits)))
    start = hits[0]

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
        fail('block end not found')

    d = ind(lines[start])
    # single string literal for the SQL
    SQL = Q + 'ALTER TABLE `ConversationEntity` ADD COLUMN `parent_chat_id` TEXT' + Q
    insert_block = [
        d + 'if (!hasColumn(db, ' + Q + 'ConversationEntity' + Q + ', ' + Q + 'parent_chat_id' + Q + ')) {',
        d + '    db.execSQL(' + SQL + ')',
        d + '} // ' + MARK,
    ]
    lines[end + 1:end + 1] = insert_block

    out = NL.join(lines)
    if MARK not in out or 'parent_chat_id' not in out:
        fail('selfcheck missing')
    if out.count(SQL) != 1:
        fail('SQL literal count != 1')

    (ROOT / IDR).write_text(out, encoding='utf-8')
    print('batch104v2: OK (single-literal SQL)')

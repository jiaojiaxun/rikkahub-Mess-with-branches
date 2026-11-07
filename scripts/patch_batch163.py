#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch163: 修 BackupArchiveRestorer.kt 编译错误(batch150 引入)

编译错误: Unresolved reference 'JsonArray' / 'jsonObject' / 'JsonElement'
改动: 加 3 个 import
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhBackupRestorerFix'
BR = 'app/src/main/java/me/rerere/rikkahub/data/sync/webdav/BackupArchiveRestorer.kt'


def fail(msg):
    print('::error file=' + BR + '::batch163 ' + str(msg)[:1400])
    sys.stdout.flush()
    sys.exit(0)


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


t = (ROOT / BR).read_text(encoding='utf-8')
if MARK in t:
    print('batch163: already applied')
    sys.exit(0)

bal0 = balance(t)
lines = t.split(NL)

imp_hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('import ')]
if not imp_hits:
    fail('no import lines')
last_imp = imp_hits[-1]

new_imports = [
    'import kotlinx.serialization.json.JsonArray // ' + MARK,
    'import kotlinx.serialization.json.JsonElement // ' + MARK,
    'import kotlinx.serialization.json.jsonObject // ' + MARK,
]
for j, imp in enumerate(new_imports):
    lines.insert(last_imp + 1 + j, imp)

out = NL.join(lines)
if MARK not in out:
    fail('marker missing')
if balance(out) != bal0:
    fail('balance changed')

(ROOT / BR).write_text(out, encoding='utf-8')
print('::notice::batch163 OK - BackupArchiveRestorer imports added')

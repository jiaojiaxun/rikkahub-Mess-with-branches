#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch106: LITE backup attachment size threshold

LITE mode now skips files larger than a threshold (default 5MB) in uploads/
and fonts/. Smaller files (icons, small images, text) are kept.

Changes to WebDavSync.kt:
  A. Add const LITE_MAX_FILE_SIZE = 5L * 1024 * 1024
  B. backupFileEntries signature: add maxFileSize param (default MAX_VALUE)
  C. filter: add && it.length() <= maxFileSize to both walkTopDown filters
  D. prepareBackupFile: pass LITE_MAX_FILE_SIZE when format == LITE

Five checks:
1. import: zero new
2. conflict: WebDavSync.kt touched by batch6v2 (createOfficialSettingsText +
   createFullDatabaseSnapshot lines). Anchors (backupFileEntries sig +
   fileEntries line + walkTopDown lines) not in batch6 region.
3. scope: backupFileEntries private fun + prepareBackupFile fun
4. brackets: param addition comma-separated; filter change inline
5. signature: backupFileEntries adds param with default
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhLiteThreshold'
WD = 'app/src/main/java/me/rerere/rikkahub/data/sync/webdav/WebDavSync.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch106 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + WD + '::' + body[:1400])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


t = (ROOT / WD).read_text(encoding='utf-8')
if MARK in t:
    print('batch106: already applied')
else:
    lines = t.split(NL)
    applied = []

    # A. Add const after COPY_BUFFER_SIZE
    CONST_ANCHOR = 'private const val COPY_BUFFER_SIZE = 16 * 1024'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == CONST_ANCHOR]
    if len(hits) != 1:
        fail('COPY_BUFFER_SIZE anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ci = hits[0]
    d = ind(lines[ci])
    lines.insert(ci + 1, d + 'private const val LITE_MAX_FILE_SIZE = 5L * 1024 * 1024 // ' + MARK)
    applied.append('const')

    # B. backupFileEntries signature: add maxFileSize param
    SIG_OLD = 'private fun backupFileEntries(full: Boolean): List<Pair<File, String>> = buildList {'
    SIG_NEW = 'private fun backupFileEntries(full: Boolean, maxFileSize: Long = Long.MAX_VALUE): List<Pair<File, String>> = buildList {'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == SIG_OLD]
    if len(hits) != 1:
        fail('backupFileEntries sig anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    lines[hits[0]] = ind(lines[hits[0]]) + SIG_NEW
    applied.append('signature')

    # C. Replace both walkTopDown filter lines to add size check
    OLD_FILTER = 'root.walkTopDown().filter(File::isFile).forEach { file ->'
    NEW_FILTER = 'root.walkTopDown().filter { it.isFile && it.length() <= maxFileSize }.forEach { file ->'
    replaced = 0
    for i in range(len(lines)):
        if lines[i].strip() == OLD_FILTER:
            lines[i] = ind(lines[i]) + NEW_FILTER
            replaced += 1
    if replaced != 2:
        fail('walkTopDown filter replaced count=' + str(replaced) + ' (expected 2)')
    applied.append('filters(' + str(replaced) + ')')

    # D. prepareBackupFile: pass LITE_MAX_FILE_SIZE when format == LITE
    CALL_OLD = 'val fileEntries = if (includeFiles) backupFileEntries(full) else emptyList()'
    CALL_NEW = ('val liteMax = if (format == BackupExportFormat.LITE) LITE_MAX_FILE_SIZE else Long.MAX_VALUE // ' + MARK + NL +
                ind(lines[0]) + '            val fileEntries = if (includeFiles) backupFileEntries(full, liteMax) else emptyList()')
    hits = [i for i, ln in enumerate(lines) if ln.strip() == CALL_OLD]
    if len(hits) != 1:
        fail('fileEntries call anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    d = ind(lines[hits[0]])
    lines[hits[0]] = d + 'val liteMax = if (format == BackupExportFormat.LITE) LITE_MAX_FILE_SIZE else Long.MAX_VALUE // ' + MARK
    lines.insert(hits[0] + 1, d + 'val fileEntries = if (includeFiles) backupFileEntries(full, liteMax) else emptyList()')
    # remove old line (now at hits[0]+2 since we inserted one)
    del lines[hits[0] + 2]
    applied.append('callsite')

    out = NL.join(lines)
    for need in [MARK, 'LITE_MAX_FILE_SIZE', 'maxFileSize', 'liteMax']:
        if need not in out:
            fail('selfcheck missing: ' + need)

    (ROOT / WD).write_text(out, encoding='utf-8')
    print('batch106: OK (' + ', '.join(applied) + ')')

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch106 v4: includeImages read from config.liteAttachmentTypes

v3 hardcoded includeImages = true. v4 reads it from the WebDavConfig field
added by batch114 (order: 106 < 114, both run in the same CI pass).
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhLiteThreshold'
WD = 'app/src/main/java/me/rerere/rikkahub/data/sync/webdav/WebDavSync.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch106v4 ' + str(msg)
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
    print('batch106v4: already applied')
else:
    lines = t.split(NL)
    applied = []

    # A. consts
    CONST_ANCHOR = 'private const val COPY_BUFFER_SIZE = 16 * 1024'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == CONST_ANCHOR]
    if len(hits) != 1:
        fail('COPY_BUFFER_SIZE anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ci = hits[0]
    d = ind(lines[ci])
    lines.insert(ci + 1, d + 'private const val LITE_MAX_FILE_SIZE = 3L * 1024 * 1024 // ' + MARK)
    lines.insert(ci + 2, d + 'private val IMAGE_EXTS = setOf("jpg", "jpeg", "png", "gif", "webp", "bmp", "heic", "heif") // ' + MARK)
    applied.append('consts')

    # B. signature
    SIG_OLD = 'private fun backupFileEntries(full: Boolean): List<Pair<File, String>> = buildList {'
    SIG_NEW = 'private fun backupFileEntries(full: Boolean, maxFileSize: Long = Long.MAX_VALUE, includeImages: Boolean = true): List<Pair<File, String>> = buildList {'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == SIG_OLD]
    if len(hits) != 1:
        fail('sig anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    lines[hits[0]] = ind(lines[hits[0]]) + SIG_NEW
    applied.append('signature')

    # C. filters
    OLD_FILTER = 'root.walkTopDown().filter(File::isFile).forEach { file ->'
    NEW_FILTER = 'root.walkTopDown().filter { it.isFile && it.length() <= maxFileSize && (includeImages || it.extension.lowercase() !in IMAGE_EXTS) }.forEach { file ->'
    replaced = 0
    for i in range(len(lines)):
        if lines[i].strip() == OLD_FILTER:
            lines[i] = ind(lines[i]) + NEW_FILTER
            replaced += 1
    if replaced != 2:
        fail('walkTopDown filter replaced count=' + str(replaced))
    applied.append('filters(' + str(replaced) + ')')

    # D. call site: read from config
    CALL_OLD = 'val fileEntries = if (includeFiles) backupFileEntries(full) else emptyList()'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == CALL_OLD]
    if len(hits) != 1:
        fail('fileEntries call anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    d = ind(lines[hits[0]])
    lines[hits[0]] = d + 'val includeImages = config.liteAttachmentTypes.isEmpty() || WebDavConfig.LiteAttachmentType.IMAGE in config.liteAttachmentTypes // ' + MARK
    lines.insert(hits[0] + 1, d + 'val liteMax = if (format == BackupExportFormat.LITE) LITE_MAX_FILE_SIZE else Long.MAX_VALUE // ' + MARK)
    lines.insert(hits[0] + 2, d + 'val fileEntries = if (includeFiles) backupFileEntries(full, liteMax, includeImages) else emptyList()')
    applied.append('callsite')

    out = NL.join(lines)
    for need in [MARK, 'LITE_MAX_FILE_SIZE', 'includeImages', 'IMAGE_EXTS', 'LiteAttachmentType.IMAGE']:
        if need not in out:
            fail('selfcheck missing: ' + need)
    if 'totalBytes' not in out:
        fail('totalBytes missing')

    (ROOT / WD).write_text(out, encoding='utf-8')
    print('batch106v4: OK (' + ', '.join(applied) + ')')

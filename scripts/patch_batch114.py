#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch114: task 10b - LITE attachment type selector (文本/图片)

Adds WebDavConfig.liteAttachmentTypes (List<LiteAttachmentType>) + the enum,
and a 文本/图片 MultiChoiceSegmentedButtonRow in ImportExportTab right after
the backup-item selector added by batch113 (order: 113 < 114, so its MARK
exists when this runs).

Files:
  PreferencesStore.kt: enum LiteAttachmentType + field
  ImportExportTab.kt: selector UI, anchored on batch113's MARK

Five checks:
1. import: ImportExportTab reuses SegmentedButton imports from batch113; zero new
2. conflict: PreferencesStore.kt untouched by patches; ImportExportTab anchored
   on batch113 MARK (has a stable position)
3. scope: WebDavConfig data class + @Composable
4. brackets: self-balanced
5. signature: field has default
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhLiteTypes'
PS = 'app/src/main/java/me/rerere/rikkahub/data/datastore/PreferencesStore.kt'
IE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/backup/tabs/ImportExportTab.kt'


def fail(msg, lines=None, around=-1, path=PS):
    body = 'batch114 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + path + '::' + body[:1400])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


# ============================================================
# PreferencesStore.kt: enum + field
# ============================================================
t = (ROOT / PS).read_text(encoding='utf-8')
if MARK + 'PS' in t:
    print('batch114 PS: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)

    # A. add field + enum inside WebDavConfig
    #    Anchor: the items default line
    ITEM_ANCHOR = '    val items: List<BackupItem> = listOf('
    hits = [i for i, ln in enumerate(lines) if ln == ITEM_ANCHOR]
    if len(hits) != 1:
        fail('items anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ii = hits[0]
    # find the closing '),' of the items list
    close = -1
    for j in range(ii, len(lines)):
        if lines[j].strip() == '),':
            close = j
            break
    if close < 0:
        fail('items list close not found', lines, ii)
    d = ind(lines[ii])
    lines.insert(close + 1, d + 'val liteAttachmentTypes: List<LiteAttachmentType> = listOf(LiteAttachmentType.TEXT, LiteAttachmentType.IMAGE), // ' + MARK + 'PS')

    # B. add enum after BackupItem enum
    ENUM_ANCHOR = '    enum class BackupItem {'
    hits = [i for i, ln in enumerate(lines) if ln == ENUM_ANCHOR]
    if len(hits) != 1:
        fail('BackupItem enum anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ei = hits[0]
    # find the '}' that closes BackupItem enum
    enum_close = -1
    for j in range(ei, len(lines)):
        if lines[j].strip() == '}':
            enum_close = j
            break
    if enum_close < 0:
        fail('BackupItem enum close not found', lines, ei)
    d = ind(lines[ei])
    lines[enum_close + 1:enum_close + 1] = [
        d + '',
        d + 'enum class LiteAttachmentType { // ' + MARK + 'PS',
        d + '    TEXT,',
        d + '    IMAGE,',
        d + '}',
    ]

    out = NL.join(lines)
    for need in [MARK + 'PS', 'LiteAttachmentType', 'liteAttachmentTypes']:
        if need not in out:
            fail('PS selfcheck missing: ' + need)
    if balance(out) != bal0:
        fail('PS balance changed', path=PS)

    (ROOT / PS).write_text(out, encoding='utf-8')
    print('batch114 PS: OK')


# ============================================================
# ImportExportTab.kt: 文本/图片 selector after the backup-item item
# ============================================================
t = (ROOT / IE).read_text(encoding='utf-8')
if MARK + 'IE' in t:
    print('batch114 IE: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)

    # anchor: batch113's item block end. batch113 inserted:
    #   item(key = "backup_items") { // rhBackupItemPick
    #   ...
    #   }
    # Its closing is the '}' line. Find the start then the matching close.
    start = -1
    for i, ln in enumerate(lines):
        if 'item(key = "backup_items")' in ln and 'rhBackupItemPick' in ln:
            start = i
            break
    if start < 0:
        fail('batch113 anchor not found (run order: 113 before 114?)', lines, 0, path=IE)
    # find matching close: depth on braces from start
    depth = 0
    close = -1
    for i in range(start, len(lines)):
        for ch in lines[i]:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
        if depth <= 0 and i > start:
            close = i
            break
    if close < 0:
        fail('backup_items block close not found', lines, start, path=IE)
    d = ind(lines[start])
    block = [
        d + 'item(key = "lite_types") { // ' + MARK + 'IE',
        d + '    CardGroup(modifier = Modifier.padding(horizontal = 0.dp), title = { Text("轻量备份附件") }) {',
        d + '        item(',
        d + '            headlineContent = { Text("选择轻量备份包含的附件类型") },',
        d + '            supportingContent = {',
        d + '                MultiChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {',
        d + '                    WebDavConfig.LiteAttachmentType.entries.forEachIndexed { index, item ->',
        d + '                        SegmentedButton(',
        d + '                            shape = SegmentedButtonDefaults.itemShape(index = index, count = WebDavConfig.LiteAttachmentType.entries.size),',
        d + '                            onCheckedChange = { checked ->',
        d + '                                val cur = settings.webDavConfig.liteAttachmentTypes',
        d + '                                val next = if (checked) (cur + item).distinct() else cur - item',
        d + '                                vm.updateSettings(settings.copy(webDavConfig = settings.webDavConfig.copy(liteAttachmentTypes = next)))',
        d + '                            },',
        d + '                            checked = item in settings.webDavConfig.liteAttachmentTypes,',
        d + '                        ) {',
        d + '                            Text(if (item == WebDavConfig.LiteAttachmentType.TEXT) "文本" else "图片")',
        d + '                        }',
        d + '                    }',
        d + '                }',
        d + '            },',
        d + '        )',
        d + '    }',
        d + '}',
    ]
    lines[close + 1:close + 1] = block

    out = NL.join(lines)
    for need in [MARK + 'IE', 'LiteAttachmentType', 'liteAttachmentTypes']:
        if need not in out:
            fail('IE selfcheck missing: ' + need, path=IE)
    if balance(out) != bal0:
        fail('IE balance changed', path=IE)

    (ROOT / IE).write_text(out, encoding='utf-8')
    print('batch114 IE: OK')

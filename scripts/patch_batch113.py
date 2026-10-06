#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch113: task 9 - backup item selector in ImportExportTab

ImportExportTab currently has no 聊天记录/文件 multi-select; WebDavTab and S3Tab
do. This adds the same MultiChoiceSegmentedButtonRow bound to
settings.webDavConfig.items so the export honors the same DATABASE/FILES choice.

Files touched:
  ImportExportTab.kt only (batch6v2 added the LITE row; anchors avoid its region).

Five checks:
1. import: MultiChoiceSegmentedButtonRow / SegmentedButton / SegmentedButtonDefaults /
   WebDavConfig / collectAsStateWithLifecycle; each added only if absent
2. conflict: anchors are the LazyColumn start + the settings-collect area, both
   untouched by batch6v2 (which edited a specific item(...) block)
3. scope: inside ImportExportTab @Composable
4. brackets: self-balanced composable
5. signature: unchanged
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhBackupItemPick'
IE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/backup/tabs/ImportExportTab.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch113 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + IE + '::' + body[:1400])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


t = (ROOT / IE).read_text(encoding='utf-8')
if MARK in t:
    print('batch113: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    applied = []
    existing = set(ln.strip() for ln in lines)

    # 1. imports (only if absent), inserted after last import
    imp_hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('import ')]
    if not imp_hits:
        fail('no import lines')
    last_imp = imp_hits[-1]
    need = [
        'import androidx.compose.material3.MultiChoiceSegmentedButtonRow',
        'import androidx.compose.material3.SegmentedButton',
        'import androidx.compose.material3.SegmentedButtonDefaults',
        'import me.rerere.rikkahub.data.datastore.WebDavConfig',
    ]
    missing = [x for x in need if x not in existing]
    for j, imp in enumerate(missing):
        lines.insert(last_imp + 1 + j, imp + ' // ' + MARK)
    applied.append('imports+' + str(len(missing)))

    # 2. add settings collect after `val progress by ...`
    PROG = [i for i, ln in enumerate(lines) if ln.strip().startswith('val progress by vm.progress.collectAsStateWithLifecycle()')]
    if len(PROG) != 1:
        fail('progress collect anchor count=' + str(len(PROG)), lines, PROG[0] if PROG else 0)
    pi = PROG[0]
    d = ind(lines[pi])
    lines.insert(pi + 1, d + 'val settings by vm.settings.collectAsStateWithLifecycle() // ' + MARK)
    applied.append('settings-collect')

    # 3. insert backup-item selector as the first item of the export LazyColumn.
    #    Anchor: the LazyColumn's stickyHeader for local backup export.
    LC = [i for i, ln in enumerate(lines) if ln.strip().startswith('stickyHeader { StickyHeader { Text(stringResource(R.string.backup_page_local_bac')]
    if len(LC) != 1:
        fail('stickyHeader anchor count=' + str(len(LC)), lines, LC[0] if LC else 0)
    li = LC[0]
    d = ind(lines[li])
    block = [
        d + 'item(key = "backup_items") { // ' + MARK,
        d + '    CardGroup(modifier = Modifier.padding(horizontal = 0.dp), title = { Text("备份项") }) {',
        d + '        item(',
        d + '            headlineContent = { Text("选择要备份的内容") },',
        d + '            supportingContent = {',
        d + '                MultiChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {',
        d + '                    WebDavConfig.BackupItem.entries.forEachIndexed { index, item ->',
        d + '                        SegmentedButton(',
        d + '                            shape = SegmentedButtonDefaults.itemShape(index = index, count = WebDavConfig.BackupItem.entries.size),',
        d + '                            onCheckedChange = { checked ->',
        d + '                                val cur = settings.webDavConfig.items',
        d + '                                val next = if (checked) (cur + item).distinct() else cur - item',
        d + '                                vm.updateSettings(settings.copy(webDavConfig = settings.webDavConfig.copy(items = next)))',
        d + '                            },',
        d + '                            checked = item in settings.webDavConfig.items,',
        d + '                        ) {',
        d + '                            Text(if (item == WebDavConfig.BackupItem.DATABASE) "聊天记录" else "文件")',
        d + '                        }',
        d + '                    }',
        d + '                }',
        d + '            },',
        d + '        )',
        d + '    }',
        d + '}',
    ]
    lines[li:li] = block
    applied.append('selector')

    out = NL.join(lines)
    for need_t in [MARK, 'MultiChoiceSegmentedButtonRow', 'webDavConfig.items', 'settings by vm.settings']:
        if need_t not in out:
            fail('selfcheck missing: ' + need_t)
    if balance(out) != bal0:
        fail('balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

    (ROOT / IE).write_text(out, encoding='utf-8')
    print('batch113: OK (' + ', '.join(applied) + ')')

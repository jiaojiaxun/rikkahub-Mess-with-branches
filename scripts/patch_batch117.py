#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch117 v2: Step7 assistant card - fix 5 compile errors

v1 errors:
1. Unresolved reference 'IconButton' -> missing import
2. Unresolved reference 'getCurrentAssistant' / 'getCurrentChatModel'
   -> missing imports (they live in data.datastore)
3. UIAvatar onUpdate type inference failed -> the param is ((Avatar) -> Unit)?,
   used a trailing-lambda-ish form; v2 passes an explicit null-safe lambda
   with a typed parameter

v2 adds the 3 imports and fixes the UIAvatar call.
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhAssistantCard'
CD = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatDrawer.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch117v2 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + CD + '::' + body[:1400])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


t = (ROOT / CD).read_text(encoding='utf-8')
if MARK in t:
    print('batch117v2: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    applied = []
    existing = set(ln.strip() for ln in lines)

    # 1. imports (only if absent)
    imp_hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('import ')]
    if not imp_hits:
        fail('no import lines')
    last_imp = imp_hits[-1]
    need = [
        'import androidx.compose.material3.IconButton',
        'import me.rerere.rikkahub.data.datastore.getCurrentAssistant',
        'import me.rerere.rikkahub.data.datastore.getCurrentChatModel',
        'import me.rerere.rikkahub.data.model.Avatar',
    ]
    missing = [x for x in need if x not in existing]
    for j, imp in enumerate(missing):
        lines.insert(last_imp + 1 + j, imp + ' // ' + MARK)
    applied.append('imports+' + str(len(missing)))

    # 2. find BackupReminderCard close (same anchor as v1)
    BR = [i for i, ln in enumerate(lines) if ln.strip().startswith('BackupReminderCard(')]
    if len(BR) != 1:
        fail('BackupReminderCard count=' + str(len(BR)), lines, BR[0] if BR else 0)
    bi = BR[0]
    depth = 0
    br_close = -1
    for i in range(bi, len(lines)):
        for ch in lines[i]:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
        if depth <= 0 and i > bi:
            br_close = i
            break
    if br_close < 0:
        fail('BackupReminderCard close not found', lines, bi)

    d = ind(lines[bi])
    card = [
        d + '',
        d + '// ' + MARK + ': assistant card (Yuihub style)',
        d + 'Surface(',
        d + '    modifier = Modifier.fillMaxWidth(),',
        d + '    shape = MaterialTheme.shapes.medium,',
        d + '    color = MaterialTheme.colorScheme.surfaceContainerLow,',
        d + '    tonalElevation = 0.dp,',
        d + ') {',
        d + '    Row(',
        d + '        modifier = Modifier.padding(12.dp),',
        d + '        verticalAlignment = Alignment.CenterVertically,',
        d + '        horizontalArrangement = Arrangement.spacedBy(12.dp),',
        d + '    ) {',
        d + '        val cardAssistant = settings.getCurrentAssistant()',
        d + '        val cardAssistantName = cardAssistant.name.ifBlank { stringResource(R.string.assistant_page_default_assistant) }',
        d + '        UIAvatar(',
        d + '            name = cardAssistantName,',
        d + '            value = cardAssistant.avatar,',
        d + '            onUpdate = null,',
        d + '            modifier = Modifier.size(40.dp),',
        d + '        )',
        d + '        Column(modifier = Modifier.weight(1f)) {',
        d + '            Text(',
        d + '                text = cardAssistantName,',
        d + '                style = MaterialTheme.typography.titleSmall,',
        d + '                maxLines = 1,',
        d + '                overflow = TextOverflow.Ellipsis,',
        d + '            )',
        d + '            Text(',
        d + '                text = settings.getCurrentChatModel()?.displayName ?: "\u672a\u9009\u62e9\u6a21\u578b",',
        d + '                style = MaterialTheme.typography.labelSmall,',
        d + '                color = MaterialTheme.colorScheme.onSurfaceVariant,',
        d + '                maxLines = 1,',
        d + '                overflow = TextOverflow.Ellipsis,',
        d + '            )',
        d + '        }',
        d + '        IconButton(onClick = { }) {',
        d + '            Icon(HugeIcons.LookTop, contentDescription = "\u5207\u6362\u52a9\u624b", modifier = Modifier.size(20.dp))',
        d + '        }',
        d + '    }',
        d + '}',
    ]
    lines[br_close + 1:br_close + 1] = card
    applied.append('card')

    out = NL.join(lines)
    for need in [MARK, 'cardAssistant', 'getCurrentChatModel', 'IconButton', 'onUpdate = null']:
        if need not in out:
            fail('selfcheck missing: ' + need)
    if balance(out) != bal0:
        fail('balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

    (ROOT / CD).write_text(out, encoding='utf-8')
    print('batch117v2: OK (' + ', '.join(applied) + ')')

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch117: Step7 - assistant card at top of drawer (Yuihub style)

Adds a DrawerAssistantCard above the user avatar row: current assistant's
avatar + name + switch button (opens assistant picker). Matches Yuihub's
顶部用户头像/昵称/助手卡 pattern.

Five checks:
1. import: zero new (all components already imported in ChatDrawer.kt)
2. conflict: ChatDrawer.kt touched by batch74 (sidebar overhaul); anchor is
   between BackupReminderCard and the user avatar row - untouched by batch74
3. scope: inside ModalDrawerSheet Column
4. brackets: self-balanced
5. signature: unchanged
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhAssistantCard'
CD = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatDrawer.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch117 ' + str(msg)
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
    print('batch117: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    applied = []

    # Anchor: the BackupReminderCard block close, then the user avatar Row start
    # Find the BackupReminderCard( call
    BR = [i for i, ln in enumerate(lines) if ln.strip().startswith('BackupReminderCard(')]
    if len(BR) != 1:
        fail('BackupReminderCard count=' + str(len(BR)), lines, BR[0] if BR else 0)
    bi = BR[0]
    # find its closing ')' line
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
        d + '        val assistant = settings.getCurrentAssistant()',
        d + '        UIAvatar(',
        d + '            name = assistant.name.ifBlank { stringResource(R.string.assistant_page_default_assistant) },',
        d + '            value = assistant.avatar,',
        d + '            onUpdate = { },',
        d + '            modifier = Modifier.size(40.dp),',
        d + '        )',
        d + '        Column(modifier = Modifier.weight(1f)) {',
        d + '            Text(',
        d + '                text = assistant.name.ifBlank { stringResource(R.string.assistant_page_default_assistant) },',
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
        d + '        IconButton(onClick = { /* TODO: open assistant picker */ }) {',
        d + '            Icon(HugeIcons.LookTop, contentDescription = "\u5207\u6362\u52a9\u624b", modifier = Modifier.size(20.dp))',
        d + '        }',
        d + '    }',
        d + '}',
    ]
    lines[br_close + 1:br_close + 1] = card
    applied.append('card')

    out = NL.join(lines)
    for need in [MARK, 'getCurrentAssistant', 'UIAvatar']:
        if need not in out:
            fail('selfcheck missing: ' + need)
    if balance(out) != bal0:
        fail('balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

    (ROOT / CD).write_text(out, encoding='utf-8')
    print('batch117: OK (' + ', '.join(applied) + ')')

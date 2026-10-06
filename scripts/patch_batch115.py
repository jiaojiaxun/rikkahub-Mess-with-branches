#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch115 v3: cron dialog beautification - fix close match

v2 failed: cron field close is ')' (no comma), not '),'.
v3 uses `in ('),', ')')` to match both forms.

Adversarial checks:
- anchor 'onValueChange = { cronExpr = it },' exists in batch111 output ✓
- 'supportingText = {' exists ✓
- brace depth tracking: L251 '},' has '}' → depth 0 ✓
- close match: ')' no comma → v3 matches ✓
- chips block self-balanced ✓
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhCronBeautify'
SP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingScheduledJobsPage.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch115v3 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + SP + '::' + body[:1400])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


t = (ROOT / SP).read_text(encoding='utf-8')
if MARK in t:
    print('batch115v3: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    applied = []

    # 1. imports
    imp_hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('import ')]
    if not imp_hits:
        fail('no import lines')
    last_imp = imp_hits[-1]
    existing = set(ln.strip() for ln in lines)
    need = [
        'import androidx.compose.foundation.layout.Spacer',
        'import androidx.compose.foundation.layout.width',
        'import androidx.compose.material3.Surface',
    ]
    missing = [x for x in need if x not in existing]
    for j, imp in enumerate(missing):
        lines.insert(last_imp + 1 + j, imp + ' // ' + MARK)
    applied.append('imports+' + str(len(missing)))

    # 2. find cron field
    CRON_FIELD = 'onValueChange = { cronExpr = it },'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == CRON_FIELD]
    if len(hits) != 1:
        fail('cronExpr anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ci = hits[0]

    # 3. find supportingText = { after cron field
    st_idx = -1
    for j in range(ci + 1, min(ci + 10, len(lines))):
        if lines[j].strip() == 'supportingText = {':
            st_idx = j
            break
    if st_idx < 0:
        fail('supportingText not found after cronExpr', lines, ci)

    # 4. track brace depth to find supportingText close
    depth = 0
    st_close = -1
    for j in range(st_idx, len(lines)):
        for ch in lines[j]:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
        if depth <= 0 and j > st_idx:
            st_close = j
            break
    if st_close < 0:
        fail('supportingText close not found', lines, st_idx)

    # 5. find OutlinedTextField close ')' or '),'  ← v3 fix
    field_close = -1
    for j in range(st_close, min(st_close + 5, len(lines))):
        s = lines[j].strip()
        if s in (')', '),'):
            field_close = j
            break
    if field_close < 0:
        fail('cron field close not found', lines, st_close)

    # 6. insert chips after field close
    d = ind(lines[field_close])
    chips = [
        d + '',
        d + '// ' + MARK + ': cron preset chips',
        d + 'Text("\u5e38\u7528\u793a\u4f8b\uff1a", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)',
        d + 'Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {',
        d + '    listOf("0 9 * * *" to "\u6bcf\u5929 9:00", "0 * * * *" to "\u6bcf\u5c0f\u65f6", "0 9 * * 1" to "\u6bcf\u5468\u4e00 9:00", "*/30 * * * *" to "\u6bcf 30 \u5206\u949f").forEach { (cron, label) ->',
        d + '        Surface(',
        d + '            onClick = { cronExpr = cron },',
        d + '            shape = MaterialTheme.shapes.small,',
        d + '            color = MaterialTheme.colorScheme.secondaryContainer,',
        d + '        ) {',
        d + '            Text(',
        d + '                text = label,',
        d + '                style = MaterialTheme.typography.labelSmall,',
        d + '                modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),',
        d + '            )',
        d + '        }',
        d + '    }',
        d + '}',
    ]
    lines[field_close + 1:field_close + 1] = chips
    applied.append('chips')

    out = NL.join(lines)
    for need in [MARK, 'cronExpr', 'preset']:
        if need not in out:
            fail('selfcheck missing: ' + need)
    if balance(out) != bal0:
        fail('balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

    (ROOT / SP).write_text(out, encoding='utf-8')
    print('batch115v3: OK (' + ', '.join(applied) + ')')

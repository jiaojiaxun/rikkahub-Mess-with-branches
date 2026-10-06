#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch120 v2: fix Q literal + missing fillMaxSize import

v1 compile errors:
1. "Unresolved reference 'Q'" — the on_click handler body had a Python template
   variable Q that leaked as a literal into Kotlin code. The line was meant to be
   Kotlin string concatenation, not Python. Fixed by removing the bogus Q line.
2. "Unresolved reference 'fillMaxSize'" — ChatMessage.kt never imported it.

v2: fix the click-handler line to plain Kotlin (no Q), add fillMaxSize import.
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhAttachCard'
CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch120v2 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + CM + '::' + body[:1400])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def find_block_end(lines, start):
    depth = 0
    for i in range(start, len(lines)):
        for ch in lines[i]:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
        if depth <= 0 and i > start:
            return i
    return -1


def build_card_lines(d, icon_expr, name_expr, size_expr, pkg_expr):
    return [
        d + 'Surface(',
        d + '    tonalElevation = 2.dp,',
        d + '    onClick = {',
        d + '        val intent = Intent(Intent.ACTION_VIEW)',
        d + '        intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)',
        d + '        intent.data = FileProvider.getUriForFile(',
        d + '            context,',
        d + '            ' + pkg_expr + ',',
        d + '            part.url.toUri().toFile()',
        d + '        )',
        d + '        val chooserIndent = Intent.createChooser(intent, null)',
        d + '        context.startActivity(chooserIndent)',
        d + '    },',
        d + '    modifier = Modifier.fillMaxWidth(),',
        d + '    shape = RoundedCornerShape(16.dp),',
        d + '    color = MaterialTheme.colorScheme.surfaceContainerHigh,',
        d + ') {',
        d + '    Row(',
        d + '        modifier = Modifier.padding(12.dp),',
        d + '        verticalAlignment = Alignment.CenterVertically,',
        d + '        horizontalArrangement = Arrangement.spacedBy(12.dp),',
        d + '    ) {',
        d + '        Surface(',
        d + '            modifier = Modifier.size(44.dp),',
        d + '            shape = RoundedCornerShape(12.dp),',
        d + '            color = MaterialTheme.colorScheme.surfaceContainerHigh,',
        d + '        ) {',
        d + '            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {',
        d + '                ' + icon_expr,
        d + '            }',
        d + '        }',
        d + '        Column(modifier = Modifier.weight(1f)) {',
        d + '            Text(',
        d + '                text = ' + name_expr + ',',
        d + '                maxLines = 1,',
        d + '                overflow = TextOverflow.Ellipsis,',
        d + '                style = MaterialTheme.typography.titleSmall,',
        d + '            )',
        d + '            Text(',
        d + '                text = ' + size_expr + ',',
        d + '                maxLines = 1,',
        d + '                overflow = TextOverflow.Ellipsis,',
        d + '                style = MaterialTheme.typography.labelSmall,',
        d + '                color = MaterialTheme.colorScheme.onSurfaceVariant,',
        d + '            )',
        d + '        }',
        d + '        Surface(',
        d + '            modifier = Modifier.size(36.dp),',
        d + '            shape = CircleShape,',
        d + '            color = MaterialTheme.colorScheme.surfaceContainerHigh,',
        d + '        ) {',
        d + '            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {',
        d + '                Icon(',
        d + '                    imageVector = HugeIcons.Download01,',
        d + '                    contentDescription = null,',
        d + '                    modifier = Modifier.size(20.dp),',
        d + '                    tint = MaterialTheme.colorScheme.onSurfaceVariant,',
        d + '                )',
        d + '            }',
        d + '        }',
        d + '    }',
        d + '}',
    ]


t = (ROOT / CM).read_text(encoding='utf-8')
if MARK in t:
    print('batch120v2: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    applied = []
    existing = set(ln.strip() for ln in lines)

    # 1. imports (fillMaxSize + CircleShape + Download01 + fileSizeToString)
    imp_hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('import ')]
    if not imp_hits:
        fail('no import lines')
    last_imp = imp_hits[-1]
    need = [
        'import androidx.compose.foundation.layout.fillMaxSize',
        'import androidx.compose.foundation.shape.CircleShape',
        'import me.rerere.hugeicons.stroke.Download01',
        'import me.rerere.rikkahub.utils.fileSizeToString',
    ]
    missing = [x for x in need if x not in existing]
    for j, imp in enumerate(missing):
        lines.insert(last_imp + 1 + j, imp + ' // ' + MARK)
    applied.append('imports+' + str(len(missing)))

    # 2. Document block replacement
    DOC_ANCHOR = 'is UIMessagePart.Document -> {'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == DOC_ANCHOR]
    if len(hits) != 1:
        fail('Document anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    di = hits[0]
    d = ind(lines[di])
    doc_end = find_block_end(lines, di)
    if doc_end < 0:
        fail('Document block end not found', lines, di)
    # Kotlin string for package name: "${context.packageName}.fileprovider"
    pkg_expr = chr(34) + chr(36) + '{context.packageName}.fileprovider' + chr(34)
    doc_icon = 'Icon(imageVector = HugeIcons.File02, contentDescription = null, modifier = Modifier.size(24.dp))'
    doc_name = 'part.fileName'
    doc_size = 'part.fileName.substringAfterLast(\'.\', "file").uppercase() + " · " + runCatching { part.url.toUri().toFile().length().fileSizeToString() }.getOrDefault("未知大小")'
    new_doc = [d + 'is UIMessagePart.Document -> {'] + build_card_lines(d + '    ', doc_icon, doc_name, doc_size, pkg_expr) + [d + '}']
    lines[di:doc_end + 1] = new_doc
    applied.append('Document')

    # 3. Audio block replacement
    AUD_ANCHOR = 'is UIMessagePart.Audio -> {'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == AUD_ANCHOR]
    if len(hits) != 1:
        fail('Audio anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ai = hits[0]
    d = ind(lines[ai])
    aud_end = find_block_end(lines, ai)
    if aud_end < 0:
        fail('Audio block end not found', lines, ai)
    aud_icon = 'Icon(imageVector = HugeIcons.MusicNote03, contentDescription = null, modifier = Modifier.size(24.dp))'
    aud_name = 'part.url.toUri().toFile().name'
    aud_size = '"audio · " + runCatching { part.url.toUri().toFile().length().fileSizeToString() }.getOrDefault("未知大小")'
    new_aud = [d + 'is UIMessagePart.Audio -> {'] + build_card_lines(d + '    ', aud_icon, aud_name, aud_size, pkg_expr) + [d + '}']
    lines[ai:aud_end + 1] = new_aud
    applied.append('Audio')

    out = NL.join(lines)
    for need in [MARK, 'Download01', 'fileSizeToString', 'CircleShape', 'fillMaxSize']:
        if need not in out:
            fail('selfcheck missing: ' + need)
    if balance(out) != bal0:
        fail('balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

    (ROOT / CM).write_text(out, encoding='utf-8')
    print('batch120v2: OK (' + ', '.join(applied) + ')')

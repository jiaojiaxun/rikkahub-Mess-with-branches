#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch121: multi API key input block for provider settings - part B4

User request: below the API key field on the provider settings page, add a small
add button; tapping it appends a second input field, then third, fourth, fifth...

How it works: provider.apiKey stays a single String. The UI shows one field per
key and re-joins all values with newline separators when any field changes.
KeyRoulette already splits that string on whitespace/commas and rotates between
the parts, so no data-model change is needed.

Changes in ProviderConfigure.kt:
1. add missing imports (conditional on exact line presence)
2. replace every apiKey field with a call to the shared RhMultiApiKeyBlock
3. append RhMultiApiKeyBlock + helpers at the end of the file

Guards: marker rhMultiKey for idempotency; sites are matched by exact stripped
lines; unverifiable sites emit ::warning with context instead of blocking; the
final brace balance is compared against the original; at least 2 sites must be
replaced.
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BS = chr(92)
MARK = 'rhMultiKey'
PC = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/components/ProviderConfigure.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch121 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + PC + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def line_depth(ln):
    depth = 0
    in_str = False
    k = 0
    while k < len(ln):
        c = ln[k]
        if in_str:
            if c == BS:
                k += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        k += 1
    return depth


t = (ROOT / PC).read_text(encoding='utf-8')
if MARK in t:
    print('batch121: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)

    # ---- 1. imports ----
    imp_idx = [i for i, ln in enumerate(lines) if ln.strip().startswith('import ')]
    if not imp_idx:
        fail('no import lines')
    last_imp = imp_idx[-1]
    existing = set(ln.strip() for ln in lines)
    need = [
        'import androidx.compose.foundation.layout.Column',
        'import androidx.compose.foundation.layout.Row',
        'import androidx.compose.foundation.layout.Spacer',
        'import androidx.compose.foundation.layout.size',
        'import androidx.compose.foundation.layout.width',
        'import androidx.compose.material3.TextButton',
        'import androidx.compose.runtime.LaunchedEffect',
        'import me.rerere.hugeicons.stroke.Add01',
    ]
    missing = [x for x in need if x not in existing]
    for j, imp in enumerate(missing):
        lines.insert(last_imp + 1 + j, imp + ' // ' + MARK)

    # ---- 2. replace apiKey field sites (bottom-up so indices stay valid) ----
    hits = [i for i, ln in enumerate(lines) if ln.strip() == 'value = provider.apiKey,']
    if not hits:
        fail('no apiKey field sites found', lines, 0)

    replaced = 0
    skipped = []
    for hi in reversed(hits):
        ok = True
        otf = hi - 1
        if otf < 1 or lines[otf].strip() != 'OutlinedTextField(':
            ok = False
        if ok and hi + 1 < len(lines):
            if not lines[hi + 1].strip().startswith('onValueChange = { onEdit(provider.copy(apiKey'):
                ok = False
        if not ok:
            skipped.append(hi)
            continue
        depth = line_depth(lines[otf])
        close = -1
        for j in range(otf + 1, min(otf + 40, len(lines))):
            depth += line_depth(lines[j])
            if depth <= 0:
                close = j
                break
        if close < 0:
            skipped.append(hi)
            continue
        start = otf
        if lines[otf - 1].strip() == 'var keyVisible by remember { mutableStateOf(false) }':
            start = otf - 1
        d = ind(lines[start])
        new_call = [
            d + '// ' + MARK + ': one field per key; the add button appends another',
            d + 'RhMultiApiKeyBlock(',
            d + '    apiKey = provider.apiKey,',
            d + '    onApiKeyChange = { onEdit(provider.copy(apiKey = it)) },',
            d + ')',
        ]
        lines[start:close + 1] = new_call
        replaced += 1

    for hi in skipped:
        lo = max(0, hi - 2)
        hi2 = min(len(lines), hi + 3)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:80] for i in range(lo, hi2))
        print('::warning file=' + PC + '::batch121 skipped unverifiable apiKey site: ' + ctx[:1200])

    if replaced < 2:
        fail('replaced sites = ' + str(replaced) + ' (expected at least 2)', lines, 0)

    # ---- 3. append shared block ----
    block = [
        '',
        '// ' + MARK + ': shared multi-key input block for provider settings.',
        '// provider.apiKey stays a single String; one field is shown per key and all',
        '// values are re-joined with newline separators; KeyRoulette splits on',
        '// whitespace and commas, and rotates between the keys.',
        'private val RH_KEY_SPLIT_REGEX = Regex("[' + BS + BS + 's,]+")',
        '',
        'private fun rhParseApiKeys(raw: String): List<String> =',
        '    raw.split(RH_KEY_SPLIT_REGEX).map { it.trim() }.filter { it.isNotEmpty() }',
        '',
        '@Composable',
        'private fun RhMultiApiKeyBlock(',
        '    apiKey: String,',
        '    onApiKeyChange: (String) -> Unit,',
        ') {',
        '    var rhFields by remember { mutableStateOf(rhParseApiKeys(apiKey).ifEmpty { listOf("") }) }',
        '    var rhVisibleIndex by remember { mutableStateOf(-1) }',
        '    LaunchedEffect(apiKey) {',
        '        val rhCanonical = rhFields.map { it.trim() }.filter { it.isNotEmpty() }.joinToString("' + BS + 'n")',
        '        if (apiKey != rhCanonical) {',
        '            rhFields = rhParseApiKeys(apiKey).ifEmpty { listOf("") }',
        '        }',
        '    }',
        '    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {',
        '        rhFields.forEachIndexed { index, value ->',
        '            val rhLabel = stringResource(R.string.setting_provider_page_api_key) +',
        '                (if (rhFields.size > 1) " #" + (index + 1) else "")',
        '            OutlinedTextField(',
        '                value = value,',
        '                onValueChange = { newValue ->',
        '                    rhFields = rhFields.toMutableList().also { it[index] = newValue }',
        '                    onApiKeyChange(',
        '                        rhFields.map { it.trim() }.filter { it.isNotEmpty() }.joinToString("' + BS + 'n")',
        '                    )',
        '                },',
        '                label = { Text(rhLabel) },',
        '                modifier = Modifier.fillMaxWidth(),',
        '                maxLines = 3,',
        '                visualTransformation = if (rhVisibleIndex == index) VisualTransformation.None else PasswordVisualTransformation(),',
        '                trailingIcon = {',
        '                    IconButton(onClick = {',
        '                        rhVisibleIndex = if (rhVisibleIndex == index) -1 else index',
        '                    }) {',
        '                        Icon(',
        '                            if (rhVisibleIndex == index) HugeIcons.ViewOff else HugeIcons.View,',
        '                            contentDescription = stringResource(',
        '                                if (rhVisibleIndex == index) R.string.accessibility_hide_password',
        '                                else R.string.accessibility_show_password',
        '                            )',
        '                        )',
        '                    }',
        '                },',
        '            )',
        '        }',
        '        Row(',
        '            modifier = Modifier.fillMaxWidth(),',
        '            horizontalArrangement = Arrangement.End,',
        '        ) {',
        '            TextButton(onClick = { rhFields = rhFields + "" }) {',
        '                Icon(HugeIcons.Add01, contentDescription = null, modifier = Modifier.size(16.dp))',
        '                Spacer(modifier = Modifier.width(4.dp))',
        '                Text("\u589e\u52a0 API Key")',
        '            }',
        '        }',
        '    }',
        '}',
    ]
    out_lines = lines
    while out_lines and out_lines[-1].strip() == '':
        out_lines.pop()
    out_lines.extend(block)
    out_lines.append('')

    out = NL.join(out_lines)

    # ---- self checks ----
    for needcheck in [MARK, 'RhMultiApiKeyBlock(', 'rhParseApiKeys', 'RH_KEY_SPLIT_REGEX']:
        if needcheck not in out:
            fail('selfcheck missing: ' + needcheck)
    if out.count('RhMultiApiKeyBlock(') != replaced + 1:
        fail('call sites count mismatch: ' + str(out.count('RhMultiApiKeyBlock(')) + ' vs expected ' + str(replaced + 1))
    if balance(out) != bal0:
        fail('balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

    (ROOT / PC).write_text(out, encoding='utf-8')
    print('::notice::batch121 OK - replaced sites = ' + str(replaced) + ', imports added = ' + str(len(missing)))

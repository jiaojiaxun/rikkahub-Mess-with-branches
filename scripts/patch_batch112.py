#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch112 v5: fix Python SyntaxError in v4 (missing comma in list literal)

v4 died at import: L133
    d + 'streamOutput = streamOutput,'
    d + 'onUpdateStreamOutput = onUpdateStreamOutput,',
first line missing trailing comma inside a list literal -> SyntaxError.

v5 = v4 with the comma added. Everything else unchanged.
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhStreamToggle'
RP = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ReasoningPicker.kt'
CI = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ChatInput.kt'


def fail(msg, lines=None, around=-1, path=RP):
    body = 'batch112v5 ' + str(msg)
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


def param_list_end(lines, start):
    depth = 0
    for i in range(start, len(lines)):
        for ch in lines[i]:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
        if depth <= 0 and i > start:
            return i
    return -1


# ============================================================
# ReasoningPicker.kt
# ============================================================
t = (ROOT / RP).read_text(encoding='utf-8')
if MARK in t:
    print('batch112v5 RP: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    applied = []

    # A. import Switch
    IMP = 'import androidx.compose.material3.SliderDefaults'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == IMP]
    if len(hits) != 1:
        fail('SliderDefaults import count=' + str(len(hits)), lines, hits[0] if hits else 0)
    d = ind(lines[hits[0]])
    lines.insert(hits[0] + 1, d + 'import androidx.compose.material3.Switch // ' + MARK)
    applied.append('import')

    # B. ReasoningButton signature
    RB = 'fun ReasoningButton('
    hits = [i for i, ln in enumerate(lines) if ln.strip() == RB]
    if len(hits) != 1:
        fail('fun ReasoningButton count=' + str(len(hits)), lines, hits[0] if hits else 0)
    rbi = hits[0]
    rbe = param_list_end(lines, rbi)
    if rbe < 0:
        fail('ReasoningButton param list end not found', lines, rbi)
    d = ind(lines[rbe])
    lines.insert(rbe, d + '    streamOutput: Boolean = true, // ' + MARK)
    lines.insert(rbe + 1, d + '    onUpdateStreamOutput: (Boolean) -> Unit = {}, // ' + MARK)
    applied.append('btn-sig')

    # C. ReasoningPicker signature
    RPf = 'fun ReasoningPicker('
    hits = [i for i, ln in enumerate(lines) if ln.strip() == RPf]
    if len(hits) != 1:
        fail('fun ReasoningPicker count=' + str(len(hits)), lines, hits[0] if hits else 0)
    rpi = hits[0]
    rpe = param_list_end(lines, rpi)
    if rpe < 0:
        fail('ReasoningPicker param list end not found', lines, rpi)
    d = ind(lines[rpe])
    lines.insert(rpe, d + '    streamOutput: Boolean = true, // ' + MARK)
    lines.insert(rpe + 1, d + '    onUpdateStreamOutput: (Boolean) -> Unit = {}, // ' + MARK)
    applied.append('picker-sig')

    # D. ReasoningButton's ReasoningPicker call (comma fix)  <-- v4 bug here
    CALL = 'onUpdateReasoningLevel = onUpdateReasoningLevel'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == CALL]
    if len(hits) != 1:
        fail('picker call count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ci = hits[0]
    d = ind(lines[ci])
    lines[ci] = d + 'onUpdateReasoningLevel = onUpdateReasoningLevel,'
    new_args = [
        d + 'streamOutput = streamOutput,',
        d + 'onUpdateStreamOutput = onUpdateStreamOutput,',
    ]
    lines[ci + 1:ci + 1] = new_args
    applied.append('picker-call')

    # E. Switch row after Slider
    sh = [i for i, ln in enumerate(lines) if ln.strip() == 'Slider(']
    if len(sh) != 1:
        fail('Slider count=' + str(len(sh)), lines, sh[0] if sh else 0)
    si = sh[0]
    depth = 0
    se = -1
    for i in range(si, len(lines)):
        for ch in lines[i]:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
        if depth <= 0 and i > si:
            se = i
            break
    if se < 0:
        fail('Slider end not found', lines, si)
    d = ind(lines[si])
    switch_row = [
        d + '',
        d + '// ' + MARK + ': stream output toggle',
        d + 'Row(',
        d + '    modifier = Modifier.fillMaxWidth(),',
        d + '    verticalAlignment = Alignment.CenterVertically,',
        d + '    horizontalArrangement = Arrangement.SpaceBetween,',
        d + ') {',
        d + '    Column {',
        d + '        Text(',
        d + '            text = "\u6d41\u5f0f\u8f93\u51fa",',
        d + '            style = MaterialTheme.typography.bodyMedium,',
        d + '        )',
        d + '        Text(',
        d + '            text = "\u5173\u95ed\u540e\u7b49\u5f85\u5b8c\u6574\u56de\u590d\u518d\u663e\u793a",',
        d + '            style = MaterialTheme.typography.labelSmall,',
        d + '            color = MaterialTheme.colorScheme.onSurfaceVariant,',
        d + '        )',
        d + '    }',
        d + '    Switch(',
        d + '        checked = streamOutput,',
        d + '        onCheckedChange = onUpdateStreamOutput,',
        d + '    )',
        d + '}',
    ]
    lines[se + 1:se + 1] = switch_row
    applied.append('switch-row')

    out = NL.join(lines)
    for need in [MARK, 'Switch(', 'streamOutput: Boolean', 'onUpdateStreamOutput']:
        if need not in out:
            fail('RP selfcheck missing: ' + need)
    if balance(out) != bal0:
        fail('RP balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))
    if 'onUpdateReasoningLevel = onUpdateReasoningLevel' + NL in out:
        fail('picker call comma fix failed')

    (ROOT / RP).write_text(out, encoding='utf-8')
    print('batch112v5 RP: OK (' + ', '.join(applied) + ')')


# ============================================================
# ChatInput.kt
# ============================================================
t = (ROOT / CI).read_text(encoding='utf-8')
if MARK in t:
    print('batch112v5 CI: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)

    RB_ANCHOR = 'onUpdateReasoningLevel = {'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == RB_ANCHOR]
    if len(hits) != 1:
        fail('ChatInput ReasoningButton anchor count=' + str(len(hits)), lines, hits[0] if hits else 0, path=CI)
    ri = hits[0]
    close_idx = -1
    for j in range(ri + 1, min(ri + 5, len(lines))):
        if lines[j].strip() == '},':
            close_idx = j
            break
    if close_idx < 0:
        fail('onUpdateReasoningLevel closing not found', lines, ri, path=CI)
    d = ind(lines[close_idx])
    ci_new = [
        d + 'streamOutput = assistant.streamOutput, // ' + MARK,
        d + 'onUpdateStreamOutput = { enabled ->',
        d + '    onUpdateAssistant(assistant.copy(streamOutput = enabled))',
        d + '},',
    ]
    lines[close_idx + 1:close_idx + 1] = ci_new

    out = NL.join(lines)
    for need in [MARK, 'streamOutput = assistant.streamOutput', 'onUpdateStreamOutput']:
        if need not in out:
            fail('CI selfcheck missing: ' + need, path=CI)
    if balance(out) != bal0:
        fail('CI balance changed: ' + str(bal0) + ' -> ' + str(balance(out)), path=CI)

    (ROOT / CI).write_text(out, encoding='utf-8')
    print('batch112v5 CI: OK')

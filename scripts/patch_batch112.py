#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch112 v2: stream output toggle in ReasoningPicker - fix param injection

v1 failed: ReasoningPicker.kt L66 "Unresolved reference 'streamOutput' on
receiver of type '(ReasoningLevel) -> Unit'". Root cause: v1 inserted
streamOutput/onUpdateStreamOutput into BOTH ReasoningButton and
ReasoningPicker signatures (they share the same anchor text), causing the
ReasoningButton body to reference undefined variables.

v2: only modify ReasoningPicker's signature + call site. ReasoningButton
stays unchanged (it just passes through).

Changes:
  A. ReasoningPicker.kt: add Switch import
  B. ReasoningPicker.kt: add streamOutput/onUpdateStreamOutput params to
     ReasoningPicker signature ONLY (not ReasoningButton)
  C. ReasoningPicker.kt: add Switch row after Slider
  D. ChatInput.kt: pass streamOutput + onUpdateStreamOutput to ReasoningButton

Five checks:
1. import: add Switch import to ReasoningPicker.kt
2. conflict: ReasoningPicker.kt untouched by other patches; ChatInput.kt untouched
   in the ReasoningButton call region
3. scope: ReasoningPicker @Composable only
4. brackets: param additions comma-separated; Switch row self-balanced
5. signature: ReasoningPicker adds optional params (defaults for backward compat)
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhStreamToggle'
RP = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ReasoningPicker.kt'
CI = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ChatInput.kt'


def fail(msg, lines=None, around=-1, path=RP):
    body = 'batch112v2 ' + str(msg)
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
# A+B: ReasoningPicker.kt - add Switch import + params + Switch row
# ============================================================
t = (ROOT / RP).read_text(encoding='utf-8')
if MARK in t:
    print('batch112v2 RP: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    applied = []

    # A. Add Switch import after SliderDefaults import
    IMP_ANCHOR = 'import androidx.compose.material3.SliderDefaults'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == IMP_ANCHOR]
    if len(hits) != 1:
        fail('SliderDefaults import anchor count=' + str(len(hits)), lines, hits[0] if hits else 0, path=RP)
    d = ind(lines[hits[0]])
    lines.insert(hits[0] + 1, d + 'import androidx.compose.material3.Switch // ' + MARK)
    applied.append('import')

    # B. ReasoningPicker signature: add streamOutput + onUpdateStreamOutput
    # Anchor: 'fun ReasoningPicker(' line
    SIG_ANCHOR = 'fun ReasoningPicker('
    hits = [i for i, ln in enumerate(lines) if ln.strip() == SIG_ANCHOR]
    if len(hits) != 1:
        fail('ReasoningPicker anchor count=' + str(len(hits)), lines, hits[0] if hits else 0, path=RP)
    pi = hits[0]
    # Find the closing paren of the parameter list
    depth = 0
    param_end = -1
    for i in range(pi, len(lines)):
        for ch in lines[i]:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
        if depth <= 0 and i > pi:
            param_end = i
            break
    if param_end < 0:
        fail('ReasoningPicker param list end not found', lines, pi, path=RP)
    # Insert before the closing paren
    d = ind(lines[param_end])
    lines.insert(param_end, d + '    streamOutput: Boolean = true, // ' + MARK)
    lines.insert(param_end + 1, d + '    onUpdateStreamOutput: (Boolean) -> Unit = {}, // ' + MARK)
    applied.append('signature')

    # C. Add Switch row after Slider in the bottom sheet
    # Anchor: the closing of Slider block
    slider_hits = [i for i, ln in enumerate(lines) if ln.strip() == 'Slider(']
    if len(slider_hits) != 1:
        fail('Slider anchor count=' + str(len(slider_hits)), lines, slider_hits[0] if slider_hits else 0, path=RP)
    slider_i = slider_hits[0]
    depth = 0
    slider_end = -1
    for i in range(slider_i, len(lines)):
        for ch in lines[i]:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
        if depth <= 0 and i > slider_i:
            slider_end = i
            break
    if slider_end < 0:
        fail('Slider closing paren not found', lines, slider_i, path=RP)
    d = ind(lines[slider_i])
    switch_block = [
        d + '',
        d + '// ' + MARK + ': stream output toggle',
        d + 'Row(',
        d + '    modifier = Modifier.fillMaxWidth(),',
        d + '    verticalAlignment = Alignment.CenterVertically,',
        d + '    horizontalArrangement = Arrangement.SpaceBetween,',
        d + ') {',
        d + '    Column {',
        d + '        Text(',
        d + '            text = "流式输出",',
        d + '            style = MaterialTheme.typography.bodyMedium,',
        d + '        )',
        d + '        Text(',
        d + '            text = "关闭后等待完整回复再显示",',
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
    lines[slider_end + 1:slider_end + 1] = switch_block
    applied.append('switch-row')

    out = NL.join(lines)
    for need in [MARK, 'Switch(', 'streamOutput: Boolean', 'onUpdateStreamOutput']:
        if need not in out:
            fail('RP selfcheck missing: ' + need, path=RP)
    if balance(out) != bal0:
        fail('RP bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(out)), path=RP)

    (ROOT / RP).write_text(out, encoding='utf-8')
    print('batch112v2 RP: OK (' + ', '.join(applied) + ')')


# ============================================================
# D: ChatInput.kt - pass streamOutput + onUpdateStreamOutput to ReasoningButton
# ============================================================
t = (ROOT / CI).read_text(encoding='utf-8')
if MARK in t:
    print('batch112v2 CI: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)

    # Anchor: the ReasoningButton call - onUpdateReasoningLevel = {
    RB_ANCHOR = 'onUpdateReasoningLevel = {'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == RB_ANCHOR]
    if len(hits) != 1:
        fail('ChatInput ReasoningButton anchor count=' + str(len(hits)), lines, hits[0] if hits else 0, path=CI)
    ri = hits[0]
    d = ind(lines[ri])
    # Find the closing '},' of the onUpdateReasoningLevel lambda
    close_idx = -1
    for j in range(ri + 1, min(ri + 5, len(lines))):
        if lines[j].strip() == '},':
            close_idx = j
            break
    if close_idx < 0:
        fail('onUpdateReasoningLevel closing not found', lines, ri, path=CI)
    d = ind(lines[close_idx])
    lines.insert(close_idx + 1, d + 'streamOutput = assistant.streamOutput, // ' + MARK)
    lines.insert(close_idx + 2, d + 'onUpdateStreamOutput = { enabled ->')
    lines.insert(close_idx + 3, d + '    onUpdateAssistant(assistant.copy(streamOutput = enabled))')
    lines.insert(close_idx + 4, d + '},')

    out = NL.join(lines)
    for need in [MARK, 'streamOutput = assistant.streamOutput', 'onUpdateStreamOutput']:
        if need not in out:
            fail('CI selfcheck missing: ' + need, path=CI)
    if balance(out) != bal0:
        fail('CI bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(out)), path=CI)

    (ROOT / CI).write_text(out, encoding='utf-8')
    print('batch112v2 CI: OK')

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch112: add stream output toggle to ReasoningPicker bottom sheet

The stream output switch (assistant.streamOutput) was buried in
AssistantBasicPage (assistant detail settings). User wants it accessible
from the chat input's reasoning depth picker bottom sheet.

Adds a "流式输出" Switch row below the Slider in ReasoningPicker.
The toggle reads/writes assistant.streamOutput via onUpdateAssistant
(already available in ChatInput scope as onUpdateAssistant callback).

Changes to ReasoningPicker.kt:
  A. Add params: streamOutput: Boolean, onUpdateStreamOutput: (Boolean) -> Unit
  B. Add Switch row after Slider
  C. ChatInput.kt: pass streamOutput + onUpdateStreamOutput to ReasoningButton
  D. ReasoningButton: pass through to ReasoningPicker

Five checks:
1. import: add Switch to ReasoningPicker.kt (already has Material3 imports);
   ChatInput.kt zero new (Switch not needed - ReasoningButton handles it)
2. conflict: ReasoningPicker.kt untouched by any patch; ChatInput.kt untouched
   by any patch in the ReasoningButton call region
3. scope: ReasoningPicker @Composable / ChatInput @Composable
4. brackets: param additions comma-separated; Switch row self-balanced
5. signature: ReasoningButton/ReasoningPicker add optional params (defaults)
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhStreamToggle'
RP = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ReasoningPicker.kt'
CI = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ChatInput.kt'


def fail(msg, lines=None, around=-1, path=RP):
    body = 'batch112 ' + str(msg)
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
# A+B: ReasoningPicker.kt - add streamOutput params + Switch row
# ============================================================
t = (ROOT / RP).read_text(encoding='utf-8')
if MARK in t:
    print('batch112 RP: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    applied = []

    # A1. Add Switch import after Slider import
    SLIDER_IMP = 'import androidx.compose.material3.Slider'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == SLIDER_IMP]
    if len(hits) != 1:
        fail('Slider import anchor count=' + str(len(hits)), lines, hits[0] if hits else 0, path=RP)
    d = ind(lines[hits[0]])
    lines.insert(hits[0] + 1, d + 'import androidx.compose.material3.Switch // ' + MARK)
    applied.append('import')

    # A2. ReasoningPicker signature: add streamOutput + onUpdateStreamOutput params
    SIG_ANCHOR = 'onUpdateReasoningLevel: (ReasoningLevel) -> Unit,'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == SIG_ANCHOR]
    if len(hits) != 2:
        fail('onUpdateReasoningLevel anchor count=' + str(len(hits)) + ' (expected 2: ReasoningButton + ReasoningPicker)', lines, hits[0] if hits else 0, path=RP)
    # First occurrence = ReasoningButton, second = ReasoningPicker
    for hit_idx in sorted(hits, reverse=True):
        d = ind(lines[hit_idx])
        lines.insert(hit_idx + 1, d + 'streamOutput: Boolean = true, // ' + MARK)
        lines.insert(hit_idx + 2, d + 'onUpdateStreamOutput: (Boolean) -> Unit = {}, // ' + MARK)
    applied.append('signature')

    # A3. ReasoningButton: pass streamOutput/onUpdateStreamOutput to ReasoningPicker call
    # Anchor: onUpdateReasoningLevel = onUpdateReasoningLevel
    PICKER_CALL = 'onUpdateReasoningLevel = onUpdateReasoningLevel'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == PICKER_CALL]
    if len(hits) != 1:
        fail('ReasoningPicker call anchor count=' + str(len(hits)), lines, hits[0] if hits else 0, path=RP)
    d = ind(lines[hits[0]])
    lines.insert(hits[0] + 1, d + 'streamOutput = streamOutput, // ' + MARK)
    lines.insert(hits[0] + 2, d + 'onUpdateStreamOutput = onUpdateStreamOutput, // ' + MARK)
    applied.append('passthrough')

    # B. Add Switch row after Slider in ReasoningPicker bottom sheet
    # Anchor: the closing of Slider block - find Slider( then its closing )
    slider_hits = [i for i, ln in enumerate(lines) if ln.strip() == 'Slider(']
    if len(slider_hits) != 1:
        fail('Slider anchor count=' + str(len(slider_hits)), lines, slider_hits[0] if slider_hits else 0, path=RP)
    slider_i = slider_hits[0]
    # Find closing paren of Slider block
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
    for need in [MARK, 'Switch(', 'streamOutput', 'onUpdateStreamOutput']:
        if need not in out:
            fail('RP selfcheck missing: ' + need, path=RP)
    if balance(out) != bal0:
        fail('RP bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(out)), path=RP)

    (ROOT / RP).write_text(out, encoding='utf-8')
    print('batch112 RP: OK (' + ', '.join(applied) + ')')


# ============================================================
# C: ChatInput.kt - pass streamOutput to ReasoningButton
# ============================================================
t = (ROOT / CI).read_text(encoding='utf-8')
if MARK in t:
    print('batch112 CI: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)

    # Anchor: the ReasoningButton call in ChatInput
    # It has onUpdateReasoningLevel = { onUpdateAssistant(assistant.copy(reasoningLevel = it)) },
    # We add streamOutput = assistant.streamOutput, onUpdateStreamOutput = { onUpdateAssistant(assistant.copy(streamOutput = it)) }
    RB_ANCHOR = 'onUpdateReasoningLevel = {'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == RB_ANCHOR]
    if len(hits) != 1:
        fail('ChatInput ReasoningButton anchor count=' + str(len(hits)), lines, hits[0] if hits else 0, path=CI)
    ri = hits[0]
    d = ind(lines[ri])
    # The next lines should be: onUpdateAssistant(assistant.copy(reasoningLevel = it)) },
    # We insert after the closing of onUpdateReasoningLevel lambda
    # Find the closing '},' line
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
    applied_ci = ['passthrough']

    out = NL.join(lines)
    for need in [MARK, 'streamOutput = assistant.streamOutput', 'onUpdateStreamOutput']:
        if need not in out:
            fail('CI selfcheck missing: ' + need, path=CI)
    if balance(out) != bal0:
        fail('CI bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(out)), path=CI)

    (ROOT / CI).write_text(out, encoding='utf-8')
    print('batch112 CI: OK (' + ', '.join(applied_ci) + ')')

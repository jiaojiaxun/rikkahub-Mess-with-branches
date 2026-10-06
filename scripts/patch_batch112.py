#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch112 v4: stream output toggle - one-shot, all anchors on repo state

v1/v2/v3 all failed. Root causes accumulated:
- v1: params injected into wrong function via shared anchor
- v2: only ReasoningPicker changed, ReasoningButton (the call target) missed
- v3: call-site insert missed a comma on `onUpdateReasoningLevel = onUpdateReasoningLevel`
      (original line has NO trailing comma), so new args parsed as lambda body;
      v3 also dropped v2's ChatInput.kt change when overwriting the script.

v4 does everything in ONE script, all anchors based on the RAW repo state
(ReasoningPicker.kt has no rhStreamToggle marks; ChatInput.kt has none):

ReasoningPicker.kt:
  A. import Switch
  B. ReasoningButton signature: +2 params (scan to end of param list)
  C. ReasoningPicker signature: +2 params (scan to end of param list)
  D. ReasoningButton's ReasoningPicker call: replace the comma-less
     `onUpdateReasoningLevel = onUpdateReasoningLevel` line with
     `... = ...,` + 2 new arg lines
  E. Switch row after Slider
ChatInput.kt:
  F. pass streamOutput + onUpdateStreamOutput to ReasoningButton

Five checks + Python three checks (Q/NL vars, single-literal strings,
helper defined first, explicit exit(1)).
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhStreamToggle'
RP = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ReasoningPicker.kt'
CI = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ChatInput.kt'


def fail(msg, lines=None, around=-1, path=RP):
    body = 'batch112v4 ' + str(msg)
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
    '''Given the index of a `fun Foo(` line, return the index of the line
    containing the matching closing paren (depth returns to 0).'''
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
    print('batch112v4 RP: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    applied = []

    # A. import Switch after SliderDefaults
    IMP = 'import androidx.compose.material3.SliderDefaults'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == IMP]
    if len(hits) != 1:
        fail('SliderDefaults import count=' + str(len(hits)), lines, hits[0] if hits else 0)
    d = ind(lines[hits[0]])
    lines.insert(hits[0] + 1, d + 'import androidx.compose.material3.Switch // ' + MARK)
    applied.append('import')

    # B. ReasoningButton signature: add params
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

    # C. ReasoningPicker signature: add params (re-find after B shifted lines)
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

    # D. ReasoningButton's ReasoningPicker call: comma fix
    #    Original line (no trailing comma):
    #        onUpdateReasoningLevel = onUpdateReasoningLevel
    CALL = 'onUpdateReasoningLevel = onUpdateReasoningLevel'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == CALL]
    if len(hits) != 1:
        fail('picker call count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ci = hits[0]
    d = ind(lines[ci])
    lines[ci] = d + 'onUpdateReasoningLevel = onUpdateReasoningLevel,'
    lines[ci + 1:ci + 1] = [
        d + 'streamOutput = streamOutput,'
        d + 'onUpdateStreamOutput = onUpdateStreamOutput,',
    ]
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
    lines[se + 1:se + 1] = [
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
    applied.append('switch-row')

    out = NL.join(lines)
    for need in [MARK, 'Switch(', 'streamOutput: Boolean', 'onUpdateStreamOutput']:
        if need not in out:
            fail('RP selfcheck missing: ' + need)
    if balance(out) != bal0:
        fail('RP balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))
    # comma fix verification
    if 'onUpdateReasoningLevel = onUpdateReasoningLevel\n' in out:
        fail('picker call comma fix failed')

    (ROOT / RP).write_text(out, encoding='utf-8')
    print('batch112v4 RP: OK (' + ', '.join(applied) + ')')


# ============================================================
# ChatInput.kt
# ============================================================
t = (ROOT / CI).read_text(encoding='utf-8')
if MARK in t:
    print('batch112v4 CI: already applied')
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
    lines.insert(close_idx + 1, d + 'streamOutput = assistant.streamOutput, // ' + MARK)
    lines.insert(close_idx + 2, d + 'onUpdateStreamOutput = { enabled ->')
    lines.insert(close_idx + 3, d + '    onUpdateAssistant(assistant.copy(streamOutput = enabled))')
    lines.insert(close_idx + 4, d + '},')

    out = NL.join(lines)
    for need in [MARK, 'streamOutput = assistant.streamOutput', 'onUpdateStreamOutput']:
        if need not in out:
            fail('CI selfcheck missing: ' + need, path=CI)
    if balance(out) != bal0:
        fail('CI balance changed: ' + str(bal0) + ' -> ' + str(balance(out)), path=CI)

    (ROOT / CI).write_text(out, encoding='utf-8')
    print('batch112v4 CI: OK')

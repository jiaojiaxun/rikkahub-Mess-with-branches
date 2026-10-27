#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch290 v9: line-oriented drawer polish.

#522/#523 both failed before Kotlin with Python SyntaxError at a multi-line
parenthesized expression after the CI sed rewrite. v9 removes that whole
class of failure: no multi-line parenthesized expressions, no raw-string
ambiguity, no exit(0) literal, and no full-file Kotlin duplication.
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
BS = chr(92)
MARK = 'rhDrawer290'
DIAG = 'ci_diag_batch290.txt'
DRAWER = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/RhThoughtDrawer.kt'
REASON = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageReasoning.kt'
TOOLS = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageTools.kt'
report = []
failures = []


def note(message):
    report.append(str(message)[:900])


def fail(message):
    failures.append(str(message)[:300])
    report.append('FAIL ' + str(message)[:420])


def lines_of(text):
    return text.split(NL)


def text_of(lines):
    out = ''
    for i, line in enumerate(lines):
        if i:
            out += NL
        out += line
    return out


def indent_of(line):
    stripped = line.lstrip()
    return line[:len(line) - len(stripped)]


def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


def write(rel, text):
    (ROOT / rel).write_text(text, encoding='utf-8')


def find_one(lines, predicate, label):
    hits = [i for i, line in enumerate(lines) if predicate(line)]
    if len(hits) != 1:
        fail(label + ' count=' + str(len(hits)))
        return -1
    return hits[0]


def replace_line(lines, predicate, make_line, label):
    idx = find_one(lines, predicate, label)
    if idx < 0:
        return lines
    lines[idx] = indent_of(lines[idx]) + make_line(indent_of(lines[idx]))
    return lines


def insert_after(lines, predicate, new_lines, label):
    idx = find_one(lines, predicate, label)
    if idx < 0:
        return lines
    base = indent_of(lines[idx])
    block = [base + ln if ln else ln for ln in new_lines]
    return lines[:idx + 1] + block + lines[idx + 1:]


def replace_block(lines, predicate, old_tail, new_block, label):
    start = find_one(lines, predicate, label)
    if start < 0:
        return lines
    end = start + len(old_tail)
    got = [ln.strip() for ln in lines[start:end]]
    if got != old_tail:
        fail(label + ' block mismatch: ' + repr(got[:3]))
        return lines
    base = indent_of(lines[start])
    block = [base + ln if ln else ln for ln in new_block]
    return lines[:start] + block + lines[end:]


def balanced(text):
    return text.count('(') == text.count(')') and text.count('{') == text.count('}') and text.count('[') == text.count(']')


def part_drawer():
    lines = lines_of(read(DRAWER))
    if any(MARK in line for line in lines):
        note('drawer already at 290')
        return
    if find_one(lines, lambda ln: ln.strip() == 'fun RhThoughtDrawer(', 'drawer fun') < 0:
        return

    # Down chevron for expanded rows.
    lines = replace_line(
        lines,
        lambda ln: ln.strip() == 'import me.rerere.hugeicons.stroke.ArrowUp01',
        lambda ind: 'import me.rerere.hugeicons.stroke.ArrowDown01',
        'drawer arrow import',
    )
    for i, line in enumerate(lines):
        if 'HugeIcons.ArrowUp01' in line:
            lines[i] = line.replace('HugeIcons.ArrowUp01', 'HugeIcons.ArrowDown01')
    for i, line in enumerate(lines):
        if '.background(MaterialTheme.colorScheme.surfaceContainerHigh)' in line:
            lines[i] = line.replace('surfaceContainerHigh', 'surfaceContainerHighest')

    lines = replace_line(
        lines,
        lambda ln: ln.strip() == 'modifier = Modifier.weight(1f, fill = false),',
        lambda ind: 'modifier = Modifier.weight(1f),',
        'drawer header weight',
    )

    lines = replace_block(
        lines,
        lambda ln: ln.strip() == 'if (groupOpened) {',
        [
            'if (groupOpened) {',
            'Column(modifier = Modifier.fillMaxWidth()) {',
            'steps.fastForEach { step ->',
            'scope.content(step)',
            '}',
            '}',
            '}',
        ],
        [
            'Column(modifier = Modifier.fillMaxWidth()) {',
            'steps.fastForEach { step ->',
            'if (step is ThinkingStep.ReasoningStep || groupOpened) {',
            'scope.content(step)',
            '}',
            '}',
            '}',
        ],
        'group/reasoning visibility',
    )

    lines = insert_after(
        lines,
        lambda ln: ln.strip() == 'label: String = "",',
        ['onExpand: (() -> Unit)? = null,', 'previewLimit: Int = 0,'],
        'json block parameters',
    )

    lines = replace_block(
        lines,
        lambda ln: ln.strip() == 'val body = text.trim()',
        ['val body = text.trim()', 'if (body.isEmpty()) {', 'return', '}'],
        [
            'val raw = text.trim()',
            'if (raw.isEmpty()) {',
            'return',
            '}',
            'val shown = if (previewLimit > 0 && raw.length > previewLimit) {',
            'raw.take(previewLimit) + ' + Q + ' ...' + Q,
            '} else {',
            'raw',
            '}',
        ],
        'json preview body',
    )
    lines = replace_line(
        lines,
        lambda ln: ln.strip() == 'text = body,',
        lambda ind: 'text = shown,',
        'json preview text',
    )

    # Add click-to-expand only to the payload block (first surfaceContainerHighest
    # background after the 14.dp payload corner), not to the small pill.
    payload_bg = -1
    for i, line in enumerate(lines):
        if 'RoundedCornerShape(14.dp)' in line:
            for j in range(i + 1, min(i + 5, len(lines))):
                if '.background(MaterialTheme.colorScheme.surfaceContainerHighest)' in lines[j]:
                    payload_bg = j
                    break
            break
    if payload_bg < 0:
        fail('payload background anchor missing')
        return
    base = indent_of(lines[payload_bg])
    modifier_block = [
        '.then(',
        'if (onExpand != null) {',
        'Modifier.clickable { onExpand() }',
        '} else {',
        'Modifier',
        '}',
        ')',
    ]
    lines = lines[:payload_bg + 1] + [base + ln for ln in modifier_block] + lines[payload_bg + 1:]

    lines = replace_block(
        lines,
        lambda ln: ln.strip() == 'private fun rhStepsStartMillis(steps: List<ThinkingStep>): Long? {',
        [
            'private fun rhStepsStartMillis(steps: List<ThinkingStep>): Long? {',
            'return steps.filterIsInstance<ThinkingStep.ReasoningStep>()',
            '.map { it.reasoning.createdAt.toEpochMilliseconds() }',
            '.minOrNull()',
            '}',
        ],
        [
            'private fun rhStepsStartMillis(steps: List<ThinkingStep>): Long? {',
            'val candidates = mutableListOf<Long>()',
            'steps.filterIsInstance<ThinkingStep.ReasoningStep>().forEach { step ->',
            'candidates.add(step.reasoning.createdAt.toEpochMilliseconds())',
            '}',
            'steps.filterIsInstance<ThinkingStep.ToolStep>().forEach { step ->',
            'step.tool.executionStartedAt?.let { stamp ->',
            'candidates.add(stamp)',
            '}',
            '}',
            'return candidates.minOrNull()',
            '}',
        ],
        'tool start time',
    )

    package_idx = find_one(
        lines,
        lambda ln: ln.strip() == 'package me.rerere.rikkahub.ui.components.message',
        'drawer package',
    )
    if package_idx < 0:
        return
    lines.insert(package_idx + 1, '// ' + MARK)

    text = text_of(lines)
    if not balanced(text):
        fail('drawer unbalanced after edits')
        return
    for token in ['ArrowDown01', 'step is ThinkingStep.ReasoningStep || groupOpened',
                  'onExpand: (() -> Unit)? = null', 'previewLimit: Int = 0',
                  'executionStartedAt', 'surfaceContainerHighest']:
        if token not in text:
            fail('drawer missing ' + token)
            return
    if 'ArrowUp01' in text:
        fail('drawer still has ArrowUp01')
        return
    write(DRAWER, text)
    note('drawer OK: line-oriented polish')


def part_reasoning():
    lines = lines_of(read(REASON))
    if any(MARK in line for line in lines):
        note('reasoning already at 290')
        return
    lines = replace_line(
        lines,
        lambda ln: ln.strip() == 'if (showThinkingTitle && state.duration > 0.seconds) {',
        lambda ind: 'if (!plainLabel && showThinkingTitle && state.duration > 0.seconds) { // ' + MARK,
        'reasoning extra guard',
    )
    text = text_of(lines)
    if MARK not in text:
        return
    write(REASON, text)
    note('reasoning OK: plain label hides seconds')


def part_tools():
    lines = lines_of(read(TOOLS))
    if any(MARK in line for line in lines):
        note('tools already at 290')
        return
    start = find_one(
        lines,
        lambda ln: ln.strip() == 'private fun rhToolFaviconUrl(tool: UIMessagePart.Tool): String? {',
        'favicon function start',
    )
    if start < 0:
        return
    end = -1
    for i in range(start + 1, len(lines)):
        if lines[i].strip() == '}' and indent_of(lines[i]) == '':
            end = i
            break
    if end < 0:
        fail('favicon function end missing')
        return
    new_fn = [
        'private fun rhToolFaviconUrl(tool: UIMessagePart.Tool): String? {',
        '    val args = runCatching { tool.inputAsJson() as? JsonObject }.getOrNull()',
        '    val direct = args?.get(' + Q + 'url' + Q + ')?.jsonPrimitiveOrNull?.contentOrNull',
        '    if (direct != null && direct.startsWith(' + Q + 'http' + Q + ')) {',
        '        return direct',
        '    }',
        '    val outputText = tool.output.filterIsInstance<UIMessagePart.Text>()',
        '        .joinToString(' + Q + BS + 'n' + Q + ') { it.text }',
        '    val content = runCatching { JsonInstant.parseToJsonElement(outputText) }.getOrNull()',
        '    val root = content as? JsonObject ?: return null',
        '    val items = root.get(' + Q + 'items' + Q + ') as? kotlinx.serialization.json.JsonArray ?: return null',
        '    val first = items.firstOrNull() as? JsonObject ?: return null',
        '    val url = first.get(' + Q + 'url' + Q + ') as? JsonPrimitive ?: return null',
        '    return url.content.takeIf { it.startsWith(' + Q + 'http' + Q + ') }',
        '}',
    ]
    lines = lines[:start] + new_fn + lines[end + 1:]

    lines = insert_after(
        lines,
        lambda ln: ln.strip() == 'text = tool.input,',
        ['previewLimit = 1200, // ' + MARK],
        'args preview',
    )
    lines = insert_after(
        lines,
        lambda ln: ln.strip() == 'showExpandIcon = true, // rhDrawer289',
        [
            'onExpand = if (hasResultDetail) ({ showResult = true }) else null, // ' + MARK,
            'previewLimit = 2400, // ' + MARK,
        ],
        'result preview and expand',
    )

    text = text_of(lines)
    if not balanced(text):
        fail('tools unbalanced after edits')
        return
    for token in ['kotlinx.serialization.json.JsonArray', 'previewLimit = 1200',
                  'previewLimit = 2400', 'onExpand = if (hasResultDetail)']:
        if token not in text:
            fail('tools missing ' + token)
            return
    write(TOOLS, text)
    note('tools OK: safe favicon, preview caps, detail callback')


def main():
    for name, fn in [('drawer', part_drawer), ('reasoning', part_reasoning), ('tools', part_tools)]:
        try:
            fn()
            note(name + ' DONE')
        except Exception as exc:  # noqa: BLE001
            fail(name + ' EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
    body = NL.join(report) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:  # noqa: BLE001
        print('::error::batch290 diag write failed ' + str(exc)[:200])
    for line in report:
        print('::error::batch290 ' + str(line)[:800])
    if failures:
        print('::error::batch290 FAILED count=' + str(len(failures)))
        raise SystemExit(1)
    print('batch290: OK')


main()
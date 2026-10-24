#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch290 v6: minimal anchored polish on top of batch289.

This deliberately does NOT carry a second full copy of RhThoughtDrawer.kt.
The CI chain has already applied 286 and 289 before this script; edit only
the verified anchors in that tree. This avoids whole-file replacement
mistakes and keeps the patch small and reviewable.

All edits are idempotent and each file is written once, after its checks.
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
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


def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


def write(rel, text):
    (ROOT / rel).write_text(text, encoding='utf-8')


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        fail(label + ' count=' + str(count))
        return text
    return text.replace(old, new, 1)


def insert_after_line(text, anchor, addition, label):
    if addition.strip() in text:
        return text
    lines = text.split(NL)
    hits = [i for i, line in enumerate(lines) if line.strip() == anchor.strip()]
    if len(hits) != 1:
        fail(label + ' anchor count=' + str(len(hits)))
        return text
    i = hits[0]
    indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    lines.insert(i + 1, indent + addition)
    return NL.join(lines)


def balanced(text):
    return (text.count('(') == text.count(')') and
            text.count('{') == text.count('}') and
            text.count('[') == text.count(']'))


def part_drawer():
    text = read(DRAWER)
    if MARK in text:
        note('drawer already at 290')
        return
    if 'rhDrawer289' not in text:
        fail('drawer prerequisite rhDrawer289 missing')
        return
    original = text
    text = text.replace('import me.rerere.hugeicons.stroke.ArrowUp01',
                        'import me.rerere.hugeicons.stroke.ArrowDown01')
    text = text.replace('HugeIcons.ArrowUp01', 'HugeIcons.ArrowDown01')
    text = text.replace('.background(MaterialTheme.colorScheme.surfaceContainerHigh)',
                        '.background(MaterialTheme.colorScheme.surfaceContainerHighest)')
    text = replace_once(text, 'modifier = Modifier.weight(1f, fill = false),',
                        'modifier = Modifier.weight(1f),', 'drawer header weight')
    text = replace_once(text, '    label: String = "",\n',
                        '    label: String = "",\n    onExpand: (() -> Unit)? = null,\n    previewLimit: Int = 0,\n',
                        'json block parameters')
    old_body = '''    val body = text.trim()
    if (body.isEmpty()) {
        return
    }'''
    new_body = '''    val raw = text.trim()
    if (raw.isEmpty()) {
        return
    }
    val shown = if (previewLimit > 0 && raw.length > previewLimit) {
        raw.take(previewLimit) + " ..."
    } else {
        raw
    }'''
    text = replace_once(text, old_body, new_body, 'json preview body')
    text = replace_once(text, '            text = body,', '            text = shown,', 'json preview text')
    old_modifier = '''            .background(MaterialTheme.colorScheme.surfaceContainerHighest)
            .padding(horizontal = 12.dp, vertical = 10.dp),'''
    new_modifier = '''            .background(MaterialTheme.colorScheme.surfaceContainerHighest)
            .then(
                if (onExpand != null) {
                    Modifier.clickable { onExpand() }
                } else {
                    Modifier
                }
            )
            .padding(horizontal = 12.dp, vertical = 10.dp),'''
    text = replace_once(text, old_modifier, new_modifier, 'json expand modifier')
    old_start = '''private fun rhStepsStartMillis(steps: List<ThinkingStep>): Long? {
    return steps.filterIsInstance<ThinkingStep.ReasoningStep>()
        .map { it.reasoning.createdAt.toEpochMilliseconds() }
        .minOrNull()
}'''
    new_start = '''private fun rhStepsStartMillis(steps: List<ThinkingStep>): Long? {
    val candidates = mutableListOf<Long>()
    steps.filterIsInstance<ThinkingStep.ReasoningStep>().forEach { step ->
        candidates.add(step.reasoning.createdAt.toEpochMilliseconds())
    }
    steps.filterIsInstance<ThinkingStep.ToolStep>().forEach { step ->
        step.tool.executionStartedAt?.let { stamp ->
            candidates.add(stamp)
        }
    }
    return candidates.minOrNull()
}'''
    text = replace_once(text, old_start, new_start, 'tool start time')
    text = text.replace('package me.rerere.rikkahub.ui.components.message\n',
                        'package me.rerere.rikkahub.ui.components.message\n\n// rhDrawer290\n', 1)
    if text == original:
        fail('drawer no changes produced')
        return
    if not balanced(text):
        fail('drawer unbalanced after edits')
        return
    for token in ['ArrowDown01', 'onExpand: (() -> Unit)? = null',
                  'previewLimit: Int = 0', 'executionStartedAt', 'surfaceContainerHighest']:
        if token not in text:
            fail('drawer missing ' + token)
            return
    if 'ArrowUp01' in text:
        fail('drawer still has ArrowUp01')
        return
    write(DRAWER, text)
    note('drawer OK: anchored polish')


def part_reasoning():
    text = read(REASON)
    if MARK in text:
        note('reasoning already at 290')
        return
    old = 'if (showThinkingTitle && state.duration > 0.seconds) {'
    new = 'if (!plainLabel && showThinkingTitle && state.duration > 0.seconds) { // ' + MARK
    text = replace_once(text, old, new, 'reasoning extra guard')
    if MARK not in text:
        return
    write(REASON, text)
    note('reasoning OK: plain label hides seconds')


def part_tools():
    text = read(TOOLS)
    if MARK in text:
        note('tools already at 290')
        return
    original = text
    start_marker = 'private fun rhToolFaviconUrl(tool: UIMessagePart.Tool): String? {'
    start = text.find(start_marker)
    if start < 0:
        fail('favicon function missing')
        return
    end = text.find('\n}\n', start)
    if end < 0:
        fail('favicon function end missing')
        return
    end += 3
    new_function = '''private fun rhToolFaviconUrl(tool: UIMessagePart.Tool): String? {
    val args = runCatching { tool.inputAsJson() as? JsonObject }.getOrNull()
    val direct = args?.get("url")?.jsonPrimitiveOrNull?.contentOrNull
    if (direct != null && direct.startsWith("http")) {
        return direct
    }
    val content = runCatching {
        JsonInstant.parseToJsonElement(
            tool.output.filterIsInstance<UIMessagePart.Text>().joinToString(" ") { it.text }
        )
    }.getOrNull()
    val root = content as? JsonObject ?: return null
    val items = root.get("items") as? kotlinx.serialization.json.JsonArray ?: return null
    val first = items.firstOrNull() as? JsonObject ?: return null
    val url = first.get("url") as? JsonPrimitive ?: return null
    return url.content.takeIf { it.startsWith("http") }
}'''
    text = text[:start] + new_function + text[end:]
    text = insert_after_line(text, 'text = tool.input,', 'previewLimit = 1200, // ' + MARK, 'args preview')
    result_anchor = 'text = tool.output.filterIsInstance<UIMessagePart.Text>().joinToString("\\n") { it.text },'
    if result_anchor not in text:
        fail('result text anchor missing')
        return
    text = text.replace(result_anchor, result_anchor + NL + '        previewLimit = 2400, // ' + MARK, 1)
    expand_anchor = 'showExpandIcon = true, // rhDrawer289'
    if expand_anchor not in text:
        fail('expand icon anchor missing')
        return
    text = text.replace(expand_anchor, expand_anchor + NL +
                        '        onExpand = if (hasResultDetail) ({ showResult = true }) else null, // ' + MARK, 1)
    if text == original:
        fail('tools no changes produced')
        return
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
        sys.exit(1)
    print('batch290: OK')


main()
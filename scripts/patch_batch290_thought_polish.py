#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch290 v7: minimal anchored drawer polish.

Runs after batch286/289 in the CI chain. No duplicate full Kotlin file.
Each source file is checked before a single write; all edits are idempotent.

UI rules:
- expanded chevrons point down; opened levels use solid dots;
- the group drawer controls only tool steps, never hides reasoning steps;
- reasoning plainLabel hides the seconds in the extra slot;
- result blocks open the existing detail sheet;
- favicon parsing is shape-safe and JsonArray is fully qualified;
- preview strings are capped before Compose layout;
- Tool.executionStartedAt supplies a start time for tool-only blocks.
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


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        fail(label + ' count=' + str(count))
        return text
    return text.replace(old, new, 1)


def insert_after(text, anchor, addition, label):
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
            text.count('[') == text.count(']')


def part_drawer():
    text = read(DRAWER)
    if MARK in text:
        note('drawer already at 290')
        return
    if 'fun RhThoughtDrawer(' not in text or 'fun RhToolJsonBlock(' not in text:
        fail('drawer prerequisite missing')
        return
    text = text.replace('import me.rerere.hugeicons.stroke.ArrowUp01',
                        'import me.rerere.hugeicons.stroke.ArrowDown01')
    text = text.replace('HugeIcons.ArrowUp01', 'HugeIcons.ArrowDown01')
    text = text.replace('.background(MaterialTheme.colorScheme.surfaceContainerHigh)',
                        '.background(MaterialTheme.colorScheme.surfaceContainerHighest)')
    text = replace_once(text, 'modifier = Modifier.weight(1f, fill = false),',
                        'modifier = Modifier.weight(1f),', 'drawer header weight')

    # A group is a drawer for tools, not a second switch for reasoning.
    old_group = '''                if (groupOpened) {
                    Column(modifier = Modifier.fillMaxWidth()) {
                        steps.fastForEach { step ->
                            scope.content(step)
                        }
                    }
                }'''
    new_group = '''                Column(modifier = Modifier.fillMaxWidth()) {
                    steps.fastForEach { step ->
                        if (step is ThinkingStep.ReasoningStep || groupOpened) {
                            scope.content(step)
                        }
                    }
                }'''
    text = replace_once(text, old_group, new_group, 'group/reasoning visibility')

    text = replace_once(text, '    label: String = "",\n',
                        '    label: String = "",\n    onExpand: (() -> Unit)? = null,\n    previewLimit: Int = 0,\n',
                        'json block parameters')
    text = replace_once(text, '''    val body = text.trim()
    if (body.isEmpty()) {
        return
    }''', '''    val raw = text.trim()
    if (raw.isEmpty()) {
        return
    }
    val shown = if (previewLimit > 0 && raw.length > previewLimit) {
        raw.take(previewLimit) + " ..."
    } else {
        raw
    }''', 'json preview body')
    text = replace_once(text, '            text = body,', '            text = shown,', 'json preview text')
    text = replace_once(text, '''            .background(MaterialTheme.colorScheme.surfaceContainerHighest)
            .padding(horizontal = 12.dp, vertical = 10.dp),''',
                        '''            .background(MaterialTheme.colorScheme.surfaceContainerHighest)
            .then(
                if (onExpand != null) {
                    Modifier.clickable { onExpand() }
                } else {
                    Modifier
                }
            )
            .padding(horizontal = 12.dp, vertical = 10.dp),''',
                        'json expand modifier')
    text = replace_once(text, '''private fun rhStepsStartMillis(steps: List<ThinkingStep>): Long? {
    return steps.filterIsInstance<ThinkingStep.ReasoningStep>()
        .map { it.reasoning.createdAt.toEpochMilliseconds() }
        .minOrNull()
}''', '''private fun rhStepsStartMillis(steps: List<ThinkingStep>): Long? {
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
}''', 'tool start time')
    text = text.replace('package me.rerere.rikkahub.ui.components.message\n',
                        'package me.rerere.rikkahub.ui.components.message\n\n// rhDrawer290\n', 1)
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
    (ROOT / DRAWER).write_text(text, encoding='utf-8')
    note('drawer OK: anchored polish and independent reasoning rows')


def part_reasoning():
    text = read(REASON)
    if MARK in text:
        note('reasoning already at 290')
        return
    text = replace_once(text, 'if (showThinkingTitle && state.duration > 0.seconds) {',
                        'if (!plainLabel && showThinkingTitle && state.duration > 0.seconds) { // ' + MARK,
                        'reasoning extra guard')
    if MARK not in text:
        return
    (ROOT / REASON).write_text(text, encoding='utf-8')
    note('reasoning OK: plain label hides seconds')


def part_tools():
    text = read(TOOLS)
    if MARK in text:
        note('tools already at 290')
        return
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
    val outputText = tool.output.filterIsInstance<UIMessagePart.Text>()
        .joinToString("\\n") { it.text }
    val content = runCatching { JsonInstant.parseToJsonElement(outputText) }.getOrNull()
    val root = content as? JsonObject ?: return null
    val items = root.get("items") as? kotlinx.serialization.json.JsonArray ?: return null
    val first = items.firstOrNull() as? JsonObject ?: return null
    val url = first.get("url") as? JsonPrimitive ?: return null
    return url.content.takeIf { it.startsWith("http") }
}'''
    text = text[:start] + new_function + text[end:]
    text = insert_after(text, 'text = tool.input,', 'previewLimit = 1200, // ' + MARK, 'args preview')
    text = insert_after(text, 'showExpandIcon = true, // rhDrawer289',
                        'previewLimit = 2400, // ' + MARK, 'result preview')
    text = insert_after(text, 'showExpandIcon = true, // rhDrawer289',
                        'onExpand = if (hasResultDetail) ({ showResult = true }) else null, // ' + MARK,
                        'result expand callback')
    if not balanced(text):
        fail('tools unbalanced after edits')
        return
    for token in ['kotlinx.serialization.json.JsonArray', 'previewLimit = 1200',
                  'previewLimit = 2400', 'onExpand = if (hasResultDetail)']:
        if token not in text:
            fail('tools missing ' + token)
            return
    (ROOT / TOOLS).write_text(text, encoding='utf-8')
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
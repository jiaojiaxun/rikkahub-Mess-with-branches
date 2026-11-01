#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch317: show AI _display purpose in header and tool rows.'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhLivePurpose317'
DIAG = 'ci_diag_batch317_live_purpose.txt'
HEADER = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/RhThoughtHeader.kt'
TOOLS = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageTools.kt'
STR_EN = 'app/src/main/res/values/strings.xml'
STR_ZH = 'app/src/main/res/values-zh/strings.xml'
report = []
failures = []


def note(message):
    report.append(str(message)[:900])


def fail(message):
    failures.append(str(message)[:300])
    report.append('FAIL ' + str(message)[:500])


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


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def ensure_import(text, line, anchor):
    lines = text.split(NL)
    stripped = [item.strip() for item in lines]
    if line in stripped:
        return text
    hits = [index for index, item in enumerate(stripped) if item == anchor]
    if len(hits) != 1:
        fail('import anchor ' + anchor + ' count=' + str(len(hits)))
        return text
    lines.insert(hits[0] + 1, line)
    return NL.join(lines)


def patch_header():
    text = read(HEADER)
    if MARK in text:
        note('header already applied')
        return
    text = ensure_import(text, 'import me.rerere.rikkahub.data.ai.tools.RH_DISPLAY_PARAM', 'import me.rerere.rikkahub.R')
    if failures:
        return
    text = ensure_import(
        text,
        'import me.rerere.rikkahub.ui.components.message.tools.getStringContent',
        'import me.rerere.rikkahub.ui.components.message.tools.ToolUIRegistry',
    )
    if failures:
        return

    old_reasoning = '''        is ThinkingStep.ReasoningStep -> {
            val seconds = rememberRhReasoningSeconds(step.reasoning, loading)
            stringResource(R.string.rh_thought_activity_thinking, seconds)
        }'''
    new_reasoning = '''        is ThinkingStep.ReasoningStep -> {
            val snippet = rhReasoningSnippet(step.reasoning.reasoning)
            if (snippet.isNotBlank()) {
                stringResource(R.string.rh_thought_activity_reasoning, snippet)
            } else {
                val seconds = rememberRhReasoningSeconds(step.reasoning, loading)
                stringResource(R.string.rh_thought_activity_thinking, seconds)
            }
        }'''
    text = replace_once(text, old_reasoning, new_reasoning, 'reasoning branch')
    if failures:
        return

    helper = '''private fun rhReasoningSnippet(text: String): String {
    val line = text.lineSequence().map { it.trim() }.lastOrNull { it.isNotBlank() } ?: return ""
    return if (line.length > 28) line.take(28) + "..." else line
}

'''
    fn_head = '''@Composable
private fun rhToolPurpose(tool: UIMessagePart.Tool, loading: Boolean): String {'''
    text = replace_once(text, fn_head, helper + fn_head, 'tool purpose head')
    if failures:
        return

    old_first = '''private fun rhToolPurpose(tool: UIMessagePart.Tool, loading: Boolean): String {
    val renderer = remember(tool.toolName) { ToolUIRegistry.resolve(tool.toolName) }'''
    new_first = '''private fun rhToolPurpose(tool: UIMessagePart.Tool, loading: Boolean): String {
    tool.inputAsJson().getStringContent(RH_DISPLAY_PARAM)?.takeIf { it.isNotBlank() }?.let { return it }
    val renderer = remember(tool.toolName) { ToolUIRegistry.resolve(tool.toolName) }'''
    text = replace_once(text, old_first, new_first, 'tool display priority')
    if failures:
        return

    text = text.replace('package me.rerere.rikkahub.ui.components.message' + NL,
                        'package me.rerere.rikkahub.ui.components.message' + NL + NL + '// ' + MARK + NL, 1)
    if 'rhReasoningSnippet' not in text or 'RH_DISPLAY_PARAM' not in text:
        fail('header selfcheck missing')
        return
    write(HEADER, text)
    note('header OK: _display priority and reasoning snippet')


def patch_tools():
    text = read(TOOLS)
    if MARK in text:
        note('tools already applied')
        return
    text = ensure_import(text, 'import me.rerere.rikkahub.data.ai.tools.RH_DISPLAY_PARAM', 'import me.rerere.rikkahub.R')
    if failures:
        return

    old_label = '''        label = {
            val rhVerbRes = rhToolVerbRes(tool.toolName)
            val rhPillText = rhToolPillText(tool)
            if (rhVerbRes != null && rhPillText != null) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(5.dp),
                ) {
                    Text(
                        text = stringResource(rhVerbRes),
                        style = MaterialTheme.typography.titleSmall,
                        color = MaterialTheme.colorScheme.secondary,
                        modifier = Modifier.shimmer(isLoading = loading),
                    )
                    RhToolPill(
                        text = rhPillText,
                        faviconUrl = rhToolFaviconUrl(tool),
                    )
                }
            } else {
                val rhTitleText = renderer.title(context)
                Text(
                    text = rhTitleText,
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.secondary,
                    modifier = Modifier.shimmer(isLoading = loading),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        },'''
    new_label = '''        label = {
            val rhDisplayText = context.arguments.getStringContent(RH_DISPLAY_PARAM)
                ?.takeIf { it.isNotBlank() }
            if (rhDisplayText != null) {
                Text(
                    text = rhDisplayText,
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.secondary,
                    modifier = Modifier.shimmer(isLoading = loading),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            } else {
                val rhVerbRes = rhToolVerbRes(tool.toolName)
                val rhPillText = rhToolPillText(tool)
                if (rhVerbRes != null && rhPillText != null) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(5.dp),
                    ) {
                        Text(
                            text = stringResource(rhVerbRes),
                            style = MaterialTheme.typography.titleSmall,
                            color = MaterialTheme.colorScheme.secondary,
                            modifier = Modifier.shimmer(isLoading = loading),
                        )
                        RhToolPill(
                            text = rhPillText,
                            faviconUrl = rhToolFaviconUrl(tool),
                        )
                    }
                } else {
                    val rhTitleText = renderer.title(context)
                    Text(
                        text = rhTitleText,
                        style = MaterialTheme.typography.titleSmall,
                        color = MaterialTheme.colorScheme.secondary,
                        modifier = Modifier.shimmer(isLoading = loading),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        },'''
    bal0 = balance(text)
    text = replace_once(text, old_label, new_label, 'tool label block')
    if failures:
        return
    if balance(text) != bal0:
        fail('tools balance changed')
        return
    if 'getStringContent(RH_DISPLAY_PARAM)' not in text:
        fail('tools _display read missing')
        return
    text = text.replace('package me.rerere.rikkahub.ui.components.message' + NL,
                        'package me.rerere.rikkahub.ui.components.message' + NL + NL + '// ' + MARK + NL, 1)
    write(TOOLS, text)
    note('tools OK: _display replaces verb/tool name when present')


def add_strings():
    entries = [
        ('rh_thought_activity_reasoning', 'Working on: %1$s', '正在处理：%1$s'),
    ]
    for key, english, chinese in entries:
        for rel_path, value in [(STR_EN, english), (STR_ZH, chinese)]:
            path = ROOT / rel_path
            if not path.exists():
                fail('strings missing ' + rel_path)
                continue
            content = path.read_text(encoding='utf-8')
            marker = 'name="' + key + '"'
            if marker in content:
                continue
            at = content.rfind('</resources>')
            if at < 0:
                fail('no resources close in ' + rel_path)
                continue
            row = '    <string ' + marker + '>' + value + '</string>' + NL
            content = content[:at] + row + content[at:]
            path.write_text(content, encoding='utf-8')
            note('string added ' + rel_path)


def main():
    for name, action in [('header', patch_header), ('tools', patch_tools), ('strings', add_strings)]:
        try:
            action()
            note(name + ' DONE')
        except Exception as exc:
            fail(name + ' EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
    body = NL.join(report) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:
        print('::error::batch317 diag write failed ' + str(exc)[:200])
    for line in report:
        print('::error::batch317 ' + line)
    if failures:
        print('::error::batch317 FAILED count=' + str(len(failures)))
        raise SystemExit(1)
    print('batch317: OK')


main()
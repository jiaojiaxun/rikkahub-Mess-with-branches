#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch295: live current-activity header for the thought drawer.

The top row used to show a total "已工作 N秒". It now shows the latest action:

  - ReasoningStep: "思考N秒" (live while reasoning is unfinished)
  - ToolStep: the existing ToolUIRenderer.title (e.g. "核对apk"), reused
    rather than generating or summarizing the tool purpose again
  - ServerToolStep: the existing generic tool-call title
  - no steps: existing "思考过程" fallback

The tool row keeps its own title, so both places show the action title at the
same time. AnimatedContent animates step-to-step changes (fade + vertical
slide); per-second reasoning text updates do not retrigger the animation.

A new self-contained RhThoughtHeader.kt is added; RhThoughtDrawer.kt only
replaces the top RhDrawerRow call. No full-file rewrite of the drawer.
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhDrawer295'
DIAG = 'ci_diag_batch295_header_activity.txt'
DRAWER = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/RhThoughtDrawer.kt'
HEADER = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/RhThoughtHeader.kt'
STR_EN = 'app/src/main/res/values/strings.xml'
STR_ZH = 'app/src/main/res/values-zh/strings.xml'
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


HEADER_TEXT = '''
package me.rerere.rikkahub.ui.components.message

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.delay
import me.rerere.ai.ui.UIMessagePart
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.ArrowDown01
import me.rerere.hugeicons.stroke.ArrowRight01
import me.rerere.rikkahub.R
import me.rerere.rikkahub.ui.components.message.tools.ToolUIContext
import me.rerere.rikkahub.ui.components.message.tools.ToolUIRegistry
import me.rerere.rikkahub.utils.JsonInstant

/** rhDrawer295: current activity header with animated step changes. */
@Composable
fun RhThoughtHeader(
    steps: List<ThinkingStep>,
    loading: Boolean,
    expanded: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val latest = rhLatestStep(steps)
    Row(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .clickable { onClick() }
            .padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Box(modifier = Modifier.weight(1f)) {
            AnimatedContent(
                targetState = rhHeaderKey(latest),
                transitionSpec = {
                    (fadeIn() + slideInVertically { height -> height / 3 })
                        .togetherWith(
                            fadeOut() + slideOutVertically { height -> -height / 3 }
                        )
                },
            ) { key ->
                Text(
                    text = rhHeaderText(latest, loading),
                    style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        Icon(
            imageVector = if (expanded) HugeIcons.ArrowDown01 else HugeIcons.ArrowRight01,
            contentDescription = null,
            modifier = Modifier.size(16.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

private fun rhLatestStep(steps: List<ThinkingStep>): ThinkingStep? {
    for (index in steps.indices.reversed()) {
        val step = steps[index]
        val active = when (step) {
            is ThinkingStep.ReasoningStep -> step.reasoning.finishedAt == null
            is ThinkingStep.ToolStep -> !step.tool.isExecuted
            is ThinkingStep.ServerToolStep -> !step.tool.isFinished
        }
        if (active) {
            return step
        }
    }
    return steps.lastOrNull()
}

private fun rhHeaderKey(step: ThinkingStep?): String = when (step) {
    null -> "none"
    is ThinkingStep.ReasoningStep -> "reasoning:" + step.reasoning.createdAt.toEpochMilliseconds()
    is ThinkingStep.ToolStep -> "tool:" + step.tool.toolCallId
    is ThinkingStep.ServerToolStep -> "server:" + step.tool.toolCallId
}

@Composable
private fun rhHeaderText(step: ThinkingStep?, loading: Boolean): String {
    if (step == null) {
        return stringResource(R.string.rh_thought_process)
    }
    return when (step) {
        is ThinkingStep.ReasoningStep -> {
            val seconds = rememberRhReasoningSeconds(step.reasoning, loading)
            stringResource(R.string.rh_thought_activity_thinking, seconds)
        }

        is ThinkingStep.ToolStep -> rhToolPurpose(step.tool, loading)

        is ThinkingStep.ServerToolStep -> stringResource(
            R.string.chat_message_tool_call_generic,
            step.tool.toolName,
        )
    }
}

@Composable
private fun rememberRhReasoningSeconds(
    reasoning: UIMessagePart.Reasoning,
    loading: Boolean,
): Long {
    val start = reasoning.createdAt.toEpochMilliseconds()
    val recordedEnd = reasoning.finishedAt?.toEpochMilliseconds()
    var tick by remember { mutableStateOf(0L) }
    LaunchedEffect(reasoning.finishedAt, loading) {
        if (reasoning.finishedAt == null && loading) {
            while (true) {
                tick = System.currentTimeMillis()
                delay(1000L)
            }
        }
    }
    val end = recordedEnd ?: tick
    if (end <= start) {
        return 0L
    }
    return (end - start) / 1000L
}

@Composable
private fun rhToolPurpose(tool: UIMessagePart.Tool, loading: Boolean): String {
    val renderer = remember(tool.toolName) { ToolUIRegistry.resolve(tool.toolName) }
    val context = remember(tool, loading) {
        ToolUIContext(
            tool = tool,
            arguments = tool.inputAsJson(),
            content = if (tool.isExecuted) {
                runCatching {
                    JsonInstant.parseToJsonElement(
                        tool.output.filterIsInstance<UIMessagePart.Text>()
                            .joinToString(" ") { it.text }
                    )
                }.getOrNull()
            } else {
                null
            },
            loading = loading && !tool.isExecuted,
        )
    }
    return renderer.title(context).ifBlank { tool.toolName }
}
'''


def part_header():
    path = ROOT / HEADER
    current = path.read_text(encoding='utf-8') if path.exists() else ''
    if MARK in current:
        note('header already present')
        return
    text = HEADER_TEXT.strip(NL) + NL
    if 'fun RhThoughtHeader(' not in text:
        fail('header body missing')
        return
    if 'rhToolPurpose' not in text or 'AnimatedContent' not in text:
        fail('header helpers missing')
        return
    if text.count('(') != text.count(')') or text.count('{') != text.count('}'):
        fail('header unbalanced')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    note('header written chars=' + str(len(text)))


def part_drawer():
    text = read(DRAWER)
    if MARK in text:
        note('drawer already at 295')
        return
    old_block = '''        RhDrawerRow(
            label = if (seconds > 0L) {
                stringResource(R.string.rh_thought_worked, seconds)
            } else {
                stringResource(R.string.rh_thought_process)
            },
            expanded = opened,
            strong = false,
            leading = null,
            onClick = { userExpanded = !opened },
        )'''
    new_block = '''        RhThoughtHeader(
            steps = steps,
            loading = loading,
            expanded = opened,
            onClick = { userExpanded = !opened },
        )'''
    text = replace_once(text, old_block, new_block, 'drawer header call')
    if MARK not in text:
        package_line = 'package me.rerere.rikkahub.ui.components.message'
        if package_line in text:
            text = text.replace(package_line, package_line + NL + '// ' + MARK, 1)
        else:
            fail('package line missing')
    checks = ['RhThoughtHeader(', 'steps = steps,', 'loading = loading,']
    for token in checks:
        if token not in text:
            fail('drawer missing ' + token)
    if 'rh_thought_worked' in text and 'RhDrawerRow(' in text:
        # The string may remain in strings.xml, but this call site must be gone.
        if 'label = if (seconds > 0L)' in text:
            fail('old worked header still present')
    if text.count('(') != text.count(')') or text.count('{') != text.count('}'):
        fail('drawer unbalanced')
    if not failures:
        (ROOT / DRAWER).write_text(text, encoding='utf-8')
        note('drawer header call replaced')


def part_strings():
    entries = [
        ('rh_thought_activity_thinking', 'Thinking %1$ds', '思考%1$d秒'),
    ]
    for rel, english, chinese in entries:
        for path, value in [(STR_EN, english), (STR_ZH, chinese)]:
            if not path.exists():
                fail('missing strings file ' + str(path))
                continue
            content = path.read_text(encoding='utf-8')
            key = 'name="' + rel + '"'
            if key in content:
                continue
            closing = content.rfind('</resources>')
            if closing < 0:
                fail('no </resources> in ' + str(path))
                continue
            row = '    <string ' + key + '>' + value + '</string>' + NL
            content = content[:closing] + row + content[closing:]
            path.write_text(content, encoding='utf-8')
            note('string added ' + str(path))


def main():
    for name, fn in [('header', part_header), ('drawer', part_drawer), ('strings', part_strings)]:
        try:
            fn()
            note(name + ' DONE')
        except Exception as exc:
            fail(name + ' EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
    body = NL.join(report) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:
        print('::error::batch295 diag write failed ' + str(exc)[:200])
    for line in report:
        print('::error::batch295 ' + str(line)[:800])
    if failures:
        print('::error::batch295 FAILED count=' + str(len(failures)))
        raise SystemExit(1)
    print('batch295: OK')


main()
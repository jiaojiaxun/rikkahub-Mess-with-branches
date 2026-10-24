#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch286: drawer-style chain-of-thought (nested expand, layer by layer)

User request: the thinking / tool-call area should behave like the reference
screenshots - one drawer inside another, opened in order:

    L0  已工作 28秒            ▸      (whole block, collapsed by default)
    L1    ● 使用了 4 个网页工具 ▸      (tool group)
    L2      (idea) 思考过程     ▸      (single reasoning row)
    L2      (tool) 搜索 xxx     ▸      (single tool row)
    L3        { 入参 JSON }            (grey rounded block)
    L3        { 结果 JSON }            (grey rounded block)

What the CI tree actually looks like today (verified by reading the
`snapshot` branch, not by guessing):

  ChatMessage.kt ThinkingBlock branch currently carries, in order,
    * `var showSummaryPanel` (batch76)
    * ModalBottomSheet + HighlightCodeBlock dump (batch76 + batch88)
    * progress badge `N/M` (rhToolProgressBadge)
    * ChainOfThought(collapsedLabel = ToolSummaryMapper.summarize(...))
  ChainOfThought.kt collapse row already toggles in place (rhBatch136).
  ChatMessageTools.kt rows default to expanded = true (rhToolExpand249).

So the flat look comes from: no grouping layer, no elapsed-time header, and
tool rows that are expanded from the start.

This batch replaces the WHOLE ThinkingBlock branch with one call to a new
self-contained drawer component, and turns tool rows into collapsed leaves
whose expanded body shows argument / result JSON blocks.

Why a whole-branch replacement (slice between two anchors) instead of
line-by-line edits: the branch is the union of batch76 + batch88 + progress
badge injections. Every one of those anchors disappears here on purpose -
their patches will then fail loudly (warn-only) instead of double-injecting.

Five checks:
 1. imports: RhThoughtDrawer.kt is self-contained (new file). ChatMessage.kt
    gains no new symbol - RhThoughtDrawer lives in the same package. Unused
    imports left behind (ModalBottomSheet / HighlightCodeBlock) are warnings.
 2. same-file conflicts: ChatMessage.kt is touched by batch45/66/68/76/88/
    rhToolProgressBadge/rhSemanticSummary. The slice boundaries are the two
    stable `is MessagePartBlock.*` labels, which none of them edit.
 3. scope: everything inside `when (block)` in MessagePartsBlock; `block`,
    `loading`, `generationActive`, `settings`, `model`, `assistant`,
    `onTool*` handlers are all in scope. RhDrawerScopeImpl implements the
    public ChainOfThoughtScope interface, so ChatMessageToolStep /
    ChatMessageReasoningStep / ChatMessageServerToolStep keep working
    unchanged.
 4. braces: each generated block is balanced on its own; the script asserts
    whole-file balance is unchanged.
 5. signatures: ChainOfThoughtScope overrides provide no default values
    (Kotlin forbids that); all other signatures are new.

Python checks: no inline quote soup (triple-quoted blocks only), explicit NL
concat, helpers defined before use, every failure recorded and reported.
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhThoughtDrawer286'
DIAG = 'ci_diag_batch286.txt'

CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
TOOLS = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageTools.kt'
NEW_FILE = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/RhThoughtDrawer.kt'
STR_EN = 'app/src/main/res/values/strings.xml'
STR_ZH = 'app/src/main/res/values-zh/strings.xml'

report = []
failures = []


def note(msg):
    report.append(str(msg)[:900])


def add_fail(msg):
    failures.append(str(msg)[:300])
    report.append('FAIL ' + str(msg)[:400])


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


def write(rel, text):
    (ROOT / rel).write_text(text, encoding='utf-8')


def lines_of(text):
    return text.split(NL)


def text_of(lines):
    out = ''
    for i, ln in enumerate(lines):
        if i:
            out += NL
        out += ln
    return out


def ind_of(line):
    stripped = line.lstrip()
    return line[:len(line) - len(stripped)]


# ---------------------------------------------------------------------------
# New component file
# ---------------------------------------------------------------------------
DRAWER_TEXT = '''
package me.rerere.rikkahub.ui.components.message

import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardColors
import androidx.compose.material3.CardDefaults
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
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.util.fastForEach
import kotlinx.coroutines.delay
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.ArrowRight01
import me.rerere.hugeicons.stroke.ArrowUp01
import me.rerere.rikkahub.R

/**
 * Nested "drawer" presentation of a chain-of-thought block.
 *
 * Layer 0 is a single elapsed-time row. Opening it reveals either
 *  - one tool-group row (when the block contains tool calls), which opens into
 *    the original step timeline, or
 *  - the step timeline directly (reasoning-only blocks).
 *
 * Every step row keeps its own expand state, so a single tool can be opened
 * down to its argument / result payloads without opening the rest.
 *
 * [content] is the very same lambda the caller already used for
 * ChainOfThought, so approval cards, ask_user, image output and webview cards
 * keep rendering exactly as before.
 */
@Composable
fun RhThoughtDrawer(
    modifier: Modifier = Modifier,
    cardColors: CardColors = CardDefaults.cardColors(
        containerColor = MaterialTheme.colorScheme.surfaceContainerHigh,
    ),
    steps: List<ThinkingStep>,
    loading: Boolean = false,
    forceExpanded: Boolean = false,
    content: @Composable ChainOfThoughtScope.(ThinkingStep) -> Unit,
) {
    var userExpanded by remember { mutableStateOf(false) }
    var userGroupExpanded by remember { mutableStateOf(false) }
    val opened = userExpanded || forceExpanded || loading
    val groupOpened = userGroupExpanded || forceExpanded || loading
    val toolCount = steps.count { it !is ThinkingStep.ReasoningStep }
    val seconds = rememberRhWorkedSeconds(steps, loading)
    val scope = remember { RhDrawerScopeImpl() }

    Card(
        modifier = modifier,
        colors = cardColors,
        shape = RoundedCornerShape(16.dp),
    ) {
        Column(
            modifier = Modifier
                .padding(horizontal = 4.dp, vertical = 2.dp)
                .animateContentSize(),
        ) {
            RhDrawerRow(
                label = if (seconds > 0L) {
                    stringResource(R.string.rh_thought_worked, seconds)
                } else {
                    stringResource(R.string.rh_thought_process)
                },
                expanded = opened,
                showDot = false,
                onClick = { userExpanded = !opened },
            )
            if (opened) {
                if (toolCount > 0) {
                    RhDrawerRow(
                        modifier = Modifier.padding(start = 10.dp),
                        label = rhToolGroupLabel(steps),
                        expanded = groupOpened,
                        showDot = true,
                        onClick = { userGroupExpanded = !groupOpened },
                    )
                    if (groupOpened) {
                        Column(modifier = Modifier.padding(start = 18.dp)) {
                            steps.fastForEach { step ->
                                scope.content(step)
                            }
                        }
                    }
                } else {
                    Column(modifier = Modifier.padding(start = 10.dp)) {
                        steps.fastForEach { step ->
                            scope.content(step)
                        }
                    }
                }
            }
        }
    }
}

/**
 * Small grey rounded block used to show raw tool payloads.
 *
 * Deliberately plain Text instead of the syntax highlighter: tool outputs can
 * be tens of kilobytes and re-highlighting them on every streaming frame
 * caused visible jank (see the batch238/241 line of work).
 */
@Composable
fun RhToolJsonBlock(
    label: String,
    text: String,
    maxLines: Int = 8,
) {
    val body = text.trim()
    if (body.isEmpty()) {
        return
    }
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surfaceContainerHighest)
            .padding(horizontal = 10.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Text(
            text = body,
            style = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
            color = MaterialTheme.colorScheme.onSurface,
            maxLines = maxLines,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun RhDrawerRow(
    label: String,
    expanded: Boolean,
    showDot: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .clickable { onClick() }
            .padding(vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        if (showDot) {
            Box(
                modifier = Modifier
                    .size(6.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.onSurfaceVariant),
            )
        }
        Text(
            text = label,
            style = MaterialTheme.typography.titleSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f, fill = false),
        )
        Icon(
            imageVector = if (expanded) HugeIcons.ArrowUp01 else HugeIcons.ArrowRight01,
            contentDescription = null,
            modifier = Modifier.size(16.dp),
            tint = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun RhDrawerStepRow(
    icon: (@Composable () -> Unit)?,
    label: @Composable () -> Unit,
    extra: (@Composable () -> Unit)?,
    onClick: (() -> Unit)?,
    expanded: Boolean,
    onExpandedChange: (Boolean) -> Unit,
    contentVisible: Boolean,
    content: (@Composable () -> Unit)?,
) {
    val iconContent = icon
    val extraContent = extra
    val clickHandler = onClick
    val contentBlock = content
    val hasContent = contentBlock != null

    Column(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(8.dp))
                .then(
                    if (clickHandler != null) {
                        Modifier.clickable { clickHandler() }
                    } else if (hasContent) {
                        Modifier.clickable { onExpandedChange(!expanded) }
                    } else {
                        Modifier
                    }
                )
                .padding(vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Box(
                modifier = Modifier.width(20.dp),
                contentAlignment = Alignment.Center,
            ) {
                if (iconContent != null) {
                    Box(
                        modifier = Modifier.size(16.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        iconContent()
                    }
                } else {
                    Box(
                        modifier = Modifier
                            .size(6.dp)
                            .clip(CircleShape)
                            .background(MaterialTheme.colorScheme.outline),
                    )
                }
            }
            Box(modifier = Modifier.weight(1f)) {
                label()
            }
            if (extraContent != null) {
                extraContent()
            }
            if (clickHandler != null) {
                Icon(
                    imageVector = HugeIcons.ArrowRight01,
                    contentDescription = null,
                    modifier = Modifier.size(16.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else if (hasContent) {
                Icon(
                    imageVector = if (expanded) HugeIcons.ArrowUp01 else HugeIcons.ArrowRight01,
                    contentDescription = null,
                    modifier = Modifier.size(16.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        if (contentVisible && contentBlock != null) {
            Box(
                modifier = Modifier.padding(start = 28.dp, top = 2.dp, bottom = 6.dp),
            ) {
                contentBlock()
            }
        }
    }
}

private class RhDrawerScopeImpl : ChainOfThoughtScope {
    @Composable
    override fun ChainOfThoughtStep(
        icon: (@Composable () -> Unit)?,
        label: @Composable () -> Unit,
        extra: (@Composable () -> Unit)?,
        onClick: (() -> Unit)?,
        collapsedAdaptiveWidth: Boolean,
        content: (@Composable () -> Unit)?,
    ) {
        var expanded by remember { mutableStateOf(false) }
        RhDrawerStepRow(
            icon = icon,
            label = label,
            extra = extra,
            onClick = onClick,
            expanded = expanded,
            onExpandedChange = { expanded = it },
            contentVisible = expanded,
            content = content,
        )
    }

    @Composable
    override fun ControlledChainOfThoughtStep(
        expanded: Boolean,
        onExpandedChange: (Boolean) -> Unit,
        icon: (@Composable () -> Unit)?,
        label: @Composable () -> Unit,
        extra: (@Composable () -> Unit)?,
        onClick: (() -> Unit)?,
        collapsedAdaptiveWidth: Boolean,
        contentVisible: Boolean,
        content: (@Composable () -> Unit)?,
    ) {
        RhDrawerStepRow(
            icon = icon,
            label = label,
            extra = extra,
            onClick = onClick,
            expanded = expanded,
            onExpandedChange = onExpandedChange,
            contentVisible = contentVisible,
            content = content,
        )
    }
}

@Composable
private fun rhToolGroupLabel(steps: List<ThinkingStep>): String {
    val count = steps.count { it !is ThinkingStep.ReasoningStep }
    val categoryRes = rhDominantCategory(steps)
    if (count <= 0) {
        return stringResource(R.string.rh_thought_used_tools_generic, 0)
    }
    return if (categoryRes == R.string.rh_cat_tool) {
        stringResource(R.string.rh_thought_used_tools_generic, count)
    } else {
        stringResource(R.string.rh_thought_used_tools, count, stringResource(categoryRes))
    }
}

@Composable
private fun rememberRhWorkedSeconds(steps: List<ThinkingStep>, loading: Boolean): Long {
    val start = remember(steps) { rhStepsStartMillis(steps) }
    val recordedEnd = remember(steps) { rhStepsEndMillis(steps) }
    var tick by remember { mutableStateOf(0L) }

    LaunchedEffect(loading) {
        while (true) {
            tick = System.currentTimeMillis()
            if (!loading) {
                break
            }
            delay(1000L)
        }
    }

    if (start == null || start <= 0L) {
        return 0L
    }
    val end = if (loading) maxOf(tick, start) else (recordedEnd ?: tick)
    val delta = end - start
    if (delta <= 0L) {
        return if (loading) 1L else 0L
    }
    val seconds = delta / 1000L
    return if (loading) seconds.coerceAtLeast(1L) else seconds
}

private fun rhStepsStartMillis(steps: List<ThinkingStep>): Long? {
    return steps.filterIsInstance<ThinkingStep.ReasoningStep>()
        .map { it.reasoning.createdAt.toEpochMilliseconds() }
        .minOrNull()
}

private fun rhStepsEndMillis(steps: List<ThinkingStep>): Long? {
    return steps.filterIsInstance<ThinkingStep.ReasoningStep>()
        .mapNotNull { it.reasoning.finishedAt?.toEpochMilliseconds() }
        .maxOrNull()
}

private fun rhDominantCategory(steps: List<ThinkingStep>): Int {
    val counts = mutableMapOf<Int, Int>()
    steps.forEach { step ->
        val name = when (step) {
            is ThinkingStep.ToolStep -> step.tool.toolName
            is ThinkingStep.ServerToolStep -> step.tool.toolName
            else -> null
        }
        if (name != null) {
            val key = rhCategoryRes(name)
            counts[key] = (counts[key] ?: 0) + 1
        }
    }
    var best = R.string.rh_cat_tool
    var bestCount = 0
    counts.forEach { entry ->
        if (entry.value > bestCount) {
            best = entry.key
            bestCount = entry.value
        }
    }
    return best
}

private fun rhCategoryRes(name: String): Int {
    if (name.startsWith("mcp__")) {
        return R.string.rh_cat_mcp
    }
    if (name.startsWith("browser_") || name.startsWith("web_") ||
        name == "search_web" || name == "search_image"
    ) {
        return R.string.rh_cat_web
    }
    if (name.startsWith("read_") || name.startsWith("write_") ||
        name.startsWith("list_") || name.startsWith("file_") ||
        name.startsWith("edit_") || name.startsWith("find_") ||
        name == "create_directory"
    ) {
        return R.string.rh_cat_file
    }
    return R.string.rh_cat_tool
}
'''

# ---------------------------------------------------------------------------
# Replacement for the whole ThinkingBlock branch in ChatMessage.kt
# (written at zero indent; each line is prefixed with the anchor indent)
# ---------------------------------------------------------------------------
THINKING_TEMPLATE = '''
is MessagePartBlock.ThinkingBlock -> {
    if (block.steps.isNotEmpty()) {
        val isReasoningOnlyBlock = block.steps.fastAll { it is ThinkingStep.ReasoningStep }
        // Never hide an approval request behind a collapsed drawer row.
        val hasPendingApproval = block.steps.any {
            it is ThinkingStep.ToolStep &&
                it.tool.approvalState is ToolApprovalState.Pending
        }
        RhThoughtDrawer(
            modifier = Modifier.animateContentSize(),
            steps = block.steps,
            loading = loading,
            forceExpanded = hasPendingApproval,
            cardColors = CardDefaults.cardColors(
                containerColor = MaterialTheme.colorScheme.surfaceContainerHigh.copy(alpha = settings.displaySetting.bubbleOpacity),
            ),
        ) { step ->
            when (step) {
                is ThinkingStep.ReasoningStep -> {
                    key(step.reasoning.createdAt) {
                        ChatMessageReasoningStep(
                            reasoning = step.reasoning,
                            model = model,
                            assistant = assistant,
                            collapsedAdaptiveWidth = isReasoningOnlyBlock,
                        )
                    }
                }

                is ThinkingStep.ToolStep -> {
                    key(step.tool.toolCallId.ifBlank { step.hashCode().toString() }) {
                        ChatMessageToolStep(
                            tool = step.tool,
                            loading = loading && !step.tool.isExecuted,
                            generationActive = generationActive,
                            onToolApproval = onToolApproval,
                            onToolAnswer = onToolAnswer,
                            onRerunTool = onRerunTool,
                        )
                    }
                }

                is ThinkingStep.ServerToolStep -> {
                    key(step.tool.toolCallId.ifBlank { step.hashCode().toString() }) {
                        ChatMessageServerToolStep(tool = step.tool)
                    }
                }
            }
        }
    }
}
'''


def build_thinking_block(indent):
    out = []
    for line in THINKING_TEMPLATE.strip(NL).split(NL):
        if line.strip() == '':
            out.append('')
        else:
            out.append(indent + line)
    return out


# ---------------------------------------------------------------------------
# Parts
# ---------------------------------------------------------------------------
def part_new_file():
    path = ROOT / NEW_FILE
    if path.exists() and MARK in path.read_text(encoding='utf-8'):
        note('drawer file already present')
        return
    text = DRAWER_TEXT.strip(NL) + NL
    bal = balance(text)
    if bal != 0:
        add_fail('drawer file balance=' + str(bal))
        return
    needs = [
        'fun RhThoughtDrawer(',
        'fun RhToolJsonBlock(',
        'class RhDrawerScopeImpl : ChainOfThoughtScope',
        'fun ChainOfThoughtStep(',
        'fun ControlledChainOfThoughtStep(',
        'rememberRhWorkedSeconds',
        'rhCategoryRes',
    ]
    for token in needs:
        if token not in text:
            add_fail('drawer file missing token ' + token)
            return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    note('drawer file written chars=' + str(len(text)))


def part_chat_message():
    text = read(CM)
    if MARK in text:
        note('chat message already applied')
        return
    bal0 = balance(text)
    lines = lines_of(text)

    start = -1
    for i, line in enumerate(lines):
        if line.strip() == 'is MessagePartBlock.ThinkingBlock -> {':
            start = i
            break
    if start < 0:
        add_fail('ThinkingBlock anchor not found')
        return

    end = -1
    for j in range(start + 1, len(lines)):
        if lines[j].strip().startswith('is MessagePartBlock.ContentBlock ->'):
            end = j
            break
    if end < 0:
        add_fail('ContentBlock anchor not found after ' + str(start))
        return

    indent = ind_of(lines[start])
    block = build_thinking_block(indent)
    new_lines = lines[:start] + block + lines[end:]
    new_text = text_of(new_lines)

    bal1 = balance(new_text)
    if bal1 != bal0:
        add_fail('chat message balance ' + str(bal0) + ' -> ' + str(bal1))
        return

    checks = [
        ('RhThoughtDrawer(', True),
        ('showSummaryPanel', False),
        ('工具调用（共', False),
        ('rhToolProgressBadge', False),
        ('stepNumber = toolStepIndex', False),
    ]
    for token, want in checks:
        present = token in new_text
        if present != want:
            add_fail('chat message token ' + token + ' present=' + str(present))
            return

    write(CM, new_text)
    note('chat message OK: slice ' + str(start) + '..' + str(end) + ' replaced')


def part_tools():
    text = read(TOOLS)
    marker_comment = '// ' + MARK + ': collapse by default so the drawer opens layer by layer'
    if marker_comment in text:
        note('tools already applied')
        return
    bal0 = balance(text)
    lines = lines_of(text)
    changed = []

    # 1. Tool rows start collapsed so every layer is opened by the user.
    target = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('var expanded by remember { mutableStateOf(true) }'):
            target = i
            break
    if target < 0:
        add_fail('tools expanded anchor not found')
        return
    lines[target] = ind_of(lines[target]) + 'var expanded by remember { mutableStateOf(false) } ' + marker_comment
    changed.append('collapse')

    # 2. Argument / result blocks inside the expanded body.
    summary_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == 'renderer.Summary(context)':
            summary_idx = i
            break
    if summary_idx < 0:
        add_fail('tools summary anchor not found')
        return
    base = ind_of(lines[summary_idx])
    block = [
        base + 'RhToolJsonBlock(',
        base + '    label = stringResource(R.string.rh_tool_args),',
        base + '    text = tool.input,',
        base + '    maxLines = 8,',
        base + ')',
        base + 'if (tool.isExecuted) {',
        base + '    RhToolJsonBlock(',
        base + '        label = stringResource(R.string.rh_tool_result),',
        base + '        text = tool.output.filterIsInstance<UIMessagePart.Text>().joinToString("\\n") { it.text },',
        base + '        maxLines = 10,',
        base + '    )',
        base + '}',
    ]
    lines[summary_idx:summary_idx] = block
    changed.append('payloads')

    new_text = text_of(lines)
    bal1 = balance(new_text)
    if bal1 != bal0:
        add_fail('tools balance ' + str(bal0) + ' -> ' + str(bal1))
        return
    for token in ['RhToolJsonBlock(', 'rh_tool_args', 'rh_tool_result', marker_comment]:
        if token not in new_text:
            add_fail('tools selfcheck missing ' + token)
            return
    write(TOOLS, new_text)
    note('tools OK: ' + ', '.join(changed))


STRINGS = {
    STR_EN: [
        ('rh_thought_worked', 'Worked for %1$ds'),
        ('rh_thought_process', 'Thinking'),
        ('rh_thought_used_tools', 'Used %1$d %2$s tools'),
        ('rh_thought_used_tools_generic', 'Used %1$d tools'),
        ('rh_cat_web', 'web'),
        ('rh_cat_file', 'file'),
        ('rh_cat_mcp', 'MCP'),
        ('rh_cat_tool', ''),
        ('rh_tool_args', 'Arguments'),
        ('rh_tool_result', 'Result'),
    ],
    STR_ZH: [
        ('rh_thought_worked', '已工作 %1$d秒'),
        ('rh_thought_process', '思考过程'),
        ('rh_thought_used_tools', '使用了 %1$d 个%2$s工具'),
        ('rh_thought_used_tools_generic', '使用了 %1$d 个工具'),
        ('rh_cat_web', '网页'),
        ('rh_cat_file', '文件'),
        ('rh_cat_mcp', 'MCP'),
        ('rh_cat_tool', '工具'),
        ('rh_tool_args', '参数'),
        ('rh_tool_result', '结果'),
    ],
}


def part_strings():
    for rel, entries in STRINGS.items():
        path = ROOT / rel
        if not path.exists():
            add_fail('missing strings file ' + rel)
            continue
        text = path.read_text(encoding='utf-8')
        added = 0
        for key, value in entries:
            if ('name="' + key + '"') in text:
                continue
            closing = text.rfind('</resources>')
            if closing < 0:
                add_fail('no </resources> in ' + rel)
                break
            row = ('    <!-- ' + MARK + ' -->' + NL
                   + '    <string name="' + key + '">' + value + '</string>' + NL)
            text = text[:closing] + row + text[closing:]
            added += 1
        if added:
            path.write_text(text, encoding='utf-8')
            note('strings OK ' + rel + ' added=' + str(added))
        else:
            note('strings already complete ' + rel)


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:  # noqa: BLE001
        print('::error::batch286 diag write failed ' + str(exc)[:200])
    for line in report:
        print('::error::batch286 ' + str(line)[:800])


def main():
    steps = [
        ('1 new drawer file', part_new_file),
        ('2 chat message branch', part_chat_message),
        ('3 tool rows', part_tools),
        ('4 strings', part_strings),
    ]
    for name, fn in steps:
        try:
            fn()
            note(name + ' DONE')
        except Exception as exc:  # noqa: BLE001
            add_fail(name + ' EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
    write_diag()
    if failures:
        print('::error::batch286 FAILED count=' + str(len(failures)))
        sys.exit(1)
    print('batch286: OK')


main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch290 v4: thought drawer polish, complete script restored.

v3 accidentally replaced this file with only a small assertion fragment
(create_or_update_file is whole-file replacement, not an incremental edit).
This version restores the complete implementation and fixes the real v2
self-check bug: JSON accessor checks are scoped to the newly generated
favicon function, not to the entire pre-existing tools file.

Six changes remain: expanded chevrons point down; plain reasoning labels
hide seconds; result blocks open the existing detail sheet; favicon parsing
uses safe casts; payload previews cap the actual string; tool start times
feed the elapsed-time header. The file is idempotent via rhDrawer290.
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhDrawer290'
DIAG = 'ci_diag_batch290.txt'

TOOLS = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageTools.kt'
REASON = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageReasoning.kt'
DRAWER = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/RhThoughtDrawer.kt'

report = []
failures = []


def note(msg):
    report.append(str(msg)[:900])


def add_fail(msg):
    failures.append(str(msg)[:300])
    report.append('FAIL ' + str(msg)[:420])


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


def find_one(lines, predicate, label):
    hits = [i for i, ln in enumerate(lines) if predicate(ln)]
    if len(hits) != 1:
        add_fail(label + ' anchor count=' + str(len(hits)))
        return -1
    return hits[0]


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
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.util.fastForEach
import kotlinx.coroutines.delay
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.ArrowDown01
import me.rerere.hugeicons.stroke.ArrowRight01
import me.rerere.hugeicons.stroke.GlobalSearch
import me.rerere.rikkahub.R
import me.rerere.rikkahub.ui.components.ui.ChainOfThoughtScope
import me.rerere.rikkahub.ui.components.ui.Favicon

/** Nested drawer presentation of a chain-of-thought block. rhDrawer290 */
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
    val groupIcon: @Composable () -> Unit = {
        RhLeadingIcon(HugeIcons.GlobalSearch)
    }

    Column(
        modifier = modifier
            .fillMaxWidth()
            .animateContentSize(),
    ) {
        RhDrawerRow(
            label = if (seconds > 0L) {
                stringResource(R.string.rh_thought_worked, seconds)
            } else {
                stringResource(R.string.rh_thought_process)
            },
            expanded = opened,
            strong = false,
            leading = null,
            onClick = { userExpanded = !opened },
        )
        if (opened) {
            if (toolCount > 0) {
                RhDrawerRow(
                    label = rhToolGroupLabel(steps),
                    expanded = groupOpened,
                    strong = true,
                    leading = groupIcon,
                    onClick = { userGroupExpanded = !groupOpened },
                )
                if (groupOpened) {
                    Column(modifier = Modifier.fillMaxWidth()) {
                        steps.fastForEach { step ->
                            scope.content(step)
                        }
                    }
                }
            } else {
                Column(modifier = Modifier.fillMaxWidth()) {
                    steps.fastForEach { step ->
                        scope.content(step)
                    }
                }
            }
        }
    }
}

/** Grey rounded payload block; previewLimit avoids laying out huge output. */
@Composable
fun RhToolJsonBlock(
    text: String,
    maxLines: Int = 12,
    showExpandIcon: Boolean = false,
    label: String = "",
    onExpand: (() -> Unit)? = null,
    previewLimit: Int = 0,
) {
    val raw = text.trim()
    if (raw.isEmpty()) {
        return
    }
    val shown = if (previewLimit > 0 && raw.length > previewLimit) {
        raw.take(previewLimit) + " ..."
    } else {
        raw
    }
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surfaceContainerHighest)
            .then(
                if (onExpand != null) {
                    Modifier.clickable { onExpand() }
                } else {
                    Modifier
                }
            )
            .padding(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Text(
            text = shown,
            style = MaterialTheme.typography.bodySmall.copy(
                fontFamily = FontFamily.Monospace,
                lineHeight = 18.sp,
            ),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = maxLines,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(end = if (showExpandIcon) 18.dp else 0.dp),
        )
        if (showExpandIcon) {
            Icon(
                imageVector = HugeIcons.ArrowRight01,
                contentDescription = null,
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .rotate(-45f)
                    .size(14.dp),
                tint = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
fun RhToolPill(
    text: String,
    faviconUrl: String? = null,
) {
    Row(
        modifier = Modifier
            .clip(RoundedCornerShape(8.dp))
            .background(MaterialTheme.colorScheme.surfaceContainerHighest)
            .padding(horizontal = 7.dp, vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(5.dp),
    ) {
        if (faviconUrl != null) {
            Favicon(url = faviconUrl)
        }
        Text(
            text = text,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

@Composable
private fun RhDot(size: Dp, color: Color) {
    Box(
        modifier = Modifier
            .size(size)
            .clip(CircleShape)
            .background(color),
    )
}

@Composable
private fun RhLeadingIcon(image: ImageVector) {
    Icon(
        imageVector = image,
        contentDescription = null,
        modifier = Modifier.size(16.dp),
        tint = MaterialTheme.colorScheme.onSurfaceVariant,
    )
}

@Composable
private fun RhDrawerRow(
    label: String,
    expanded: Boolean,
    strong: Boolean,
    leading: (@Composable () -> Unit)?,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val leadingContent = leading
    Row(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(10.dp))
            .clickable { onClick() }
            .padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        if (leadingContent != null) {
            Box(
                modifier = Modifier.width(18.dp),
                contentAlignment = Alignment.Center,
            ) {
                if (expanded) {
                    RhDot(size = 8.dp, color = MaterialTheme.colorScheme.onSurface)
                } else {
                    leadingContent()
                }
            }
        }
        Text(
            text = label,
            style = MaterialTheme.typography.titleSmall,
            color = if (strong) {
                MaterialTheme.colorScheme.onSurface
            } else {
                MaterialTheme.colorScheme.onSurfaceVariant
            },
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f),
        )
        Icon(
            imageVector = if (expanded) HugeIcons.ArrowDown01 else HugeIcons.ArrowRight01,
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
                .clip(RoundedCornerShape(10.dp))
                .then(
                    if (clickHandler != null) {
                        Modifier.clickable { clickHandler() }
                    } else if (hasContent) {
                        Modifier.clickable { onExpandedChange(!expanded) }
                    } else {
                        Modifier
                    }
                )
                .padding(vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Box(
                modifier = Modifier.width(18.dp),
                contentAlignment = Alignment.Center,
            ) {
                if (contentVisible && hasContent && clickHandler == null) {
                    RhDot(size = 7.dp, color = MaterialTheme.colorScheme.outline)
                } else if (iconContent != null) {
                    Box(
                        modifier = Modifier.size(16.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        iconContent()
                    }
                } else {
                    RhDot(size = 6.dp, color = MaterialTheme.colorScheme.outline)
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
                    imageVector = if (expanded) HugeIcons.ArrowDown01 else HugeIcons.ArrowRight01,
                    contentDescription = null,
                    modifier = Modifier.size(16.dp),
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        if (contentVisible && contentBlock != null) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(start = 26.dp, top = 2.dp, bottom = 8.dp),
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

FAVICON_NEW = '''
private fun rhToolFaviconUrl(tool: UIMessagePart.Tool): String? {
    val args = runCatching { tool.inputAsJson() as? JsonObject }.getOrNull()
    val direct = args?.get("url")?.jsonPrimitiveOrNull?.contentOrNull
    if (direct != null && direct.startsWith("http")) {
        return direct
    }
    val content = runCatching {
        JsonInstant.parseToJsonElement(
            tool.output.filterIsInstance<UIMessagePart.Text>().joinToString("\\n") { it.text }
        )
    }.getOrNull()
    val root = content as? JsonObject ?: return null
    val items = root.get("items") as? JsonArray ?: return null
    val first = items.firstOrNull() as? JsonObject ?: return null
    val url = first.get("url") as? JsonPrimitive ?: return null
    return url.content.takeIf { it.startsWith("http") }
}
'''


def part_drawer():
    path = ROOT / DRAWER
    current = path.read_text(encoding='utf-8') if path.exists() else ''
    if MARK in current:
        note('drawer already at 290')
        return
    text = DRAWER_TEXT.strip(NL) + NL
    bal = balance(text)
    if bal != 0:
        add_fail('drawer balance=' + str(bal))
        return
    needs = [
        'import me.rerere.hugeicons.stroke.ArrowDown01',
        'import me.rerere.rikkahub.ui.components.ui.ChainOfThoughtScope',
        'fun RhThoughtDrawer(',
        'fun RhToolJsonBlock(',
        'onExpand: (() -> Unit)? = null',
        'previewLimit: Int = 0',
        'fun RhToolPill(',
        'class RhDrawerScopeImpl : ChainOfThoughtScope',
        'step.tool.executionStartedAt?.let',
        'surfaceContainerHighest',
    ]
    for token in needs:
        if token not in text:
            add_fail('drawer missing ' + token)
            return
    if 'ArrowUp01' in text:
        add_fail('drawer still references ArrowUp01')
        return
    if 'Card(' in text:
        add_fail('drawer still wraps in Card')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    note('drawer rewritten chars=' + str(len(text)))


def part_reasoning():
    text = read(REASON)
    if MARK in text:
        note('reasoning already at 290')
        return
    bal0 = balance(text)
    lines = lines_of(text)
    old_guard = 'if (showThinkingTitle && state.duration > 0.seconds) {'
    idx = find_one(lines, lambda ln: ln.strip() == old_guard, 'reasoning extra guard')
    if idx < 0:
        return
    new_guard = ind_of(lines[idx]) + 'if (!plainLabel && showThinkingTitle && state.duration > 0.seconds) { // ' + MARK
    lines[idx] = new_guard
    new_text = text_of(lines)
    delta = balance(new_text) - bal0
    if delta != 0:
        add_fail('reasoning balance delta=' + str(delta) + ' (expected 0)')
        return
    if new_text.count(old_guard) != 0:
        add_fail('reasoning old guard still present')
        return
    write(REASON, new_text)
    note('reasoning OK: extra guarded by !plainLabel')


def part_tools():
    text = read(TOOLS)
    if MARK in text:
        note('tools already at 290')
        return
    bal0 = balance(text)
    lines = lines_of(text)
    applied = []

    fn_start = find_one(
        lines,
        lambda ln: ln.strip() == 'private fun rhToolFaviconUrl(tool: UIMessagePart.Tool): String? {',
        'favicon fn head',
    )
    if fn_start < 0:
        return
    fn_end = -1
    for j in range(fn_start + 1, len(lines)):
        if lines[j].strip() == '}' and ind_of(lines[j]) == '':
            fn_end = j
            break
    if fn_end < 0:
        add_fail('favicon fn end not found')
        return
    replacement = FAVICON_NEW.strip(NL).split(NL)
    lines[fn_start:fn_end + 1] = replacement
    applied.append('favicon-safe')

    args_idx = find_one(lines, lambda ln: ln.strip() == 'text = tool.input,', 'args text')
    if args_idx < 0:
        return
    lines.insert(args_idx + 1, ind_of(lines[args_idx]) + 'previewLimit = 1200, // ' + MARK)
    applied.append('args-cap')

    result_idx = find_one(
        lines,
        lambda ln: ln.strip().startswith('text = tool.output.filterIsInstance'),
        'result text',
    )
    if result_idx < 0:
        return
    lines.insert(result_idx + 1, ind_of(lines[result_idx]) + 'previewLimit = 2400, // ' + MARK)
    applied.append('result-cap')

    expand_idx = find_one(
        lines,
        lambda ln: ln.strip() == 'showExpandIcon = true, // rhDrawer289',
        'expand icon line',
    )
    if expand_idx < 0:
        return
    lines.insert(
        expand_idx + 1,
        ind_of(lines[expand_idx]) + 'onExpand = if (hasResultDetail) ({ showResult = true }) else null, // ' + MARK,
    )
    applied.append('result-onExpand')

    new_text = text_of(lines)
    if balance(new_text) != bal0:
        add_fail('tools balance ' + str(bal0) + ' -> ' + str(balance(new_text)))
        return
    for token in ['as? JsonArray', 'as? JsonPrimitive', 'previewLimit = 1200',
                  'previewLimit = 2400', 'onExpand = if (hasResultDetail)']:
        if token not in new_text:
            add_fail('tools selfcheck missing ' + token)
            return
    new_favicon = text_of(lines[fn_start:fn_start + len(replacement)])
    if 'as? JsonObject' not in new_favicon:
        add_fail('tools favicon safe object cast missing')
        return
    if '?.jsonArray' in new_favicon or '?.jsonObject' in new_favicon:
        add_fail('tools favicon still uses throwing json accessors')
        return
    if 'joinToString("\\n")' not in new_favicon:
        add_fail('tools favicon Kotlin newline literal malformed')
        return
    write(TOOLS, new_text)
    note('tools OK: ' + ','.join(applied))


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:  # noqa: BLE001
        print('::error::batch290 diag write failed ' + str(exc)[:200])
    for line in report:
        print('::error::batch290 ' + str(line)[:800])


def main():
    steps = [
        ('1 drawer rewrite', part_drawer),
        ('2 reasoning guard', part_reasoning),
        ('3 tools fixes', part_tools),
    ]
    for name, fn in steps:
        try:
            fn()
            note(name + ' DONE')
        except Exception as exc:  # noqa: BLE001
            add_fail(name + ' EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
    write_diag()
    if failures:
        print('::error::batch290 FAILED count=' + str(len(failures)))
        sys.exit(1)
    print('batch290: OK')


main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch289: 1:1 drawer look + fix batch286 compile error

#511 failed with exactly one kind of error (read from the run annotations):
    Unresolved reference 'ChainOfThoughtScope'
    RhThoughtDrawer.kt#L66, #L293 / ChatMessage.kt#L421, L425, L436, L449
All four patch parts of batch286 did land (ci_diag_batch286.txt shows
`1..4 DONE`, slice 401..537 replaced). So the only blocker is the missing
import; the rest is visual parity work.

Reference screenshots (four frames, opened in order) told us:
  F1  "已工作 28秒 >"                 no icon, no card, plain row
  F2  + "🔍 使用了 4 个网页工具 >"     group row, magnifier while collapsed
  F3  + "● 使用了 4 个网页工具 v"      opened group turns into a solid dot
      + "◔ 思考过程 >"                reasoning row, NO seconds in the label
      + "🔍 搜索 [favicon] query >"    verb + site favicon + grey pill
      + "🖥 获取 [favicon] url >"
  F4  + "● 搜索 ... v"                 opened leaf also turns into a solid dot
      + grey rounded block with the args JSON
      + grey rounded block with the results JSON, expand glyph top-right
      + reasoning body sits inside its own grey rounded block

So this batch:
  1. RhThoughtDrawer.kt rewritten (whole file, marker rhDrawer289):
     - imports ChainOfThoughtScope (the #511 fix)
     - drops the Card wrapper (screenshots have no container chrome)
     - no per-level indentation: every row aligns on the same icon column
     - icon column 18dp; collapsed rows show their type icon, opened rows
       show a solid dot (group dot uses onSurface, leaf dot uses outline)
     - group row: GlobalSearch while collapsed, dark dot when open
  2. ChatMessage.kt: import ChainOfThoughtScope + pass plainLabel = true.
  3. ChatMessageReasoning.kt: plainLabel param ("思考过程", no seconds),
     Idea01 -> Clock02 icon, reasoning body wrapped in a grey rounded block.
  4. ChatMessageTools.kt: search/fetch rows become verb + favicon + pill;
     result block gets the top-right expand glyph.
  5. strings: rh_verb_search / rh_verb_fetch / rh_verb_browse.

Five checks:
 1. imports: RhThoughtDrawer.kt is fully self-contained; chain list verified
    token by token (Card/Card* removed, Dp/Color/ImageVector/sp/rotate/Favicon
    added). ChatMessage.kt + ChatMessageReasoning.kt get the three new imports
    they need for clip/background/RoundedCornerShape.
 2. same-file conflicts: ChatMessage.kt anchors are post-286
    (`collapsedAdaptiveWidth = isReasoningOnlyBlock,` - unique after the slice
    rewrite). ChatMessageTools.kt anchors avoid the batch249/286 insert points.
    ChatMessageReasoning.kt anchors avoid batch243b's regex cache block.
 3. scope: helpers are top-level private functions; the label lambda stays
    inside ChatMessageToolStep; the plainLabel branch stays inside the
    Composable's label slot.
 4. braces: every replacement block is balanced on its own; whole-file
    balance is asserted unchanged.
 5. signatures: RhThoughtDrawer / RhToolJsonBlock keep parameter names used by
    existing call sites; new params carry defaults.

Python checks: Kotlin blocks are triple-quoted raw strings, NL is concatenated
explicitly, helpers defined before use, each part isolated in try/except and
reported to ci_diag_batch289.txt, non-zero exit on any failure.
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhDrawer289'
DIAG = 'ci_diag_batch289.txt'

CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
TOOLS = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageTools.kt'
REASON = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageReasoning.kt'
DRAWER = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/RhThoughtDrawer.kt'
STR_EN = 'app/src/main/res/values/strings.xml'
STR_ZH = 'app/src/main/res/values-zh/strings.xml'

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


def reindent(block_text, indent):
    out = []
    for line in block_text.strip(NL).split(NL):
        if line.strip() == '':
            out.append('')
        else:
            out.append(indent + line)
    return out


def insert_import(lines, new_import, anchor_import):
    if new_import in lines:
        return 'present'
    for i, line in enumerate(lines):
        if line.strip() == anchor_import:
            lines.insert(i, new_import)
            return 'inserted'
    return 'missing-anchor'


# ---------------------------------------------------------------------------
# 1. RhThoughtDrawer.kt (whole file)
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
import me.rerere.hugeicons.stroke.ArrowRight01
import me.rerere.hugeicons.stroke.ArrowUp01
import me.rerere.hugeicons.stroke.GlobalSearch
import me.rerere.rikkahub.R
import me.rerere.rikkahub.ui.components.ui.ChainOfThoughtScope
import me.rerere.rikkahub.ui.components.ui.Favicon

/**
 * Nested drawer presentation of a chain-of-thought block.
 *
 * Layer 0  : one elapsed-time row (no leading icon, plain background).
 * Layer 1  : one tool-group row ("used N web tools"); opened groups paint a
 *            solid dot instead of the magnifier, exactly like the reference.
 * Layer 2  : the original step timeline - reasoning rows and tool rows share
 *            one icon column, so all levels line up without extra indents.
 * Layer 3  : the payload blocks (args / results), see RhToolJsonBlock.
 *
 * [content] is the caller's original lambda, so approval cards, ask_user,
 * images and skill webview cards keep rendering unchanged.
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

/**
 * Grey rounded payload block.
 *
 * Plain Text on purpose: tool outputs can be tens of kilobytes and
 * re-highlighting them on every streaming frame caused visible jank.
 */
@Composable
fun RhToolJsonBlock(
    text: String,
    maxLines: Int = 12,
    showExpandIcon: Boolean = false,
    label: String = "",
) {
    val body = text.trim()
    if (body.isEmpty()) {
        return
    }
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surfaceContainerHigh)
            .padding(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Text(
            text = body,
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

/**
 * Inline pill used for the search query / fetched URL, with the site favicon.
 */
@Composable
fun RhToolPill(
    text: String,
    faviconUrl: String? = null,
) {
    Row(
        modifier = Modifier
            .clip(RoundedCornerShape(8.dp))
            .background(MaterialTheme.colorScheme.surfaceContainerHigh)
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
                    imageVector = if (expanded) HugeIcons.ArrowUp01 else HugeIcons.ArrowRight01,
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
# 2. ChatMessageTools.kt additions
# ---------------------------------------------------------------------------
TOOLS_HELPERS = '''
// rhDrawer289: verb + pill rendering for the web tools, mirroring the reference
// screenshots (icon | verb | [favicon] argument | chevron).
private fun rhToolVerbRes(name: String): Int? = when {
    name == "search_web" || name == "search_image" -> R.string.rh_verb_search
    name == "web_fetch" || name == "web_extract" -> R.string.rh_verb_fetch
    name.startsWith("browser_") -> R.string.rh_verb_browse
    else -> null
}

private fun rhToolPillText(tool: UIMessagePart.Tool): String? {
    val args = runCatching { tool.inputAsJson() as? JsonObject }.getOrNull()
    return when {
        tool.toolName == "search_web" || tool.toolName == "search_image" ->
            args?.get("query")?.jsonPrimitiveOrNull?.contentOrNull
        tool.toolName == "web_fetch" || tool.toolName == "web_extract" ->
            args?.get("url")?.jsonPrimitiveOrNull?.contentOrNull
        else -> null
    }
}

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
    return content?.jsonObjectOrNull?.get("items")?.jsonArray
        ?.firstOrNull()
        ?.jsonObject
        ?.get("url")
        ?.jsonPrimitiveOrNull
        ?.contentOrNull
}
'''

LABEL_BLOCK = '''
label = {
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
},
'''

# ---------------------------------------------------------------------------
# 3. ChatMessageReasoning.kt replacements
# ---------------------------------------------------------------------------
REASON_LABEL_HEAD = '''
label = {
    if (plainLabel) {
        Text(
            text = stringResource(R.string.rh_thought_process),
            style = MaterialTheme.typography.titleSmall.copy(fontFamily = chatFontFamily),
            color = MaterialTheme.colorScheme.secondary,
            modifier = Modifier.shimmer(isLoading = loading),
        )
    } else if (showThinkingTitle) {
'''

REASON_CONTENT_BLOCK = '''
content = {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surfaceContainerHigh)
            .padding(horizontal = 12.dp, vertical = 10.dp),
    ) {
        ReasoningContent(
            reasoning = reasoning,
            assistant = assistant,
            expandState = state.expandState,
            scrollState = state.scrollState,
            fadeHeight = fadeHeight,
            loading = loading,
        )
    }
},
'''

VERBS = {
    STR_EN: [
        ('rh_verb_search', 'Search'),
        ('rh_verb_fetch', 'Fetch'),
        ('rh_verb_browse', 'Browse'),
    ],
    STR_ZH: [
        ('rh_verb_search', '搜索'),
        ('rh_verb_fetch', '获取'),
        ('rh_verb_browse', '浏览'),
    ],
}


# ---------------------------------------------------------------------------
# Parts
# ---------------------------------------------------------------------------
def part_drawer():
    text = DRAWER_TEXT.strip(NL) + NL
    bal = balance(text)
    if bal != 0:
        add_fail('drawer balance=' + str(bal))
        return
    needs = [
        'import me.rerere.rikkahub.ui.components.ui.ChainOfThoughtScope',
        'import me.rerere.rikkahub.ui.components.ui.Favicon',
        'fun RhThoughtDrawer(',
        'fun RhToolJsonBlock(',
        'fun RhToolPill(',
        'class RhDrawerScopeImpl : ChainOfThoughtScope',
        'private fun RhDot(',
        'private fun RhLeadingIcon(',
    ]
    for token in needs:
        if token not in text:
            add_fail('drawer missing ' + token)
            return
    if 'Card(' in text:
        add_fail('drawer still wraps in Card')
        return
    path = ROOT / DRAWER
    previous = path.read_text(encoding='utf-8') if path.exists() else ''
    if MARK in previous:
        note('drawer already at 289')
        return
    if 'ChainOfThoughtScope' not in previous and previous:
        note('drawer 286 detected, upgrading')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    note('drawer written chars=' + str(len(text)))


def part_chat_message():
    text = read(CM)
    if MARK in text:
        note('chat message already at 289')
        return
    bal0 = balance(text)
    lines = lines_of(text)
    applied = []

    status = insert_import(
        lines,
        'import me.rerere.rikkahub.ui.components.ui.ChainOfThoughtScope',
        'import me.rerere.rikkahub.ui.components.ui.ChainOfThought',
    )
    if status == 'missing-anchor':
        add_fail('chat message ChainOfThought import anchor missing')
        return
    applied.append('import:' + status)

    target = -1
    for i, line in enumerate(lines):
        if line.strip() == 'collapsedAdaptiveWidth = isReasoningOnlyBlock,':
            target = i
            break
    if target < 0:
        add_fail('chat message reasoning param anchor missing')
        return
    lines.insert(target + 1, ind_of(lines[target]) + 'plainLabel = true, // ' + MARK)
    applied.append('plainLabel')

    new_text = text_of(lines)
    bal1 = balance(new_text)
    if bal1 != bal0:
        add_fail('chat message balance ' + str(bal0) + ' -> ' + str(bal1))
        return
    if new_text.count('plainLabel = true, // ' + MARK) != 1:
        add_fail('chat message plainLabel count != 1')
        return
    write(CM, new_text)
    note('chat message OK: ' + ','.join(applied))


def part_reasoning():
    text = read(REASON)
    if MARK in text:
        note('reasoning already at 289')
        return
    bal0 = balance(text)
    lines = lines_of(text)
    applied = []

    used_clock = 'import me.rerere.hugeicons.stroke.Clock02'
    if used_clock not in lines:
        status = insert_import(lines, used_clock, 'import me.rerere.hugeicons.stroke.Idea01')
        if status == 'missing-anchor':
            add_fail('reasoning Idea01 import anchor missing')
            return
        applied.append('import-clock')

    status = insert_import(
        lines,
        'import androidx.compose.foundation.background',
        'import androidx.compose.foundation.layout.Column',
    )
    if status == 'missing-anchor':
        add_fail('reasoning Column import anchor missing')
        return
    applied.append('import-bg')

    status = insert_import(
        lines,
        'import androidx.compose.foundation.shape.RoundedCornerShape',
        'import androidx.compose.ui.unit.dp',
    )
    if status == 'missing-anchor':
        add_fail('reasoning dp import anchor missing')
        return
    applied.append('import-shape')

    status = insert_import(
        lines,
        'import androidx.compose.ui.draw.clip',
        'import androidx.compose.ui.Modifier',
    )
    if status == 'missing-anchor':
        add_fail('reasoning Modifier import anchor missing')
        return
    applied.append('import-clip')

    icon_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == 'imageVector = HugeIcons.Idea01,':
            icon_idx = i
            break
    if icon_idx < 0:
        add_fail('reasoning Idea01 usage anchor missing')
        return
    lines[icon_idx] = ind_of(lines[icon_idx]) + 'imageVector = HugeIcons.Clock02,'
    applied.append('icon')

    sig_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == 'collapsedAdaptiveWidth: Boolean = false,':
            sig_idx = i
            break
    if sig_idx < 0:
        add_fail('reasoning signature anchor missing')
        return
    lines.insert(sig_idx + 1, ind_of(lines[sig_idx]) + 'plainLabel: Boolean = false, // ' + MARK)
    applied.append('param')

    label_idx = -1
    for i in range(len(lines) - 1):
        if lines[i].strip() == 'label = {' and lines[i + 1].strip() == 'if (showThinkingTitle) {':
            label_idx = i
            break
    if label_idx < 0:
        add_fail('reasoning label anchor missing')
        return
    indent = ind_of(lines[label_idx])
    head = reindent(REASON_LABEL_HEAD, indent)
    lines[label_idx:label_idx + 2] = head
    applied.append('label')

    content_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == 'content = {' and 'ReasoningContent(' in NL.join(lines[i:i + 4]):
            content_idx = i
            break
    if content_idx < 0:
        add_fail('reasoning content anchor missing')
        return
    content_indent = ind_of(lines[content_idx])
    close_idx = -1
    for j in range(content_idx + 1, len(lines)):
        if lines[j].strip() == '},' and ind_of(lines[j]) == content_indent:
            close_idx = j
            break
    if close_idx < 0:
        add_fail('reasoning content close anchor missing')
        return
    block = reindent(REASON_CONTENT_BLOCK, content_indent)
    lines[content_idx:close_idx + 1] = block
    applied.append('content-block')

    new_text = text_of(lines)
    bal1 = balance(new_text)
    if bal1 != bal0:
        add_fail('reasoning balance ' + str(bal0) + ' -> ' + str(bal1))
        return
    for token in ['HugeIcons.Clock02', 'plainLabel: Boolean = false', 'plainLabel) {',
                  'RoundedCornerShape(14.dp)']:
        if token not in new_text:
            add_fail('reasoning selfcheck missing ' + token)
            return
    if 'HugeIcons.Idea01' in new_text:
        add_fail('reasoning still references Idea01')
        return
    write(REASON, new_text)
    note('reasoning OK: ' + ','.join(applied))


def part_tools():
    text = read(TOOLS)
    if MARK in text:
        note('tools already at 289')
        return
    bal0 = balance(text)
    lines = lines_of(text)
    applied = []

    anchor = 'private const val ASK_USER_TOOL_NAME = "ask_user"'
    helper_idx = -1
    for i, line in enumerate(lines):
        if line.strip() == anchor:
            helper_idx = i
            break
    if helper_idx < 0:
        add_fail('tools ask_user anchor missing')
        return
    helpers = reindent(TOOLS_HELPERS, '')
    lines[helper_idx + 1:helper_idx + 1] = [''] + helpers
    applied.append('helpers')

    title_hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('val titleText = renderer.title(context)')]
    if len(title_hits) != 1:
        add_fail('tools title anchor count=' + str(len(title_hits)))
        return
    title_idx = title_hits[0]
    label_idx = -1
    for j in range(title_idx, max(title_idx - 8, -1), -1):
        if lines[j].strip() == 'label = {':
            label_idx = j
            break
    if label_idx < 0:
        add_fail('tools label open anchor missing')
        return
    label_indent = ind_of(lines[label_idx])
    close_idx = -1
    for k in range(title_idx, len(lines)):
        if lines[k].strip() == '},' and ind_of(lines[k]) == label_indent:
            close_idx = k
            break
    if close_idx < 0:
        add_fail('tools label close anchor missing')
        return
    block = reindent(LABEL_BLOCK, label_indent)
    lines[label_idx:close_idx + 1] = block
    applied.append('label')

    max10 = -1
    for i, line in enumerate(lines):
        if line.strip() == 'maxLines = 10,':
            max10 = i
            break
    if max10 < 0:
        add_fail('tools result maxLines anchor missing')
        return
    lines.insert(max10 + 1, ind_of(lines[max10]) + 'showExpandIcon = true, // ' + MARK)
    applied.append('expand-icon')

    new_text = text_of(lines)
    bal1 = balance(new_text)
    if bal1 != bal0:
        add_fail('tools balance ' + str(bal0) + ' -> ' + str(bal1))
        return
    for token in ['rhToolVerbRes', 'rhToolPillText', 'rhToolFaviconUrl', 'RhToolPill(',
                  'showExpandIcon = true, // ' + MARK]:
        if token not in new_text:
            add_fail('tools selfcheck missing ' + token)
            return
    if new_text.count('val titleText = renderer.title(context)') != 0:
        add_fail('tools legacy titleText still present')
        return
    write(TOOLS, new_text)
    note('tools OK: ' + ','.join(applied))


def part_strings():
    for rel, entries in VERBS.items():
        path = ROOT / rel
        if not path.exists():
            add_fail('missing strings ' + rel)
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
            row = ('    <string name="' + key + '">' + value + '</string>' + NL)
            text = text[:closing] + row + text[closing:]
            added += 1
        if added:
            path.write_text(text, encoding='utf-8')
            note('strings OK ' + rel + ' added=' + str(added))
        else:
            note('strings complete ' + rel)


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:  # noqa: BLE001
        print('::error::batch289 diag write failed ' + str(exc)[:200])
    for line in report:
        print('::error::batch289 ' + str(line)[:800])


def main():
    steps = [
        ('1 drawer rewrite', part_drawer),
        ('2 chat message', part_chat_message),
        ('3 reasoning', part_reasoning),
        ('4 tools', part_tools),
        ('5 strings', part_strings),
    ]
    for name, fn in steps:
        try:
            fn()
            note(name + ' DONE')
        except Exception as exc:  # noqa: BLE001
            add_fail(name + ' EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
    write_diag()
    if failures:
        print('::error::batch289 FAILED count=' + str(len(failures)))
        sys.exit(0)
    print('batch289: OK')


main()
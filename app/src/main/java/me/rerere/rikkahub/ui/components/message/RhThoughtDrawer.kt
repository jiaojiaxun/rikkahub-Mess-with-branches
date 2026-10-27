package me.rerere.rikkahub.ui.components.message
// rhDrawer295
// rhDrawer294
// rhDrawer292
// rhDrawer290

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
import me.rerere.hugeicons.stroke.ArrowDown01
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
    val opened = userExpanded || forceExpanded // rhDrawer293: default collapsed
    val groupOpened = userGroupExpanded || forceExpanded // rhDrawer293: group default collapsed
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
        RhThoughtHeader(
            steps = steps,
            loading = loading,
            expanded = opened,
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
    val start = remember(steps) { rhStepsStartMillis(steps, true) }
    val recordedEnd = remember(steps) { rhStepsEndMillis(steps) }
    val active = loading && steps.any { step ->
        when (step) {
            is ThinkingStep.ReasoningStep -> step.reasoning.finishedAt == null
            is ThinkingStep.ToolStep -> !step.tool.isExecuted
            is ThinkingStep.ServerToolStep -> !step.tool.isFinished
        }
    }
    var tick by remember { mutableStateOf(0L) }
    var frozenEnd by remember { mutableStateOf(0L) }
    var wasActive by remember { mutableStateOf(false) }

    LaunchedEffect(active) {
        if (active) {
            wasActive = true
            frozenEnd = 0L
            while (true) {
                tick = System.currentTimeMillis()
                delay(1000L)
            }
        } else {
            tick = System.currentTimeMillis()
            if (wasActive && frozenEnd == 0L) {
                frozenEnd = tick
            }
        }
    }

    if (start == null || start <= 0L) {
        return 0L
    }
    val end = when {
        active -> maxOf(tick, start)
        frozenEnd > 0L -> maxOf(frozenEnd, recordedEnd ?: 0L)
        recordedEnd != null -> recordedEnd
        else -> return 0L
    }
    val delta = end - start
    if (delta <= 0L) {
        return 0L
    }
    return delta / 1000L
}

private fun rhStepsStartMillis(steps: List<ThinkingStep>, includeTools: Boolean): Long? {
    val candidates = mutableListOf<Long>()
    steps.filterIsInstance<ThinkingStep.ReasoningStep>().forEach { step ->
        candidates.add(step.reasoning.createdAt.toEpochMilliseconds())
    }
    if (includeTools) {
        steps.filterIsInstance<ThinkingStep.ToolStep>().forEach { step ->
            step.tool.executionStartedAt?.let { stamp ->
                candidates.add(stamp)
            }
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

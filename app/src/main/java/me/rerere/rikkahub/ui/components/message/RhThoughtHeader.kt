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

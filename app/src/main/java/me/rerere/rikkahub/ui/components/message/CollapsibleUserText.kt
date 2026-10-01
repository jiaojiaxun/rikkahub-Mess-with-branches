package me.rerere.rikkahub.ui.components.message

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import me.rerere.rikkahub.R

/** Approximate rendered height of one line of chat text, used for the collapsed height. */
private const val LINE_HEIGHT_DP = 22

/** Characters that roughly fill one line of a user bubble (CJK text wraps sooner). */
private const val CHARS_PER_LINE = 40

/**
 * Collapses a long user message to [maxLines] lines with an expand / collapse toggle.
 * Short messages, or [enabled] false, render [content] unchanged.
 */
@Composable
fun CollapsibleUserText(
    text: String,
    enabled: Boolean,
    maxLines: Int,
    content: @Composable () -> Unit,
) {
    val lines = maxLines.coerceIn(3, 50)
    val estimatedLines = text.lines().sumOf { line -> 1 + line.length / CHARS_PER_LINE }
    if (!enabled || estimatedLines <= lines) {
        content()
        return
    }
    var expanded by rememberSaveable(text) { mutableStateOf(false) }
    Column {
        Box(
            modifier = if (expanded) {
                Modifier
            } else {
                Modifier
                    .heightIn(max = (lines * LINE_HEIGHT_DP).dp)
                    .clipToBounds()
            },
        ) {
            content()
        }
        TextButton(
            onClick = { expanded = !expanded },
            contentPadding = PaddingValues(horizontal = 4.dp, vertical = 0.dp),
        ) {
            Text(
                text = stringResource(
                    if (expanded) R.string.chat_message_collapse else R.string.chat_message_expand
                ),
                style = MaterialTheme.typography.labelMedium,
            )
        }
    }
}

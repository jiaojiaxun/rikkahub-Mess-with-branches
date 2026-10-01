package me.rerere.rikkahub.ui.components.ai

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import me.rerere.rikkahub.R
import me.rerere.rikkahub.data.ai.CompactionPreviewStore
import kotlin.uuid.Uuid

/**
 * Shows the compression model's reply while it streams. Renders nothing when no compaction
 * is running. [conversationId] null shows every running compaction.
 */
@Composable
fun CompactionStreamPreview(
    conversationId: Uuid?,
    modifier: Modifier = Modifier,
) {
    val all by CompactionPreviewStore.previews.collectAsState()
    val text = remember(all, conversationId) {
        val slots = if (conversationId != null) {
            all[conversationId].orEmpty().values.toList()
        } else {
            all.values.flatMap { it.values }
        }
        slots.filter { it.isNotBlank() }.joinToString("\n\n———\n\n")
    }
    if (text.isBlank()) return

    val scroll = rememberScrollState()
    // Keep the newest output in view while the reply grows.
    LaunchedEffect(scroll) {
        snapshotFlow { scroll.maxValue }.collect { scroll.scrollTo(it) }
    }
    Surface(
        modifier = modifier,
        shape = RoundedCornerShape(12.dp),
        color = MaterialTheme.colorScheme.surfaceContainerHigh,
    ) {
        Column(modifier = Modifier.padding(10.dp)) {
            Text(
                text = stringResource(R.string.compaction_stream_title),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary,
            )
            Text(
                text = text,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                modifier = Modifier
                    .padding(top = 4.dp)
                    .heightIn(max = 220.dp)
                    .verticalScroll(scroll),
            )
        }
    }
}

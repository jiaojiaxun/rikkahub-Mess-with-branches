package me.rerere.rikkahub.ui.components.message

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ProvideTextStyle
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.annotation.VisibleForTesting
import kotlinx.datetime.toJavaLocalDateTime
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.Clock02
import me.rerere.hugeicons.stroke.CoinsDollar
import me.rerere.hugeicons.stroke.Download04
import me.rerere.hugeicons.stroke.Upload02
import me.rerere.hugeicons.stroke.Zap
import me.rerere.rikkahub.R
import me.rerere.rikkahub.ui.context.LocalSettings
import me.rerere.rikkahub.data.model.ModelContextLengthResolver
import me.rerere.rikkahub.ui.pages.chat.ChatHtmlLayout
import me.rerere.rikkahub.ui.pages.chat.rhReadableOnSkin
import org.koin.compose.koinInject
import me.rerere.rikkahub.utils.formatNumber
import me.rerere.rikkahub.utils.toFixed
import java.time.Duration

/**
 * 显示消息的技术统计信息（如 token 使用量）
 */
@Composable
fun ChatMessageNerdLine(
    message: UIMessage,
    modifier: Modifier = Modifier,
    contextLength: Int? = null,
    modelIdentifier: String? = null,
    estimatedContextTokens: Int? = null,
    color: Color = MaterialTheme.colorScheme.secondary.copy(alpha = 0.5f),
) {
    if (message.role == me.rerere.ai.core.MessageRole.ASSISTANT) { // rhDshFootnote323
        val rhSteps = message.parts.count { it is UIMessagePart.Tool }
        val rhRounds = rhSteps + 1
        Text(
            text = rhSteps.toString() + " 步 · " + rhRounds.toString() + " 轮",
            style = MaterialTheme.typography.labelSmall.copy(color = color),
            modifier = modifier.padding(horizontal = 4.dp),
        )
    }

}

/**
 * Time window (ms) the speed is computed over, or null when no meaningful speed exists.
 * Measured streaming time wins; the whole-message span is only a fallback for messages
 * without tool calls (older messages saved before generationMillis existed), because with
 * tools it mixes several requests and the waits between them.
 */
@VisibleForTesting
internal fun tpsWindowMillis(generationMillis: Long?, totalMillis: Long?, hasTools: Boolean): Long? = when {
    generationMillis != null && generationMillis > 0 -> generationMillis
    !hasTools && totalMillis != null && totalMillis > 0 -> totalMillis
    else -> null
}

// Generation cost is often a tiny fraction of a cent, so a fixed decimal count would show
// "$0.0000". Render up to 6 decimals and trim trailing zeros (e.g. "$0.0123", "$0.000045").
// A positive cost smaller than 1e-6 would round to zero at 6dp and read as "$0" (free), which
// is misleading; clamp those to a "<$0.000001" form so a real charge never displays as free.
@VisibleForTesting
internal fun formatCost(cost: Double): String {
    val rounded = java.math.BigDecimal(cost)
        .setScale(6, java.math.RoundingMode.HALF_UP)
    if (cost > 0.0 && rounded.signum() == 0) {
        return "<$0.000001"
    }
    val s = rounded.stripTrailingZeros().toPlainString()
    return "$" + s
}

@Composable
fun StatsItem(
    icon: @Composable () -> Unit,
    content: @Composable () -> Unit
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(1.dp),
    ) {
        icon()
        content()
    }
}

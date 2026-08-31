package me.rerere.rikkahub.data.ai.context

import me.rerere.ai.provider.Model
import me.rerere.ai.registry.ContextWindowRegistry
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart

object ContextUsageCalculator {
    private const val DEFAULT_RESERVED_OUTPUT_TOKENS = 4_096L

    fun calculate(
        messages: List<UIMessage>,
        model: Model?,
        userContextWindowOverride: Long? = null,
        reservedOutputTokens: Long = DEFAULT_RESERVED_OUTPUT_TOKENS,
    ): ContextUsageEstimate {
        val localEstimate = ConversationTokenEstimator.estimate(messages)
        val usageIndex = messages.indexOfLast { (it.usage?.promptTokens ?: 0) > 0 }
        val actualPromptTokens = messages.getOrNull(usageIndex)
            ?.usage
            ?.promptTokens
            ?.toLong()
            ?.takeIf { it > 0L }

        val estimatedInputTokens = if (usageIndex >= 0 && actualPromptTokens != null) {
            actualPromptTokens +
                estimatePostUsageToolOutputs(messages[usageIndex]) +
                ConversationTokenEstimator.estimate(messages.drop(usageIndex + 1)).tokens
        } else {
            localEstimate.tokens
        }

        val (window, source) = resolveWindow(model, userContextWindowOverride)
        return ContextUsageEstimate.create(
            estimatedInputTokens = estimatedInputTokens,
            actualPromptTokens = actualPromptTokens,
            contextWindowTokens = window,
            reservedOutputTokens = reservedOutputTokens,
            approximate = usageIndex < 0 || usageIndex < messages.lastIndex ||
                localEstimate.uncountedMultimodalParts > 0,
            contextWindowSource = source,
            uncountedMultimodalParts = localEstimate.uncountedMultimodalParts,
        )
    }

    private fun resolveWindow(
        model: Model?,
        userContextWindowOverride: Long?,
    ): Pair<Long?, ContextWindowSource> {
        userContextWindowOverride?.takeIf { it > 0L }?.let {
            return it to ContextWindowSource.UserOverride
        }
        model?.contextLength?.takeIf { it > 0 }?.let {
            return it.toLong() to ContextWindowSource.ProviderMetadata
        }
        model?.modelId?.let(ContextWindowRegistry::resolve)?.let {
            return it to ContextWindowSource.BuiltInRegistry
        }
        return null to ContextWindowSource.Unknown
    }

    @Suppress("DEPRECATION")
    private fun estimatePostUsageToolOutputs(message: UIMessage): Long = message.parts.sumOf { part ->
        when (part) {
            is UIMessagePart.Tool -> ConversationTokenEstimator.estimate(
                listOf(message.copy(parts = part.output, usage = null))
            ).tokens.coerceAtLeast(4L) - 4L
            is UIMessagePart.ToolResult -> ApproximateTokenEstimator.estimateText(part.content.toString())
            else -> 0L
        }
    }
}

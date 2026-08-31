package me.rerere.rikkahub.data.ai.context

data class ContextUsageEstimate(
    val estimatedInputTokens: Long = 0L,
    val actualPromptTokens: Long? = null,
    val contextWindowTokens: Long? = null,
    val reservedOutputTokens: Long = 0L,
    val remainingTokens: Long? = null,
    val usageRatio: Float? = null,
    val level: ContextUsageLevel = ContextUsageLevel.Unknown,
    val approximate: Boolean = true,
    val contextWindowSource: ContextWindowSource = ContextWindowSource.Unknown,
    val uncountedMultimodalParts: Int = 0,
) {
    val progress: Float get() = usageRatio?.coerceIn(0f, 1f) ?: 0f

    companion object {
        fun create(
            estimatedInputTokens: Long,
            actualPromptTokens: Long? = null,
            contextWindowTokens: Long?,
            reservedOutputTokens: Long,
            approximate: Boolean,
            contextWindowSource: ContextWindowSource,
            uncountedMultimodalParts: Int,
        ): ContextUsageEstimate {
            val safeWindow = contextWindowTokens?.takeIf { it > 0L }
            val safeReserve = reservedOutputTokens.coerceAtLeast(0L)
            val usableWindow = safeWindow?.minus(safeReserve)?.coerceAtLeast(0L)
            val remaining = usableWindow?.minus(estimatedInputTokens)
            val ratio = usableWindow
                ?.takeIf { it > 0L }
                ?.let { estimatedInputTokens.toDouble() / it.toDouble() }
                ?.toFloat()
            return ContextUsageEstimate(
                estimatedInputTokens = estimatedInputTokens.coerceAtLeast(0L),
                actualPromptTokens = actualPromptTokens?.takeIf { it >= 0L },
                contextWindowTokens = safeWindow,
                reservedOutputTokens = safeReserve,
                remainingTokens = remaining,
                usageRatio = ratio,
                level = ContextUsageLevel.fromRatio(ratio),
                approximate = approximate,
                contextWindowSource = if (safeWindow == null) ContextWindowSource.Unknown else contextWindowSource,
                uncountedMultimodalParts = uncountedMultimodalParts.coerceAtLeast(0),
            )
        }
    }
}

enum class ContextUsageLevel {
    Normal,
    Notice,
    Warning,
    Critical,
    Unknown;

    companion object {
        fun fromRatio(ratio: Float?): ContextUsageLevel = when {
            ratio == null || !ratio.isFinite() -> Unknown
            ratio < 0.60f -> Normal
            ratio < 0.80f -> Notice
            ratio < 0.95f -> Warning
            else -> Critical
        }
    }
}

enum class ContextWindowSource {
    UserOverride,
    ProviderMetadata,
    BuiltInRegistry,
    Unknown,
}

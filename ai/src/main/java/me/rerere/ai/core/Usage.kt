package me.rerere.ai.core

import kotlinx.serialization.Serializable

@Serializable
data class TokenUsage(
    val promptTokens: Int = 0,
    val completionTokens: Int = 0,
    val cachedTokens: Int = 0,
    val totalTokens: Int = 0,
    // Provider-reported generation cost in USD (OpenRouter `usage.cost`). Null when the
    // provider doesn't report it. Nullable + defaulted so older persisted messages decode fine.
    val cost: Double? = null,
)

/**
 * Merges partial usage reports of ONE request (e.g. Claude reports input tokens on
 * message_start and output tokens on message_delta): a field the new report leaves at 0
 * keeps the earlier value. Do not use this across separate requests (tool steps); a 0 there
 * is a real value, not a missing one.
 */
fun TokenUsage?.merge(other: TokenUsage): TokenUsage {
    val promptTokens = if (other.promptTokens > 0) {
        other.promptTokens
    } else {
        this?.promptTokens ?: 0
    }
    val completionTokens = if (other.completionTokens > 0) {
        other.completionTokens
    } else {
        this?.completionTokens ?: 0
    }
    val totalTokens = promptTokens + completionTokens
    val cachedTokens = if (other.cachedTokens > 0) {
        other.cachedTokens
    } else {
        this?.cachedTokens ?: 0
    }
    val cost = other.cost ?: this?.cost
    return TokenUsage(
        promptTokens = promptTokens,
        completionTokens = completionTokens,
        totalTokens = totalTokens,
        cachedTokens = cachedTokens,
        cost = cost,
    )
}

/** Sum of two provider-reported costs; null only when neither side reported one. */
fun sumCost(a: Double?, b: Double?): Double? =
    if (a == null && b == null) null else (a ?: 0.0) + (b ?: 0.0)

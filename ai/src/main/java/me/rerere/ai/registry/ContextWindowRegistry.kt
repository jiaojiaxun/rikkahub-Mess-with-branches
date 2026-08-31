package me.rerere.ai.registry

/**
 * Conservative context-window fallback used only when provider metadata is absent.
 * Matching is exact after normalization to avoid assigning a fabricated limit to similarly
 * named third-party models.
 */
object ContextWindowRegistry {
    private const val ONE_MILLION = 1_000_000L

    private val windows = mapOf(
        "deepseek-v4-flash" to ONE_MILLION,
        "deepseek-v4-pro" to ONE_MILLION,
        "deepseek-v4-flash-vision-exp" to ONE_MILLION,
        "claude-sonnet-5" to ONE_MILLION,
        "claude-opus-5" to ONE_MILLION,
    )

    private val knownProviderPrefixes = listOf(
        "models/",
        "openai/",
        "anthropic/",
        "google/",
        "deepseek/",
        "openrouter/",
    )

    fun normalizeModelId(raw: String): String = raw
        .trim()
        .lowercase()
        .replace('\\', '/')
        .replace(Regex("/+"), "/")

    fun resolve(modelId: String): Long? {
        var candidate = normalizeModelId(modelId)
        repeat(knownProviderPrefixes.size) {
            windows[candidate]?.let { return it }
            val stripped = knownProviderPrefixes.firstNotNullOfOrNull { prefix ->
                candidate.removePrefix(prefix).takeIf { it != candidate }
            } ?: return null
            candidate = stripped
        }
        return windows[candidate]
    }
}

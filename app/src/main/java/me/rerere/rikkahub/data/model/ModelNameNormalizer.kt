package me.rerere.rikkahub.data.model

import java.util.Locale

/**
 * Normalizes provider model identifiers for deterministic capability lookup.
 * Provider prefixes, casing, separators and OpenRouter route suffixes must not change the
 * context-family match.
 */
object ModelNameNormalizer {
    private val nonAlphaNumeric = Regex("[^\\p{L}\\p{N}]+")
    // rhStripCjk: 模型名中的 CJK/全角字符不参与上下文族匹配
    private val cjkChars = Regex("[\\u3000-\\u303f\\u3400-\\u4dbf\\u4e00-\\u9fff\\uf900-\\ufaff\\uff00-\\uffef]+")

    fun key(value: String): String {
        val raw = value.trim().lowercase(Locale.ROOT)
        // OpenRouter-style identifiers may contain an owner prefix. The model segment is the
        // part that carries the family/version name; retain the full value for other models.
        val segment = raw.substringAfterLast('/').substringBefore(':')
        val compact = segment.replace(cjkChars, "").replace(nonAlphaNumeric, "")
        return when {
            // DeepSeek V4 Flash/Pro and the bare V4 family intentionally share one 1M
            // allowlist entry. This also preserves existing family aggregation semantics.
            compact.contains("deepseek") && compact.contains("v4") -> "deepseekv4"
            else -> compact
        }
    }
}


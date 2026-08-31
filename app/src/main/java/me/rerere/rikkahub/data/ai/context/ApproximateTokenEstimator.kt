package me.rerere.rikkahub.data.ai.context

import kotlin.math.ceil

object ApproximateTokenEstimator {
    private const val MESSAGE_OVERHEAD_TOKENS = 4L

    fun estimateText(text: String): Long {
        if (text.isEmpty()) return 0L

        var cjk = 0L
        var asciiLettersOrDigits = 0L
        var whitespace = 0L
        var punctuationOrOther = 0L

        text.forEach { char ->
            when {
                char.isCjk() -> cjk++
                char.isWhitespace() -> whitespace++
                char.code < 128 && char.isLetterOrDigit() -> asciiLettersOrDigits++
                else -> punctuationOrOther++
            }
        }

        return ceil(
            cjk * 1.2 +
                asciiLettersOrDigits / 4.0 +
                whitespace / 12.0 +
                punctuationOrOther / 2.0
        ).toLong()
    }

    fun withMessageOverhead(contentTokens: Long): Long =
        MESSAGE_OVERHEAD_TOKENS + contentTokens.coerceAtLeast(0L)

    private fun Char.isCjk(): Boolean =
        code in 0x3400..0x4DBF ||
            code in 0x4E00..0x9FFF ||
            code in 0xF900..0xFAFF ||
            code in 0x3040..0x30FF ||
            code in 0xAC00..0xD7AF
}

package me.rerere.rikkahub.data.ai

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.Tool
import me.rerere.ai.provider.Model
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart

data class ContextBudgetPlan(
    val estimatedInputTokens: Int,
    val triggerTokens: Int,
    val shouldCompact: Boolean,
)

/**
 * Conservative provider-independent context estimator.
 *
 * The most recent real usage is preferred because it includes provider-specific system and
 * tool-schema overhead. Messages added after that response are estimated locally. Providers
 * that do not report usage fall back to estimating the complete message list.
 */
object ContextBudgetPlanner {
        private const val CHARS_PER_TOKEN = 3
    private const val MESSAGE_OVERHEAD_TOKENS = 8
    private const val MEDIA_PART_TOKENS = 1_024
    /** Per-tool JSON envelope around the function declaration. */
    private const val TOOL_SCHEMA_ENVELOPE_TOKENS = 16L

    fun plan(
        messages: List<UIMessage>,
        contextLength: Int,
        thresholdPercent: Int,
                thresholdTokensK: Int? = null,
        reservedTokens: Int = 0,
        requestOverheadTokens: Long = 0,
    ): ContextBudgetPlan {
        require(contextLength > 0) { "contextLength must be positive" }
        val normalizedThreshold = thresholdPercent.coerceIn(5, 95)
        val safeInputBudget = (contextLength.toLong() - reservedTokens.coerceAtLeast(0).toLong())
            .coerceAtLeast(1L)
        val configuredTriggerTokens = thresholdTokensK?.let { tokensK ->
            (tokensK.toLong().coerceAtLeast(1L) * 1_000L)
                .coerceAtMost(Int.MAX_VALUE.toLong())
                .toInt()
        } ?: (contextLength.toLong() * normalizedThreshold / 100L)
            .coerceAtLeast(1L)
            .coerceAtMost(Int.MAX_VALUE.toLong())
            .toInt()
        val triggerTokens = minOf(configuredTriggerTokens.toLong(), safeInputBudget)
            .coerceAtMost(Int.MAX_VALUE.toLong())
            .toInt()
                val estimatedInputTokens = estimateInputTokens(messages, requestOverheadTokens)
        return ContextBudgetPlan(
            estimatedInputTokens = estimatedInputTokens,
            triggerTokens = triggerTokens,
            shouldCompact = estimatedInputTokens >= triggerTokens,
        )
    }

        fun estimateInputTokens(
        messages: List<UIMessage>,
        requestOverheadTokens: Long = 0,
    ): Int {
        val usageIndex = messages.indexOfLast { message ->
            val usage = message.usage
            usage != null && (usage.totalTokens > 0 || usage.promptTokens + usage.completionTokens > 0)
        }
        val estimate = if (usageIndex >= 0) {
            val usage = messages[usageIndex].usage!!
            val reportedTotal = usage.totalTokens.takeIf { it > 0 }
                ?: (usage.promptTokens + usage.completionTokens)
            reportedTotal.toLong() +
                estimatePostUsageToolOutputTokens(messages[usageIndex]) +
                messages.drop(usageIndex + 1).sumOf(::estimateMessageTokens)
                } else {
            // No provider usage exists to anchor the estimate. Include the request material
            // that lives outside the message list, or compaction will trigger too late.
            messages.sumOf(::estimateMessageTokens) + requestOverheadTokens.coerceAtLeast(0)
        }
        return estimate.coerceAtMost(Int.MAX_VALUE.toLong()).toInt()
    }

    /**
     * Estimates the context represented by the supplied messages without using provider usage.
     * This is required after compaction because reported usage belongs to the pre-compaction
     * request and cannot describe the synthetic summary that replaced it.
     */
        fun estimateContextTokens(
        messages: List<UIMessage>,
        requestOverheadTokens: Long = 0,
    ): Int = (messages.sumOf(::estimateMessageTokens) + requestOverheadTokens.coerceAtLeast(0))
        .coerceAtMost(Int.MAX_VALUE.toLong())
        .toInt()

        /**
     * Estimates tokens sent outside the message list: system prompt, memory, tool prompts,
     * and each tool's JSON declaration. Provider usage already includes this for the request
     * it describes; callers must pass it for local fallback and post-compaction estimates.
     */
    fun estimateRequestOverheadTokens(
        systemPromptText: String,
        tools: List<Tool>,
        memoryText: String = "",
        modelForToolPrompts: Model? = null,
    ): Long {
        val promptTokens = estimateTextTokens(systemPromptText) + estimateTextTokens(memoryText)
        val toolTokens = tools.sumOf { tool ->
            val toolPromptTokens = modelForToolPrompts?.let { model ->
                runCatching { tool.systemPrompt(model, emptyList()) }
                    .getOrDefault("")
                    .let(::estimateTextTokens)
            } ?: 0L
            estimateTextTokens(tool.name) +
                estimateTextTokens(tool.description) +
                estimateToolSchemaTokens(tool) +
                toolPromptTokens +
                TOOL_SCHEMA_ENVELOPE_TOKENS
        }
        return promptTokens + toolTokens
    }

    private fun estimateToolSchemaTokens(tool: Tool): Long {
        val schema = runCatching { tool.parameters() }.getOrNull() as? InputSchema.Obj
            ?: return 0L
        var tokens = 0L
        schema.properties.forEach { (name, element) ->
            tokens += estimateTextTokens(name) + estimateJsonElementTokens(element)
        }
        schema.required?.let { tokens += estimateTextTokens(it.joinToString(",")) }
        return tokens
    }

    private fun estimateJsonElementTokens(element: JsonElement): Long = when (element) {
        is JsonObject -> element.keys.sumOf { estimateTextTokens(it) } +
            element.values.sumOf { estimateJsonElementTokens(it) }
        is JsonArray -> element.sumOf { estimateJsonElementTokens(it) }
        is JsonPrimitive -> estimateTextTokens(element.content)
    }

    // rhCtxOn2Fix238: 不可变 UIMessage 实例级 O(1) 估算缓存, 避免长对话每轮重复逐字符扫描历史消息
    private data class MessageCacheKey(val id: Any, val identity: Int)
    private const val MAX_MESSAGE_CACHE_SIZE = 1024
    private val messageTokenCache: MutableMap<MessageCacheKey, Long> =
        java.util.Collections.synchronizedMap(
            object : java.util.LinkedHashMap<MessageCacheKey, Long>(256, 0.75f, true) {
                override fun removeEldestEntry(eldest: MutableMap.MutableEntry<MessageCacheKey, Long>?): Boolean =
                    size > MAX_MESSAGE_CACHE_SIZE
            }
        )

    fun estimateMessageTokens(message: UIMessage): Long {
        val key = MessageCacheKey(message.id, System.identityHashCode(message))
        messageTokenCache[key]?.let { return it }
        val contentTokens = message.parts.sumOf(::estimatePartTokens)
        val total = MESSAGE_OVERHEAD_TOKENS + contentTokens
        messageTokenCache[key] = total
        return total
    }

    /**
     * Estimates only the tool results appended after provider usage was emitted. Tool-call
     * names and arguments already belong to the reported completion.
     *
     * Only the trailing run of tool parts counts. A multi-step reply (tool -> tool -> answer)
     * keeps every step in one message, and its usage belongs to the LAST request, whose prompt
     * already contained every earlier tool result. Counting those again inflated the estimate
     * and triggered compaction too early.
     */
    @Suppress("DEPRECATION")
    private fun estimatePostUsageToolOutputTokens(message: UIMessage): Long {
        val lastNonTool = message.parts.indexOfLast { part ->
            part !is UIMessagePart.Tool && part !is UIMessagePart.ToolResult
        }
        return message.parts.drop(lastNonTool + 1).sumOf { part ->
            when (part) {
                is UIMessagePart.Tool -> part.output.sumOf(::estimatePartTokens)
                is UIMessagePart.ToolResult -> estimateTextTokens(part.content.toString())
                else -> 0L
            }
        }
    }

    /** Selects a recent tail whose estimated size fits [targetTokens]. */
    fun chooseTailStartIndex(
        messages: List<UIMessage>,
        targetTokens: Int,
        minimumRecentMessages: Int = 4,
    ): Int {
        if (messages.size <= 1) return 0

        val minimumStart = (messages.size - minimumRecentMessages.coerceAtLeast(1))
            .coerceAtLeast(0)
        var start = messages.lastIndex
        var used = 0L
        while (start >= 0) {
            val next = estimateMessageTokens(messages[start])
            if (start < minimumStart && used + next > targetTokens) break
            used += next
            start--
        }
        return (start + 1).coerceIn(1, messages.lastIndex)
    }

    @Suppress("DEPRECATION")
    private fun estimatePartTokens(part: UIMessagePart): Long = when (part) {
        is UIMessagePart.Text -> estimateTextTokens(part.text)
        is UIMessagePart.Reasoning -> estimateTextTokens(part.reasoning)
        is UIMessagePart.Tool -> estimateTextTokens(part.toolName) +
            estimateTextTokens(part.input) + part.output.sumOf(::estimatePartTokens)
        is UIMessagePart.ServerTool -> estimateTextTokens(part.toolName) +
            estimateTextTokens(part.input.toString()) + estimateTextTokens(part.output.toString())
        is UIMessagePart.ToolCall -> estimateTextTokens(part.toolName) + estimateTextTokens(part.arguments)
        is UIMessagePart.ToolResult -> estimateTextTokens(part.toolName) +
            estimateTextTokens(part.arguments.toString()) + estimateTextTokens(part.content.toString())
        is UIMessagePart.Document -> MEDIA_PART_TOKENS + estimateTextTokens(part.fileName)
        is UIMessagePart.Image,
        is UIMessagePart.Video,
        is UIMessagePart.Audio,
        UIMessagePart.Search,
            -> MEDIA_PART_TOKENS.toLong()
    }

    private fun estimateTextTokens(text: String): Long {
        var asciiChars = 0L
        var nonAsciiChars = 0L
        text.forEach { char ->
            if (char.code <= 0x7F) asciiChars++ else nonAsciiChars++
        }
        return nonAsciiChars + (asciiChars + CHARS_PER_TOKEN - 1L) / CHARS_PER_TOKEN
    }
}

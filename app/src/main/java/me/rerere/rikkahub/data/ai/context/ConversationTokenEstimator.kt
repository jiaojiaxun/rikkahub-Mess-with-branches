package me.rerere.rikkahub.data.ai.context

import me.rerere.ai.core.MessageRole
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart

data class MessageTokenEstimate(
    val tokens: Long,
    val uncountedMultimodalParts: Int,
)

object ConversationTokenEstimator {
    fun estimate(messages: List<UIMessage>): MessageTokenEstimate {
        var total = 0L
        var multimodal = 0
        messages.forEach { message ->
            val estimate = estimateMessage(message)
            total += estimate.tokens
            multimodal += estimate.uncountedMultimodalParts
        }
        return MessageTokenEstimate(total, multimodal)
    }

    @Suppress("DEPRECATION")
    private fun estimateMessage(message: UIMessage): MessageTokenEstimate {
        var tokens = ApproximateTokenEstimator.estimateText(message.role.name.lowercase())
        var multimodal = 0
        message.parts.forEach { part ->
            when (part) {
                is UIMessagePart.Text -> tokens += ApproximateTokenEstimator.estimateText(part.text)
                is UIMessagePart.Reasoning -> tokens += ApproximateTokenEstimator.estimateText(part.reasoning)
                is UIMessagePart.Tool -> {
                    tokens += ApproximateTokenEstimator.estimateText(part.toolName)
                    tokens += ApproximateTokenEstimator.estimateText(part.input)
                    val output = estimateParts(part.output)
                    tokens += output.tokens
                    multimodal += output.uncountedMultimodalParts
                }
                is UIMessagePart.ServerTool -> {
                    tokens += ApproximateTokenEstimator.estimateText(part.toolName)
                    tokens += ApproximateTokenEstimator.estimateText(part.input?.toString().orEmpty())
                    tokens += ApproximateTokenEstimator.estimateText(part.output?.toString().orEmpty())
                }
                is UIMessagePart.ToolCall -> {
                    tokens += ApproximateTokenEstimator.estimateText(part.toolName)
                    tokens += ApproximateTokenEstimator.estimateText(part.arguments)
                }
                is UIMessagePart.ToolResult -> {
                    tokens += ApproximateTokenEstimator.estimateText(part.toolName)
                    tokens += ApproximateTokenEstimator.estimateText(part.arguments.toString())
                    tokens += ApproximateTokenEstimator.estimateText(part.content.toString())
                }
                is UIMessagePart.Document -> {
                    tokens += ApproximateTokenEstimator.estimateText(part.fileName)
                    multimodal++
                }
                is UIMessagePart.Image,
                is UIMessagePart.Video,
                is UIMessagePart.Audio,
                UIMessagePart.Search,
                    -> multimodal++
            }
        }
        return MessageTokenEstimate(
            tokens = ApproximateTokenEstimator.withMessageOverhead(tokens),
            uncountedMultimodalParts = multimodal,
        )
    }

    private fun estimateParts(parts: List<UIMessagePart>): MessageTokenEstimate {
        val synthetic = UIMessage(role = MessageRole.TOOL, parts = parts)
        val estimate = estimateMessage(synthetic)
        return estimate.copy(tokens = (estimate.tokens - 4L).coerceAtLeast(0L))
    }
}

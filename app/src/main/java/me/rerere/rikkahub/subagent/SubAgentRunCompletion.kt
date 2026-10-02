package me.rerere.rikkahub.subagent

import me.rerere.ai.core.MessageRole
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart

/**
 * 分发器暴露给父级的唯一结果：子运行的最后一条 assistant 消息文本。
 * （移植自 AAAelina selectSubAgentFinalText，语义不变。）
 */
internal fun selectSubAgentFinalText(messages: List<UIMessage>): String {
    val finalAssistantMessage = messages.lastOrNull { it.role == MessageRole.ASSISTANT }
        ?: return ""
    return finalAssistantMessage.parts
        .filterIsInstance<UIMessagePart.Text>()
        .joinToString("\n") { it.text }
        .trim()
}

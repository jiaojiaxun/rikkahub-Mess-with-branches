package me.rerere.rikkahub.data.export

import kotlinx.serialization.Serializable
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart
import me.rerere.rikkahub.data.model.Conversation
import me.rerere.rikkahub.data.model.MessageNode
import me.rerere.rikkahub.utils.JsonInstant
import me.rerere.rikkahub.utils.JsonInstantPretty
import kotlin.uuid.Uuid

private const val SHARED_CONVERSATION_FORMAT = "rikkahub-conversation"
private const val SHARED_CONVERSATION_VERSION = 1

@Serializable
data class SharedConversationPayload(
    val format: String = SHARED_CONVERSATION_FORMAT,
    val version: Int = SHARED_CONVERSATION_VERSION,
    val conversation: Conversation,
)

object SharedConversationCodec {
    const val MAX_SHARED_CONVERSATION_BYTES = 32 * 1024 * 1024

    private val markdownTitleRegex = Regex("(?m)^# (.+?)\\s*$")
    private val markdownMessageRegex = Regex("(?m)^\\*\\*(User|Assistant)\\*\\*:\\s*$")

    /** Kept only to read the first JSON prototype; normal sharing uses the existing Markdown exporter. */
    fun encode(conversation: Conversation): String {
        require(!conversation.hasLocalFileAttachments()) {
            "本地附件不会随分享文件复制，请先移除附件后再分享"
        }
        val encoded = JsonInstantPretty.encodeToString(
            SharedConversationPayload(conversation = conversation)
        )
        require(encoded.toByteArray(Charsets.UTF_8).size <= MAX_SHARED_CONVERSATION_BYTES) {
            "分享聊天文件过大"
        }
        return encoded
    }

    fun decode(text: String): Conversation {
        require(text.toByteArray(Charsets.UTF_8).size <= MAX_SHARED_CONVERSATION_BYTES) {
            "分享聊天文件过大"
        }
        val trimmed = text.trimStart()
        return if (trimmed.startsWith("{")) decodeJson(trimmed) else decodeMarkdown(text)
    }

    private fun decodeJson(text: String): Conversation {
        val payload = JsonInstant.decodeFromString<SharedConversationPayload>(text)
        require(payload.format == SHARED_CONVERSATION_FORMAT) { "不是 RikkaHub 单聊分享文件" }
        require(payload.version in 1..SHARED_CONVERSATION_VERSION) {
            "不支持的单聊分享版本: ${payload.version}"
        }
        require(payload.conversation.messageNodes.isNotEmpty()) { "分享文件中没有聊天消息" }
        return payload.conversation
    }

    /** Parse the Markdown produced by ui.pages.chat.Export.kt. */
    private fun decodeMarkdown(text: String): Conversation {
        val title = markdownTitleRegex.find(text)?.groupValues?.get(1)?.trim().orEmpty()
        val headers = markdownMessageRegex.findAll(text).toList()
        require(headers.isNotEmpty()) { "不是 RikkaHub 聊天 Markdown 分享文件" }

        val nodes = headers.mapIndexedNotNull { index, header ->
            val bodyStart = header.range.last + 1
            val bodyEnd = headers.getOrNull(index + 1)?.range?.first ?: text.length
            val body = text.substring(bodyStart, bodyEnd)
                .trim()
                .removeSuffix("---")
                .trim()
            if (body.isBlank()) null else {
                val message = if (header.groupValues[1] == "User") {
                    UIMessage.user(body)
                } else {
                    UIMessage.assistant(body)
                }
                MessageNode(id = Uuid.random(), messages = listOf(message), selectIndex = 0)
            }
        }
        require(nodes.isNotEmpty()) { "分享文件中没有聊天消息" }
        return Conversation(
            id = Uuid.random(),
            assistantId = Uuid.random(),
            title = title.ifBlank { "Imported chat" },
            messageNodes = nodes,
        )
    }
}

private fun Conversation.hasLocalFileAttachments(): Boolean = messageNodes
    .asSequence()
    .flatMap { node -> node.messages.asSequence() }
    .flatMap { message -> message.parts.asSequence() }
    .any { it.hasLocalFileAttachment() }

private fun UIMessagePart.hasLocalFileAttachment(): Boolean = when (this) {
    is UIMessagePart.Image -> url.startsWith("file://")
    is UIMessagePart.Video -> url.startsWith("file://")
    is UIMessagePart.Audio -> url.startsWith("file://")
    is UIMessagePart.Document -> url.startsWith("file://")
    is UIMessagePart.Tool -> output.any { it.hasLocalFileAttachment() }
    else -> false
}

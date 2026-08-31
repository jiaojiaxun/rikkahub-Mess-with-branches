package me.rerere.rikkahub.data.export

import org.junit.Assert.assertEquals
import org.junit.Test
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart
import me.rerere.rikkahub.data.model.Conversation
import me.rerere.rikkahub.data.model.MessageNode
import kotlin.uuid.Uuid

class SharedConversationCodecTest {
    @Test(expected = IllegalArgumentException::class)
    fun encodeRejectsLocalFileAttachments() {
        SharedConversationCodec.encode(
            Conversation(
                assistantId = Uuid.random(),
                messageNodes = listOf(
                    MessageNode.of(
                        UIMessage(
                            role = me.rerere.ai.core.MessageRole.USER,
                            parts = listOf(UIMessagePart.Image("file:///private/chat-image.png")),
                        )
                    )
                ),
            )
        )
    }

    @Test
    fun markdownExportIsImportedAsConversation() {
        val markdown = """# 示例聊天

*Exported on 2026年8月28日 12:15:51*

**User**:

你好

---
**Assistant**:

你好，我可以帮忙。

---
"""

        val restored = SharedConversationCodec.decode(markdown)

        assertEquals("示例聊天", restored.title)
        assertEquals(2, restored.messageNodes.size)
        assertEquals(listOf("你好", "你好，我可以帮忙。"), restored.currentMessages.map { it.toText() })
    }

    @Test
    fun roundTripPreservesConversationMessagesAndForks() {
        val conversation = Conversation(
            id = Uuid.random(),
            assistantId = Uuid.random(),
            title = "分享测试",
            messageNodes = listOf(
                MessageNode(
                    id = Uuid.random(),
                    messages = listOf(
                        UIMessage.user("问题一"),
                        UIMessage.assistant("回答一"),
                    ),
                    selectIndex = 1,
                ),
                MessageNode.of(UIMessage.assistant("后续回答")),
            ),
        )

        val restored = SharedConversationCodec.decode(SharedConversationCodec.encode(conversation))

        assertEquals(conversation.id, restored.id)
        assertEquals(conversation.title, restored.title)
        assertEquals(conversation.messageNodes.size, restored.messageNodes.size)
        assertEquals(conversation.messageNodes.map { it.selectIndex }, restored.messageNodes.map { it.selectIndex })
        assertEquals(
            conversation.messageNodes.flatMap { node -> node.messages }.map { it.toText() },
            restored.messageNodes.flatMap { node -> node.messages }.map { it.toText() },
        )
    }
}

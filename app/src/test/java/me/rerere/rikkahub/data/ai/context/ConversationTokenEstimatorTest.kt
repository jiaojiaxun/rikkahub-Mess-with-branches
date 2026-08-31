package me.rerere.rikkahub.data.ai.context

import me.rerere.ai.core.MessageRole
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ConversationTokenEstimatorTest {
    @Test
    fun `selected branch excludes unselected alternatives`() {
        val selected = UIMessage.user("selected branch")
        val unselected = UIMessage.user("x".repeat(10_000))
        assertTrue(
            ConversationTokenEstimator.estimate(listOf(selected)).tokens <
                ConversationTokenEstimator.estimate(listOf(selected, unselected)).tokens,
        )
    }

    @Test
    fun `tool input and output are counted`() {
        val message = UIMessage(
            role = MessageRole.ASSISTANT,
            parts = listOf(
                UIMessagePart.Tool(
                    toolCallId = "1",
                    toolName = "read_file",
                    input = "{\"path\":\"notes.txt\"}",
                    output = listOf(UIMessagePart.Text("important tool result")),
                ),
            ),
        )
        assertTrue(ConversationTokenEstimator.estimate(listOf(message)).tokens > 4)
    }

    @Test
    fun `multimodal content is marked uncounted`() {
        val message = UIMessage(
            role = MessageRole.USER,
            parts = listOf(
                UIMessagePart.Text("caption"),
                UIMessagePart.Image("https://example.com/image"),
                UIMessagePart.Document("file:///tmp/report.pdf", "report.pdf", "application/pdf"),
            ),
        )
        assertEquals(2, ConversationTokenEstimator.estimate(listOf(message)).uncountedMultimodalParts)
    }
}

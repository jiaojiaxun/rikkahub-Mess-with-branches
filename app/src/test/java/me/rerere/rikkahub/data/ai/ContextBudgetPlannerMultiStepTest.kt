package me.rerere.rikkahub.data.ai

import me.rerere.ai.core.MessageRole
import me.rerere.ai.core.TokenUsage
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart
import org.junit.Assert.assertEquals
import org.junit.Test

class ContextBudgetPlannerMultiStepTest {
    @Test
    fun `earlier steps' tool output is not counted on top of the final step's usage`() {
        // tool step -> answer step: the answer request's prompt already contained the tool
        // result, so the reported usage covers it.
        val messages = listOf(
            UIMessage(
                role = MessageRole.ASSISTANT,
                parts = listOf(
                    UIMessagePart.Tool(
                        toolCallId = "call-1",
                        toolName = "read_file",
                        input = "{\"path\":\"notes.txt\"}",
                        output = listOf(UIMessagePart.Text("x".repeat(3_000))),
                    ),
                    UIMessagePart.Text("done"),
                ),
                usage = TokenUsage(promptTokens = 5_000, completionTokens = 1_000, totalTokens = 6_000),
            ),
        )

        assertEquals(6_000, ContextBudgetPlanner.estimateInputTokens(messages))
    }
}

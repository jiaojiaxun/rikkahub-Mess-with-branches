package me.rerere.rikkahub.data.ai

import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.MessageRole
import me.rerere.ai.core.TokenUsage
import me.rerere.ai.core.Tool
import me.rerere.ai.provider.Model
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ContextBudgetPlannerOverheadTest {
    @Test
    fun `fallback estimate adds overhead while usage estimate does not double count it`() {
        val messages = listOf(UIMessage.user("x".repeat(300)))
        assertEquals(608, ContextBudgetPlanner.estimateInputTokens(messages, 500))

        val withUsage = listOf(
            UIMessage(
                role = MessageRole.ASSISTANT,
                parts = listOf(UIMessagePart.Text("done")),
                usage = TokenUsage(promptTokens = 5_000, completionTokens = 1_000, totalTokens = 6_000),
            ),
        )
        assertEquals(6_000, ContextBudgetPlanner.estimateInputTokens(withUsage, 500))
    }

    @Test
    fun `request overhead counts prompt and tool schema fields`() {
        val tool = Tool(
            name = "get_weather",
            description = "Get current weather",
            parameters = {
                InputSchema.Obj(
                    properties = buildJsonObject {
                        put("city", buildJsonObject { put("type", "string") })
                    },
                    required = listOf("city"),
                )
            },
            execute = { emptyList<UIMessagePart>() },
        )

        assertEquals(41L, ContextBudgetPlanner.estimateRequestOverheadTokens(
            "You are helpful.",
            listOf(tool),
        ))
    }

    @Test
    fun `tool system prompt is measured and a throwing prompt cannot break accounting`() {
        val tool = Tool(
            name = "t",
            description = "",
            systemPrompt = { _, _ -> "Guidance " + "y".repeat(300) },
            execute = { emptyList<UIMessagePart>() },
        )
        assertEquals(120L, ContextBudgetPlanner.estimateRequestOverheadTokens(
            "",
            listOf(tool),
            modelForToolPrompts = Model(),
        ))

        val throwing = Tool(
            name = "t",
            description = "",
            systemPrompt = { _, messages -> error("needs ${messages.size}") },
            execute = { emptyList<UIMessagePart>() },
        )
        assertEquals(17L, ContextBudgetPlanner.estimateRequestOverheadTokens(
            "",
            listOf(throwing),
            modelForToolPrompts = Model(),
        ))
    }

    @Test
    fun `plan and post compaction estimate include overhead`() {
        val messages = listOf(UIMessage.user("x".repeat(300)))
        val noOverhead = ContextBudgetPlanner.plan(messages, 1_000, 50)
        assertFalse(noOverhead.shouldCompact)

        val withOverhead = ContextBudgetPlanner.plan(
            messages = messages,
            contextLength = 1_000,
            thresholdPercent = 50,
            requestOverheadTokens = 500,
        )
        assertEquals(500, withOverhead.triggerTokens)
        assertTrue(withOverhead.shouldCompact)
        assertEquals(608, ContextBudgetPlanner.estimateContextTokens(messages, 500))
    }

    @Test
    fun `memory text contributes to request overhead`() {
        assertEquals(
            300L,
            ContextBudgetPlanner.estimateRequestOverheadTokens(
                systemPromptText = "",
                tools = emptyList(),
                memoryText = "文".repeat(300),
            ),
        )
    }
}

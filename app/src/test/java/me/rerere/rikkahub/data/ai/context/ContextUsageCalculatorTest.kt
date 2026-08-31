package me.rerere.rikkahub.data.ai.context

import me.rerere.ai.core.MessageRole
import me.rerere.ai.core.TokenUsage
import me.rerere.ai.provider.Model
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ContextUsageCalculatorTest {
    @Test
    fun `provider prompt usage is preferred over local history estimate`() {
        val messages = listOf(
            UIMessage(
                role = MessageRole.ASSISTANT,
                parts = listOf(UIMessagePart.Text("response")),
                usage = TokenUsage(promptTokens = 10_000, completionTokens = 500, totalTokens = 10_500),
            ),
        )
        val estimate = ContextUsageCalculator.calculate(messages, Model(modelId = "unknown"))
        assertEquals(10_000L, estimate.estimatedInputTokens)
        assertEquals(10_000L, estimate.actualPromptTokens)
        assertFalse(estimate.approximate)
    }

    @Test
    fun `trailing messages are added after actual prompt usage`() {
        val base = UIMessage(
            role = MessageRole.ASSISTANT,
            parts = emptyList(),
            usage = TokenUsage(promptTokens = 10_000),
        )
        val estimate = ContextUsageCalculator.calculate(
            listOf(base, UIMessage.user("x".repeat(400))),
            Model(modelId = "unknown"),
        )
        assertTrue(estimate.estimatedInputTokens > 10_000L)
        assertTrue(estimate.approximate)
    }

    @Test
    fun `window precedence is override provider then registry`() {
        val model = Model(modelId = "deepseek-v4-flash", contextLength = 128_000)
        assertEquals(
            ContextWindowSource.UserOverride,
            ContextUsageCalculator.calculate(emptyList(), model, 64_000).contextWindowSource,
        )
        assertEquals(
            ContextWindowSource.ProviderMetadata,
            ContextUsageCalculator.calculate(emptyList(), model).contextWindowSource,
        )
        assertEquals(
            ContextWindowSource.BuiltInRegistry,
            ContextUsageCalculator.calculate(emptyList(), model.copy(contextLength = null)).contextWindowSource,
        )
    }

    @Test
    fun `unknown model never receives a fake window`() {
        val estimate = ContextUsageCalculator.calculate(emptyList(), Model(modelId = "custom-model"))
        assertNull(estimate.contextWindowTokens)
        assertNull(estimate.usageRatio)
    }
}

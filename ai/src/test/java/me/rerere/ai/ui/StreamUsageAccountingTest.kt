package me.rerere.ai.ui

import me.rerere.ai.core.TokenUsage
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class StreamUsageAccountingTest {
    private fun step(
        messages: List<UIMessage>,
        vararg usages: TokenUsage,
    ): List<UIMessage> {
        val handler = StreamChunkHandler()
        var out = messages
        usages.forEach { out = handler.handle(out, StreamChunk.Usage(it)) }
        return handler.handle(out, StreamChunk.Finish(null, null, null))
    }

    @Test
    fun `next step does not inherit the previous step's cache hits and cost is summed`() {
        var messages = listOf(UIMessage.user("hi"))
        messages = step(
            messages,
            TokenUsage(promptTokens = 1_000, completionTokens = 50, cachedTokens = 800, cost = 0.01),
        )
        // Claude-style partial reports: input first, output (with cost) later.
        messages = step(
            messages,
            TokenUsage(promptTokens = 1_500),
            TokenUsage(completionTokens = 80, cost = 0.02),
        )

        val usage = messages.last().usage!!
        assertEquals(1_500, usage.promptTokens)
        assertEquals(80, usage.completionTokens)
        assertEquals(1_580, usage.totalTokens)
        assertEquals(0, usage.cachedTokens)
        assertEquals(0.03, usage.cost!!, 1e-9)
    }

    @Test
    fun `cost stays null when no step reports one`() {
        var messages = listOf(UIMessage.user("hi"))
        messages = step(messages, TokenUsage(promptTokens = 10, completionTokens = 5))
        messages = step(messages, TokenUsage(promptTokens = 20, completionTokens = 6))

        assertNull(messages.last().usage!!.cost)
        assertEquals(20, messages.last().usage!!.promptTokens)
    }
}

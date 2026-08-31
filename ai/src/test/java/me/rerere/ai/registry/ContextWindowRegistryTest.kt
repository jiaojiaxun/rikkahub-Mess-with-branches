package me.rerere.ai.registry

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ContextWindowRegistryTest {
    @Test
    fun `normalizes case whitespace and slash`() {
        assertEquals(
            "models/deepseek-v4-flash",
            ContextWindowRegistry.normalizeModelId("  Models\\DeepSeek-V4-Flash  "),
        )
    }

    @Test
    fun `matches exact ids and nested provider prefixes`() {
        assertEquals(1_000_000L, ContextWindowRegistry.resolve("deepseek-v4-flash"))
        assertEquals(1_000_000L, ContextWindowRegistry.resolve("deepseek/DeepSeek-V4-Pro"))
        assertEquals(1_000_000L, ContextWindowRegistry.resolve("openrouter/deepseek/deepseek-v4-pro"))
        assertEquals(1_000_000L, ContextWindowRegistry.resolve("models/claude-sonnet-5"))
    }

    @Test
    fun `does not use broad substring matching`() {
        assertNull(ContextWindowRegistry.resolve("my-deepseek-compatible-model"))
        assertNull(ContextWindowRegistry.resolve("deepseek-v3"))
        assertNull(ContextWindowRegistry.resolve("claude-4-sonnet"))
    }
}

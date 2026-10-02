package me.rerere.rikkahub.data.model

import okhttp3.OkHttpClient
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class ModelContextLengthResolverTest {
    private val resolver = ModelContextLengthResolver(OkHttpClient())

    @Test
    fun deepSeekV4AliasesUseOneMillionContext() {
        val aliases = listOf(
            "DeepSeek v4 flash",
            "deepseek-v4-flash:free",
            "deepseek/deepseek-v4-flash",
            "DeepSeek V4 Pro",
            "deepseek-v4-pro:free",
            "deepseek/deepseek-v4",
        )

        aliases.forEach { modelId ->
            assertEquals(1_000_000, resolver.knownContextLengthForTesting(modelId))
        }
    }

    @Test
    fun otherDeepSeekGenerationsUseTheirOwnCeiling() {
        assertEquals(65_536, resolver.knownContextLengthForTesting("deepseek-v3"))
        assertEquals(131_072, resolver.knownContextLengthForTesting("deepseek/deepseek-chat"))
        assertEquals(
            131_072,
            resolver.knownContextLengthForTesting("deepseek-reasoner"),
        )
        // V3.2 must not be shadowed by the shorter V3 rule.
        assertEquals(131_072, resolver.knownContextLengthForTesting("deepseek-v3.2-exp"))
    }

    @Test
    fun unknownModelFallsBackToCatalog() {
        assertNull(resolver.knownContextLengthForTesting("totally-unknown-model-x1"))
        assertNull(resolver.knownContextLengthForTesting(""))
    }

    @Test
    fun commonFamiliesResolve() {
        assertEquals(1_048_576, resolver.knownContextLengthForTesting("gpt-4.1"))
        assertEquals(1_048_576, resolver.knownContextLengthForTesting("gpt-4.1-mini"))
        assertEquals(128_000, resolver.knownContextLengthForTesting("gpt-4o-2024-11-20"))
        assertEquals(200_000, resolver.knownContextLengthForTesting("claude-3.7-sonnet"))
        assertEquals(1_048_576, resolver.knownContextLengthForTesting("gemini-2.5-pro"))
        assertEquals(262_144, resolver.knownContextLengthForTesting("qwen3-235b"))
        assertEquals(10_000_000, resolver.knownContextLengthForTesting("qwen-long"))
        assertEquals(262_144, resolver.knownContextLengthForTesting("moonshotai/kimi-k2"))
        assertEquals(200_000, resolver.knownContextLengthForTesting("glm-4.6"))
        assertEquals(256_000, resolver.knownContextLengthForTesting("grok-4"))
    }

    @Test
    fun specificFamilyRulesWinOverGeneralOnes() {
        // gpt-4o (128K) must not be shadowed by the gpt4 (128K) / gpt5 rules, and
        // gemini-1.5-pro (2M) must not be shadowed by the generic gemini rule.
        assertEquals(2_097_152, resolver.knownContextLengthForTesting("gemini-1.5-pro"))
        assertEquals(1_048_576, resolver.knownContextLengthForTesting("gemini-1.5-flash"))
        assertEquals(400_000, resolver.knownContextLengthForTesting("gpt-5"))
        assertEquals(10_000_000, resolver.knownContextLengthForTesting("llama-4-scout"))
    }
}
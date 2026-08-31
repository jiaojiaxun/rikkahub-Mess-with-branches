package me.rerere.rikkahub.data.model

import okhttp3.OkHttpClient
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Test

class ModelNameNormalizerTest {
    @Test
    fun `deepseek v4 route labels share a family key`() {
        assertEquals(
            ModelNameNormalizer.key("deepseekv4"),
            ModelNameNormalizer.key("DeepSeek v4 flash"),
        )
        assertEquals(
            ModelNameNormalizer.key("deepseek-v4-flash:free"),
            ModelNameNormalizer.key("DEEPSEEK V4"),
        )
    }

    @Test
    fun `known context fallback covers deepseek v4 aliases`() {
        val resolver = ModelContextLengthResolver(OkHttpClient())
        assertEquals(1_000_000, resolver.knownContextLengthForTesting("DeepSeek v4 flash"))
        assertEquals(1_000_000, resolver.knownContextLengthForTesting("deepseek v4"))
        assertEquals(1_000_000, resolver.knownContextLengthForTesting("DEEPSEEK-V4-FLASH:free"))
        assertNotNull(resolver.knownContextLengthForTesting("gpt-4o"))
    }

    @Test
    fun `unrelated models remain distinct`() {
        assertEquals("gpt4o", ModelNameNormalizer.key("GPT-4o"))
        assertEquals("claude35sonnet", ModelNameNormalizer.key("claude-3.5-sonnet"))
    }
}

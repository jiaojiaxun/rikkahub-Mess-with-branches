package me.rerere.rikkahub.data.model

import okhttp3.OkHttpClient
import org.junit.Assert.assertEquals
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
    fun unrelatedModelDoesNotUseDeepSeekAllowlist() {
        assertEquals(null, resolver.knownContextLengthForTesting("deepseek-v3"))
    }
}


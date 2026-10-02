package me.rerere.rikkahub.data.model

import androidx.annotation.VisibleForTesting
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.HttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/**
 * Resolves a model context ceiling without changing the persisted Model schema.
 *
 * Priority: provider-declared metadata (the provider's own model list) always wins, then the
 * built-in family table below, then the public catalog as a last best-effort fallback.
 *
 * The family table is intentionally generous: an under-reported context length makes the app
 * compact far too early, while an over-reported one produces hard provider errors. When a rule
 * is uncertain we prefer the smaller of the plausible values.
 */
class ModelContextLengthResolver(
    private val client: OkHttpClient,
) {
    private val cache = mutableMapOf<String, Int?>()

    suspend fun resolve(modelId: String?, declared: Int?): Int? {
        declared?.takeIf { it > 0 }?.let { return it }
        val raw = modelId?.trim().orEmpty()
        if (raw.isBlank()) return null
        val key = ModelNameNormalizer.key(raw)
        synchronized(cache) {
            if (cache.containsKey(key)) return cache[key]
        }
        // The built-in family table is authoritative for the families it covers. A public
        // catalog can be stale or expose a route-specific value, so it is only consulted for
        // models the table does not know.
        val result = knownContextLength(key) ?: queryPublicCatalog(raw)
        synchronized(cache) { cache[key] = result }
        return result
    }

    private suspend fun queryPublicCatalog(modelId: String): Int? = withContext(Dispatchers.IO) {
        runCatching {
            val urlBuilder = HttpUrl.Builder()
                .scheme("https")
                .host("openrouter.ai")
                .addPathSegment("api")
                .addPathSegment("v1")
                .addPathSegment("models")
            // OpenRouter IDs are commonly author/model. Add each path component separately;
            // encoding the slash as part of one path segment makes the detail endpoint miss.
            modelId.split('/').filter { it.isNotBlank() }.forEach(urlBuilder::addPathSegment)
            val request = Request.Builder()
                .url(urlBuilder.build())
                .header("Accept", "application/json")
                .get()
                .build()
            val call = client.newCall(request)
            call.timeout().timeout(5, TimeUnit.SECONDS)
            call.execute().use { response ->
                if (!response.isSuccessful) return@use null
                val body = response.body?.string().orEmpty()
                if (body.length > MAX_RESPONSE_CHARS) return@use null
                val root = JSONObject(body)
                val data = root.optJSONObject("data") ?: root
                firstPositiveInt(
                    data,
                    "context_length",
                    "max_context_length",
                    "input_token_limit",
                    "max_input_tokens",
                )
            }
        }.getOrNull()
    }

    @VisibleForTesting
    internal fun knownContextLengthForTesting(modelId: String): Int? =
        knownContextLength(ModelNameNormalizer.key(modelId))

    private fun knownContextLength(key: String): Int? {
        if (key.isBlank()) return null
        return CONTEXT_RULES.firstOrNull { rule -> rule.matches(key) }?.contextLength
    }

    private fun firstPositiveInt(json: JSONObject, vararg keys: String): Int? =
        keys.firstNotNullOfOrNull { key -> json.optInt(key, 0).takeIf { it > 0 } }

    /**
     * A rule matches when every one of its [tokens] appears in the normalized model key
     * (lowercased, separators removed, owner prefix and route suffix dropped).
     *
     * Rules are evaluated top to bottom and the first match wins, so a specific family
     * (for example `qwenlong`) must always be listed above the general one it contains
     * (for example `qwen`).
     */
    private class ContextRule(
        private val tokens: List<String>,
        val contextLength: Int,
    ) {
        fun matches(key: String): Boolean = tokens.all { token -> key.contains(token) }
    }

    companion object {
        private const val MAX_RESPONSE_CHARS = 512 * 1024

        private val CONTEXT_RULES: List<ContextRule> = listOf(
            // ---- DeepSeek -------------------------------------------------------
            // ModelNameNormalizer collapses every deepseek+v4 alias to this single key.
            ContextRule(listOf("deepseekv4"), 1_000_000),
            ContextRule(listOf("deepseekv32"), 131_072),
            ContextRule(listOf("deepseekv31"), 131_072),
            ContextRule(listOf("deepseekv3"), 65_536),
            ContextRule(listOf("deepseekr1"), 131_072),
            ContextRule(listOf("deepseekreasoner"), 131_072),
            ContextRule(listOf("deepseekchat"), 131_072),
            ContextRule(listOf("deepseekcoder"), 131_072),
            ContextRule(listOf("deepseek"), 131_072),

            // ---- OpenAI ---------------------------------------------------------
            ContextRule(listOf("gpt41"), 1_048_576),
            ContextRule(listOf("gpt45"), 128_000),
            ContextRule(listOf("gpt4o"), 128_000),
            ContextRule(listOf("gpt4turbo"), 128_000),
            ContextRule(listOf("gpt5"), 400_000),
            ContextRule(listOf("gpt4"), 128_000),
            ContextRule(listOf("gpt3"), 16_385),
            ContextRule(listOf("gptoss"), 131_072),
            ContextRule(listOf("chatgpt"), 128_000),

            // ---- Anthropic ------------------------------------------------------
            ContextRule(listOf("claude"), 200_000),

            // ---- Google ---------------------------------------------------------
            ContextRule(listOf("gemini", "15", "pro"), 2_097_152),
            ContextRule(listOf("gemini", "15", "flash"), 1_048_576),
            ContextRule(listOf("gemini"), 1_048_576),

            // ---- Meta -----------------------------------------------------------
            ContextRule(listOf("llama4", "scout"), 10_000_000),
            ContextRule(listOf("llama4"), 1_000_000),
            ContextRule(listOf("llama3", "3"), 131_072),
            ContextRule(listOf("llama3"), 131_072),

            // ---- Alibaba --------------------------------------------------------
            ContextRule(listOf("qwenlong"), 10_000_000),
            ContextRule(listOf("qwen3"), 262_144),
            ContextRule(listOf("qwen25"), 131_072),
            ContextRule(listOf("qwen2"), 131_072),
            ContextRule(listOf("qwq"), 131_072),
            ContextRule(listOf("qwen"), 131_072),

            // ---- Zhipu ----------------------------------------------------------
            ContextRule(listOf("glm46"), 200_000),
            ContextRule(listOf("glm45"), 128_000),
            ContextRule(listOf("glm4"), 128_000),
            ContextRule(listOf("chatglm"), 128_000),
            ContextRule(listOf("glm"), 128_000),

            // ---- Moonshot -------------------------------------------------------
            ContextRule(listOf("kimi"), 262_144),
            ContextRule(listOf("moonshot"), 131_072),

            // ---- Mistral --------------------------------------------------------
            ContextRule(listOf("magistral"), 1_048_576),
            ContextRule(listOf("codestral"), 262_144),
            ContextRule(listOf("mistral"), 131_072),

            // ---- xAI ------------------------------------------------------------
            ContextRule(listOf("grok4"), 256_000),
            ContextRule(listOf("grok3"), 131_072),
            ContextRule(listOf("grok"), 131_072),

            // ---- Others ---------------------------------------------------------
            ContextRule(listOf("minimax"), 1_000_000),
            ContextRule(listOf("doubao"), 262_144),
            ContextRule(listOf("hunyuan"), 128_000),
            ContextRule(listOf("ernie"), 128_000),
            ContextRule(listOf("seed"), 262_144),
            ContextRule(listOf("commandr"), 128_000),
            ContextRule(listOf("jamba"), 131_072),
            ContextRule(listOf("nemotron"), 131_072),

            // Short reasoning-model families are matched last so they cannot shadow a
            // real family rule that merely contains those two characters.
            ContextRule(listOf("o3"), 200_000),
            ContextRule(listOf("o4"), 200_000),
            ContextRule(listOf("o1"), 200_000),
        )
    }
}
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
 * Declared provider metadata always wins; the public fallback is best-effort and cached in memory.
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
        // The explicit allowlist is authoritative. A public catalog can be stale or expose a
        // route-specific value, but the user-facing model family mapping must stay deterministic.
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

    private fun knownContextLength(key: String): Int? = when {
        // Explicit family allowlist. V4 Flash, V4 Pro and the bare V4 family label are 1M.
        key == "deepseekv4" || key == "deepseekv4pro" || key == "deepseekv4flash" -> 1_000_000
        key == "gpt4o" || key == "gpt4oturbo" -> 128_000
        key.startsWith("gpt41") -> 1_048_576
        key.startsWith("claude35sonnet") || key.startsWith("claude37sonnet") || key.startsWith("claudesonnet4") -> 200_000
        key.startsWith("gemini25pro") || key.startsWith("gemini25flash") -> 1_048_576
        else -> null
    }

    private fun firstPositiveInt(json: JSONObject, vararg keys: String): Int? =
        keys.firstNotNullOfOrNull { key -> json.optInt(key, 0).takeIf { it > 0 } }

    companion object {
        private const val MAX_RESPONSE_CHARS = 512 * 1024
    }
}

package me.rerere.rikkahub.data.translation

import okhttp3.HttpUrl
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONArray
import java.util.Locale
import java.util.concurrent.TimeUnit

/**
 * Lightweight network translation fallback. It uses a public HTTPS endpoint and has no embedded
 * credential. The result is deliberately treated as untrusted text and is never executed.
 */
class NetworkTranslator(
    private val client: OkHttpClient,
) {
    fun translate(sourceText: String, targetLanguage: Locale): String {
        require(sourceText.isNotBlank()) { "翻译内容不能为空" }
        require(sourceText.length <= MAX_SOURCE_CHARS) { "翻译内容过长" }
        val url = HttpUrl.Builder()
            .scheme("https")
            .host("translate.googleapis.com")
            .addPathSegments("translate_a/single")
            .addQueryParameter("client", "gtx")
            .addQueryParameter("sl", "auto")
            .addQueryParameter("tl", targetLanguage.toLanguageTag())
            .addQueryParameter("dt", "t")
            .addQueryParameter("q", sourceText)
            .build()
        val request = Request.Builder().url(url).get().build()
        val call = client.newCall(request)
        call.timeout().timeout(5, TimeUnit.SECONDS)
        call.execute().use { response ->
            require(response.isSuccessful) { "网络翻译请求失败：HTTP ${response.code}" }
            val body = response.body?.string().orEmpty()
            require(body.length <= MAX_RESPONSE_CHARS) { "网络翻译响应过大" }
            return parseTranslation(body)
        }
    }

    private fun parseTranslation(body: String): String {
        val root = JSONArray(body)
        val segments = root.optJSONArray(0) ?: return ""
        return buildString {
            for (index in 0 until segments.length()) {
                val segment = segments.optJSONArray(index) ?: continue
                append(segment.optString(0))
            }
        }.trim()
    }

    companion object {
        private const val MAX_SOURCE_CHARS = 100_000
        private const val MAX_RESPONSE_CHARS = 2_000_000
    }
}

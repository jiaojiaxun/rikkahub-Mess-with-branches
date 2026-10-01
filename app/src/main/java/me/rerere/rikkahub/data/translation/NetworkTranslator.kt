package me.rerere.rikkahub.data.translation

import okhttp3.HttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import java.io.InterruptedIOException
import java.util.Locale
import java.util.concurrent.TimeUnit

/**
 * Network translation via the translator endpoint Microsoft Edge uses for page translation.
 *
 * Why not Google: translate.googleapis.com is blocked in mainland China, so every call timed
 * out. Edge's endpoint is reachable there, needs no credential and takes a POST JSON body
 * (an array of strings), so long text no longer has to fit in a URL.
 *
 * Caveat: this is an unofficial endpoint Edge uses internally. It can change without notice;
 * failures surface as a readable error instead of a hang. The result is treated as untrusted
 * text and is never executed.
 */
class NetworkTranslator(
    private val client: OkHttpClient,
) {
    fun translate(sourceText: String, targetLanguage: Locale): String {
        require(sourceText.isNotBlank()) { "翻译内容不能为空" }
        require(sourceText.length <= MAX_SOURCE_CHARS) { "翻译内容过长" }

        val chunks = chunkForTranslation(sourceText)
        val target = microsoftLanguageCode(targetLanguage)
        val out = StringBuilder(sourceText.length)
        var batch = mutableListOf<TranslationChunk>()
        var batchChars = 0

        fun flush() {
            if (batch.isEmpty()) return
            val translated = requestBatch(batch.map { it.text }, target)
            batch.forEachIndexed { i, chunk ->
                out.append(translated.getOrElse(i) { chunk.text }).append(chunk.separator)
            }
            batch = mutableListOf()
            batchChars = 0
        }

        for (chunk in chunks) {
            if (batchChars + chunk.text.length > MAX_REQUEST_CHARS || batch.size >= MAX_ITEMS_PER_REQUEST) {
                flush()
            }
            batch.add(chunk)
            batchChars += chunk.text.length
        }
        flush()
        return out.toString().trim()
    }

    private fun requestBatch(texts: List<String>, target: String): List<String> {
        val url = HttpUrl.Builder()
            .scheme("https")
            .host("edge.microsoft.com")
            .addPathSegments("translate/translatetext")
            .addQueryParameter("from", "") // empty = auto-detect
            .addQueryParameter("to", target)
            .addQueryParameter("isEnterpriseClient", "false")
            .build()
        val body = JSONArray(texts).toString().toRequestBody(JSON)
        val request = Request.Builder().url(url).post(body).build()
        val call = client.newCall(request)
        call.timeout().timeout(REQUEST_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        try {
            call.execute().use { response ->
                require(response.isSuccessful) { "网络翻译请求失败：HTTP ${response.code}" }
                val raw = response.body?.string().orEmpty()
                require(raw.length <= MAX_RESPONSE_CHARS) { "网络翻译响应过大" }
                return parseTranslations(raw)
            }
        } catch (e: InterruptedIOException) {
            throw IllegalStateException("网络翻译超时（${REQUEST_TIMEOUT_SECONDS} 秒），请检查网络", e)
        }
    }

    /** Response: [{"translations":[{"text":"...","to":"zh-Hans"}]}, ...], one entry per input. */
    private fun parseTranslations(raw: String): List<String> {
        val root = JSONArray(raw)
        return List(root.length()) { i ->
            root.optJSONObject(i)
                ?.optJSONArray("translations")
                ?.optJSONObject(0)
                ?.optString("text")
                .orEmpty()
        }
    }

    companion object {
        private val JSON = "application/json; charset=utf-8".toMediaType()
        private const val MAX_SOURCE_CHARS = 100_000
        private const val MAX_RESPONSE_CHARS = 2_000_000
        private const val REQUEST_TIMEOUT_SECONDS = 15L
        internal const val MAX_CHUNK_CHARS = 1_000
        private const val MAX_REQUEST_CHARS = 4_500
        private const val MAX_ITEMS_PER_REQUEST = 50
    }
}

/** A piece of the source text plus what to append after its translation when re-joining. */
internal data class TranslationChunk(val text: String, val separator: String)

/**
 * Split at line boundaries so each item stays under [NetworkTranslator.MAX_CHUNK_CHARS];
 * a single line longer than that is hard-split. Re-joining the translations with each
 * chunk's [TranslationChunk.separator] restores the original line structure.
 */
internal fun chunkForTranslation(text: String, maxChars: Int = NetworkTranslator.MAX_CHUNK_CHARS): List<TranslationChunk> {
    val result = mutableListOf<TranslationChunk>()
    val current = StringBuilder()
    fun emit(separator: String) {
        if (current.isNotEmpty()) {
            result.add(TranslationChunk(current.toString(), separator))
            current.clear()
        } else if (separator.isNotEmpty() && result.isNotEmpty()) {
            // Blank line: keep it by extending the previous separator.
            val last = result.removeAt(result.lastIndex)
            result.add(last.copy(separator = last.separator + separator))
        }
    }
    for (line in text.split("\n")) {
        if (line.length > maxChars) {
            if (current.isNotEmpty()) emit("\n")
            val lastPiece = (line.length - 1) / maxChars
            line.chunked(maxChars).forEachIndexed { i, piece ->
                current.append(piece)
                emit(if (i == lastPiece) "\n" else "")
            }
            continue
        }
        if (current.isNotEmpty() && current.length + 1 + line.length > maxChars) emit("\n")
        if (current.isNotEmpty()) current.append('\n')
        current.append(line)
    }
    emit("")
    return result
}

/** Map a Java locale to Microsoft Translator's language codes. */
internal fun microsoftLanguageCode(locale: Locale): String {
    val lang = locale.language.lowercase(Locale.ROOT)
    return when (lang) {
        "zh" -> {
            val traditional = locale.script.equals("Hant", ignoreCase = true) ||
                locale.country.uppercase(Locale.ROOT) in setOf("TW", "HK", "MO")
            if (traditional) "zh-Hant" else "zh-Hans"
        }
        "pt" -> if (locale.country.equals("PT", ignoreCase = true)) "pt-pt" else "pt"
        "iw" -> "he" // legacy Java code for Hebrew
        "in" -> "id" // legacy Java code for Indonesian
        "nb", "no" -> "nb"
        else -> lang.ifBlank { "en" }
    }
}

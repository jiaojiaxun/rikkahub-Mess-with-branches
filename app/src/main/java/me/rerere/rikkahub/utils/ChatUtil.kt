package me.rerere.rikkahub.utils

import android.content.Context
import android.net.Uri
import android.util.Log
import me.rerere.ai.ui.UIMessage
import me.rerere.rikkahub.Screen
import me.rerere.rikkahub.ui.context.Navigator
import java.nio.ByteBuffer
import java.nio.charset.CharacterCodingException
import java.nio.charset.CodingErrorAction
import kotlin.uuid.Uuid

private const val TAG = "ChatUtil"

fun navigateToChatPage(
    navigator: Navigator,
    chatId: Uuid = Uuid.random(),
    initText: String? = null,
    initFiles: List<Uri> = emptyList(),
    nodeId: Uuid? = null,
) {
    Log.i(TAG, "navigateToChatPage: navigate to $chatId")
    navigator.clearAndNavigate(
        Screen.Chat(
            id = chatId.toString(),
            text = initText,
            files = initFiles.map { it.toString() },
            nodeId = nodeId?.toString(),
        )
    )
}

fun Context.copyMessageToClipboard(message: UIMessage) {
    this.writeClipboardText(message.toText())
}

private val ALLOWED_MIME_TYPES = setOf(
    "text/plain",
    "text/html",
    "text/css",
    "text/javascript",
    "text/csv",
    "text/xml",
    "application/json",
    "application/javascript",
    "application/xml",
    "application/x-yaml",
    "application/x-sh",
    "application/sql",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/epub+zip"
)

private val ALLOWED_FILE_EXTENSIONS = setOf(
    "txt", "md", "csv", "tsv", "json", "jsonl", "ndjson", "ipynb",
    "js", "jsx", "mjs", "cjs", "html", "htm", "css", "scss", "sass", "less",
    "vue", "svelte", "xml", "xaml", "svg", "agc",
    "py", "rb", "lua", "sql", "java", "kt", "ts", "tsx", "dart", "php", "swift", "go",
    "scala", "groovy", "pl", "r", "m", "mm", "vb", "asm", "s", "zig", "nim", "ex", "exs",
    "erl", "hs", "clj", "elm", "jl",
    "bat", "cmd", "ps1", "psm1", "sh", "bash", "zsh", "fish",
    "c", "h", "cpp", "cc", "cxx", "hpp", "hh", "hxx", "rs", "cs",
    "markdown", "mdx", "rst", "tex", "org", "adoc",
    "toml", "ini", "cfg", "conf", "env", "gradle", "kts", "properties", "cmake", "mk",
    "proto", "graphql", "gql", "yml", "yaml", "log", "diff", "patch",
    "srt", "vtt", "ass", "lrc", "gitignore", "editorconfig", "dockerfile", "makefile",
)

fun isAllowedFileType(fileName: String, mime: String): Boolean {
    if (mime in ALLOWED_MIME_TYPES || mime.startsWith("text/")) return true
    val extension = fileName.substringAfterLast('.', "").lowercase()
    if (extension in ALLOWED_FILE_EXTENSIONS) return true
    // Extension-less names such as Dockerfile / Makefile.
    return fileName.lowercase() in ALLOWED_FILE_EXTENSIONS
}

/**
 * True when [sample] (the first bytes of a file) looks like UTF-8 text: no NUL bytes and
 * decodable. Used to accept text files with unknown extensions as chat attachments.
 */
fun looksLikeText(sample: ByteArray): Boolean {
    if (sample.isEmpty()) return true
    if (sample.any { it == 0.toByte() }) return false
    val decoder = Charsets.UTF_8.newDecoder()
        .onMalformedInput(CodingErrorAction.REPORT)
        .onUnmappableCharacter(CodingErrorAction.REPORT)
    // The sample may end in the middle of a multi-byte character: allow up to 3 cut bytes.
    for (cut in 0..3) {
        val length = sample.size - cut
        if (length <= 0) break
        try {
            decoder.reset()
            decoder.decode(ByteBuffer.wrap(sample, 0, length))
            return true
        } catch (_: CharacterCodingException) {
            // try a shorter prefix
        }
    }
    return false
}

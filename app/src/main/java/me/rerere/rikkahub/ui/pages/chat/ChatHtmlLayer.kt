package me.rerere.rikkahub.ui.pages.chat

import android.annotation.SuppressLint
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.runtime.collectAsState
import kotlinx.coroutines.delay
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinStore

/**
 * Bridge object injected into the skin WebView as `AndroidChatBridge`. The skin's JS
 * calls [postMessage] with a JSON string; events are queued thread-safely and drained
 * on the main thread by the recomposition loop.
 *
 * Thread note: addJavascriptInterface callbacks arrive on a WebView-internal thread.
 * We only touch a synchronized queue here — no UI or state calls from the JS thread.
 */
class ChatHtmlBridge {
    private val queue = ArrayDeque<String>()
    private val lock = Any()

    /** Poll one event; must be called from the main thread. */
    fun poll(): String? = synchronized(lock) {
        if (queue.isEmpty()) null else queue.removeFirst()
    }

    @JavascriptInterface
    fun postMessage(json: String) {
        synchronized(lock) { queue.addLast(json) }
    }

    companion object {
        const val NAME = "AndroidChatBridge"
    }
}

/**
 * Parse a bridge event string: {"type": "...", ...} → (type, payload).
 * Returns null on malformed JSON or a missing/blank type.
 */
internal fun parseBridgeEvent(json: String): Pair<String, JsonObject>? {
    val obj = runCatching { Json.parseToJsonElement(json) as? JsonObject }.getOrNull() ?: return null
    val type = (obj["type"] as? JsonPrimitive)?.content?.takeIf { it.isNotBlank() } ?: return null
    return type to obj
}

/**
 * Full-bleed HTML layer for the chat page (dual-mode UI, HTML side).
 *
 * Rendered when html mode is on. The native message list and input bar keep working
 * — this layer sits behind them; the skin can style the visible chrome through its
 * own DOM (background, bubbles, floating widgets) while native features (send text,
 * attach files) are untouched.
 *
 * Rendering: the skin file is loaded with `loadDataWithBaseURL` using a synthetic
 * https base (no real origin), so relative URLs cannot escape to the filesystem.
 */
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun ChatHtmlLayer(
    skinStore: ChatHtmlSkinStore,
    onBridgeEvent: (type: String, payload: JsonObject) -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val state by skinStore.stateFlow.collectAsState()
    if (!state.htmlModeEnabled) return
    val skinFile = remember(state.activeSkinId) {
        skinStore.activeSkinFile(context)
    }
    if (skinFile == null) return
    val html = remember(skinFile) { runCatching { skinFile.readText() }.getOrNull() }
    if (html == null) return

    val bridge = remember { ChatHtmlBridge() }
    var webview by remember { mutableStateOf<WebView?>(null) }

    // Drain bridge events on the main thread (poll loop; see [ChatHtmlBridge] for the
    // thread-safety contract). 50ms cadence keeps taps feel instant without busy-waiting.
    LaunchedEffect(webview) {
        while (true) {
            bridge.poll()?.let { raw ->
                parseBridgeEvent(raw)?.let { (type, payload) -> onBridgeEvent(type, payload) }
            }
            delay(50)
        }
    }

    Box(modifier = modifier.fillMaxSize()) {
        AndroidView(
            factory = { ctx ->
                WebView(ctx).apply {
                    layoutParams = android.view.ViewGroup.LayoutParams(
                        android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                        android.view.ViewGroup.LayoutParams.MATCH_PARENT,
                    )
                    settings.javaScriptEnabled = true
                    settings.domStorageEnabled = true
                    // Skin is self-contained (enforced by chat_ui_write policy): no file
                    // or content access is ever needed.
                    settings.allowFileAccess = false
                    settings.allowContentAccess = false
                    // Synthetic origin — blocks navigation to real origins while keeping
                    // inline JS and https images functional. Links are not followed.
                    webViewClient = object : WebViewClient() {
                        override fun shouldOverrideUrlLoading(
                            view: WebView?,
                            request: android.webkit.WebResourceRequest?,
                        ): Boolean = true
                    }
                    addJavascriptInterface(bridge, ChatHtmlBridge.NAME)
                    webview = this
                    loadSkin(this, html)
                }
            },
            update = { /* static content: nothing to update on recomposition */ },
        )
    }
}

/** Load the skin with a synthetic https base so relative paths stay virtual. */
private fun loadSkin(view: WebView, html: String) {
    view.loadDataWithBaseURL(
        /* baseUrl = */ "https://rikkahub-skin.local/",
        /* data = */ html,
        /* mimeType = */ "text/html",
        /* encoding = */ "utf-8",
        /* historyUrl = */ null,
    )
}

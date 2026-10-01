package me.rerere.rikkahub.ui.pages.chat

import android.annotation.SuppressLint
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.MutableState
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import kotlinx.coroutines.delay
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinStore

/**
 * Bridge object injected into the skin WebView as `AndroidChatBridge`. The skin's JS
 * calls [postMessage] with a JSON string; events are queued thread-safely and drained
 * on the main thread by the recomposition loop.
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

/** Parse a bridge event string: {"type": "...", ...} -> (type, payload). */
internal fun parseBridgeEvent(json: String): Pair<String, JsonObject>? {
    val obj = runCatching { Json.parseToJsonElement(json) as? JsonObject }.getOrNull() ?: return null
    val type = (obj["type"] as? JsonPrimitive)?.contentOrNull?.takeIf { it.isNotBlank() } ?: return null
    return type to obj
}

/**
 * Layout state shared between the skin layer and the native chat list.
 *
 * [reservedTopDp] is the height of the skin's header band (below the native top bar).
 * ChatList adds it to its top padding so native messages never scroll over the skin
 * header. [active] is true while a skin is rendered; native secondary text uses it to
 * switch to a readable style ([rhReadableOnSkin]).
 */
object ChatHtmlLayout {
    val reservedTopDp: MutableState<Int> = mutableStateOf(0)
    val active: MutableState<Boolean> = mutableStateOf(false)
}

/**
 * Gives native secondary text (stats line, loading status) a translucent pill while an
 * HTML skin is behind it, so it stays readable whatever the skin colors are.
 */
@Composable
fun Modifier.rhReadableOnSkin(): Modifier {
    if (!ChatHtmlLayout.active.value) return this
    val bg = MaterialTheme.colorScheme.surface.copy(alpha = 0.85f)
    return this
        .clip(RoundedCornerShape(8.dp))
        .background(bg)
        .padding(horizontal = 6.dp, vertical = 2.dp)
}

/** Height reserved for the native TopAppBar, excluding the status bar. */
private const val TOP_BAR_DP = 64

/** Approximate height of the native ChatInput, excluding the navigation bar (heuristic). */
private const val INPUT_BAR_DP = 136

/** Theme colors exposed to the skin as CSS variables. */
internal data class SkinTheme(
    val primary: String,
    val onPrimary: String,
    val surface: String,
    val onSurface: String,
    val background: String,
    val onBackground: String,
    val dark: Boolean,
)

private fun Color.toCssHex(): String = String.format("#%06X", 0xFFFFFF and toArgb())

/**
 * Full-bleed HTML layer for the chat page (dual-mode UI, HTML side).
 *
 * Layout contract: the skin may own a header band (below the native top bar) and small
 * edge widgets. The header height is declared with <meta name="rh-header-height"> or
 * measured from the skin's in-flow content, and the native list starts below it. The
 * message area gets a translucent scrim so native bubbles and text stay readable.
 */
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun ChatHtmlLayer(
    skinStore: ChatHtmlSkinStore,
    onBridgeEvent: (type: String, payload: JsonObject) -> Unit,
    modifier: Modifier = Modifier,
) {
    val state by skinStore.stateFlow.collectAsState()
    if (!state.htmlModeEnabled) return
    val skinFile = remember(state.activeSkinId) { skinStore.activeSkinFile() } ?: return
    val lastModified = skinFile.lastModified()
    val rawHtml = remember(skinFile, lastModified) {
        runCatching { skinFile.readText() }.getOrNull()
    } ?: return

    // Leaving composition (html mode off, skin removed) restores the native layout.
    DisposableEffect(Unit) {
        ChatHtmlLayout.active.value = true
        onDispose {
            ChatHtmlLayout.active.value = false
            ChatHtmlLayout.reservedTopDp.value = 0
        }
    }

    val density = LocalDensity.current
    val safeTop = (WindowInsets.statusBars.getTop(density) / density.density).toInt() + TOP_BAR_DP
    val safeBottom = (WindowInsets.navigationBars.getBottom(density) / density.density).toInt() + INPUT_BAR_DP
    val latestSafe = remember { IntArray(2) }
    latestSafe[0] = safeTop
    latestSafe[1] = safeBottom
    // A header taller than 40% of the screen would leave no room for the conversation.
    val maxHeaderDp = (LocalConfiguration.current.screenHeightDp * 0.4f).toInt()

    val scheme = MaterialTheme.colorScheme
    val theme = SkinTheme(
        primary = scheme.primary.toCssHex(),
        onPrimary = scheme.onPrimary.toCssHex(),
        surface = scheme.surface.toCssHex(),
        onSurface = scheme.onSurface.toCssHex(),
        background = scheme.background.toCssHex(),
        onBackground = scheme.onBackground.toCssHex(),
        dark = scheme.background.luminance() < 0.5f,
    )
    val html = remember(rawHtml, theme) { injectSkinPrelude(rawHtml, theme, safeTop, safeBottom) }

    val bridge = remember { ChatHtmlBridge() }
    var webview by remember { mutableStateOf<WebView?>(null) }

    LaunchedEffect(webview, maxHeaderDp) {
        while (true) {
            bridge.poll()?.let { raw ->
                parseBridgeEvent(raw)?.let { (type, payload) ->
                    if (type == "rh_layout") {
                        // Internal prelude event, never forwarded to the page callback.
                        val header = (payload["header"] as? JsonPrimitive)?.contentOrNull
                            ?.toDoubleOrNull()?.toInt() ?: 0
                        ChatHtmlLayout.reservedTopDp.value = header.coerceIn(0, maxHeaderDp)
                    } else {
                        onBridgeEvent(type, payload)
                    }
                }
            }
            delay(50)
        }
    }

    LaunchedEffect(webview, safeTop, safeBottom) {
        webview?.evaluateJavascript(safeAreaScript(safeTop, safeBottom), null)
    }

    val reservedTop = ChatHtmlLayout.reservedTopDp.value
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
                    settings.allowFileAccess = false
                    settings.allowContentAccess = false
                    webViewClient = object : WebViewClient() {
                        override fun shouldOverrideUrlLoading(
                            view: WebView?,
                            request: android.webkit.WebResourceRequest?,
                        ): Boolean = true

                        override fun onPageFinished(view: WebView?, url: String?) {
                            view?.evaluateJavascript(safeAreaScript(latestSafe[0], latestSafe[1]), null)
                        }
                    }
                    addJavascriptInterface(bridge, ChatHtmlBridge.NAME)
                    webview = this
                }
            },
            update = { view ->
                val key = html.hashCode()
                if (view.tag != key) {
                    view.tag = key
                    loadSkin(view, html)
                }
            },
        )
        // Scrim over the message area only: the header band stays vivid, native bubbles and
        // text below it keep their contrast. No pointer input, so taps still reach the skin.
        Box(
            modifier = Modifier
                .fillMaxSize()
                .padding(top = (safeTop + reservedTop).dp)
                .background(scheme.background.copy(alpha = 0.5f))
        )
    }
}

private fun safeAreaScript(top: Int, bottom: Int): String =
    "window.__rhSetSafeArea&&window.__rhSetSafeArea($top,$bottom)"

/** Load the skin with a synthetic https base so relative paths stay virtual. */
private fun loadSkin(view: WebView, html: String) {
    view.loadDataWithBaseURL("https://rikkahub-skin.local/", html, "text/html", "utf-8", null)
}

private val VIEWPORT_META = Regex("""<meta[^>]+name\s*=\s*["']?viewport""", RegexOption.IGNORE_CASE)
private val HEAD_OPEN = Regex("""<head(\s[^>]*)?>""", RegexOption.IGNORE_CASE)
private val HTML_OPEN = Regex("""<html(\s[^>]*)?>""", RegexOption.IGNORE_CASE)
private val DOCTYPE = Regex("""<!doctype[^>]*>""", RegexOption.IGNORE_CASE)

/**
 * Insert the safe-area / theme / fixer prelude at the start of <head> (or after <html> or
 * the doctype, so a doctype-first document never drops into quirks mode).
 * Skin opt-outs: data-rh-safe="off", data-rh-contrast="off".
 */
internal fun injectSkinPrelude(html: String, theme: SkinTheme, safeTop: Int, safeBottom: Int): String {
    fun fill(template: String) = template
        .replace("__TOP__", safeTop.toString())
        .replace("__BOTTOM__", safeBottom.toString())
        .replace("__PRIMARY__", theme.primary)
        .replace("__ON_PRIMARY__", theme.onPrimary)
        .replace("__SURFACE__", theme.surface)
        .replace("__ON_SURFACE__", theme.onSurface)
        .replace("__BACKGROUND__", theme.background)
        .replace("__ON_BACKGROUND__", theme.onBackground)
        .replace("__DARK__", theme.dark.toString())

    val prelude = buildString {
        if (!VIEWPORT_META.containsMatchIn(html)) {
            append("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">")
        }
        append("<style id=\"rh-prelude-style\">").append(fill(SKIN_PRELUDE_CSS)).append("</style>")
        append("<script id=\"rh-prelude-script\">").append(fill(SKIN_PRELUDE_JS)).append("</script>")
    }
    val anchor = HEAD_OPEN.find(html) ?: HTML_OPEN.find(html) ?: DOCTYPE.find(html)
    return if (anchor != null) {
        val at = anchor.range.last + 1
        html.substring(0, at) + prelude + html.substring(at)
    } else {
        prelude + html
    }
}

private val SKIN_PRELUDE_CSS = """
:root{--rh-safe-top:__TOP__px;--rh-safe-bottom:__BOTTOM__px;--rh-primary:__PRIMARY__;--rh-on-primary:__ON_PRIMARY__;--rh-surface:__SURFACE__;--rh-on-surface:__ON_SURFACE__;--rh-background:__BACKGROUND__;--rh-on-background:__ON_BACKGROUND__;}
body{box-sizing:border-box;padding-top:var(--rh-safe-top);padding-bottom:var(--rh-safe-bottom);}
""".trimIndent()

// No dollar sign anywhere in this script: it is a Kotlin raw string.
private val SKIN_PRELUDE_JS = """
(function(){
var S={top:__TOP__,bottom:__BOTTOM__,header:-1};
function parse(c){var m=/rgba?\(([^)]+)\)/.exec(c||'');if(!m)return null;var p=m[1].split(',').map(parseFloat);return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1};}
function ch(v){v/=255;return v<=0.03928?v/12.92:Math.pow((v+0.055)/1.055,2.4);}
function lum(c){return 0.2126*ch(c.r)+0.7152*ch(c.g)+0.0722*ch(c.b);}
function ratio(a,b){var x=lum(a),y=lum(b);return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05);}
function off(el,k){return !!(el.dataset&&el.dataset[k]==='off');}
function solidBg(el){while(el&&el.nodeType===1){var cs=getComputedStyle(el);if(cs.backgroundImage&&cs.backgroundImage!=='none')return null;var c=parse(cs.backgroundColor);if(c&&c.a>=0.6)return c;el=el.parentElement;}return {r:255,g:255,b:255,a:1};}
function fixContrast(){document.querySelectorAll('button,[role=button],input[type=button],input[type=submit],a,[data-rh-action]').forEach(function(el){
if(off(el,'rhContrast'))return;var cs=getComputedStyle(el);if(cs.display==='none'||cs.visibility==='hidden')return;
if(cs.backgroundImage&&cs.backgroundImage!=='none')return;
var fg=parse(cs.color);if(!fg)return;var own=parse(cs.backgroundColor);
var bg=(own&&own.a>=0.6)?own:solidBg(el.parentElement);
if(!bg){if(el.tagName!=='A'){el.style.setProperty('background-color','var(--rh-primary)','important');el.style.setProperty('color','var(--rh-on-primary)','important');}return;}
if(ratio(fg,bg)>=4.5)return;
el.style.setProperty('color',lum(bg)>0.179?'#111111':'#FFFFFF','important');});}
function fixFixed(){var vh=window.innerHeight;document.querySelectorAll('body *').forEach(function(el){
if(off(el,'rhSafe'))return;var cs=getComputedStyle(el);if(cs.position!=='fixed'&&cs.position!=='sticky')return;
var r=el.getBoundingClientRect();if(!r.width||!r.height||r.height>vh*0.6)return;
if(r.bottom>vh-S.bottom&&r.top>vh*0.4){el.style.setProperty('bottom',(S.bottom+8)+'px','important');el.style.setProperty('top','auto','important');}
else if(r.top<S.top&&r.bottom<vh*0.6){el.style.setProperty('top',(S.top+8)+'px','important');el.style.setProperty('bottom','auto','important');}});}
function headerHeight(){var m=document.querySelector('meta[name=rh-header-height]');
if(m){var v=parseInt(m.getAttribute('content'),10);return isNaN(v)?0:Math.max(0,v);}
var h=0,kids=document.body?document.body.children:[];for(var i=0;i<kids.length;i++){var el=kids[i];
if(el.tagName==='SCRIPT'||el.tagName==='STYLE')continue;var cs=getComputedStyle(el);
if(cs.position==='fixed'||cs.position==='absolute'||cs.display==='none')continue;
var r=el.getBoundingClientRect();if(r.height>0){var b=r.bottom+window.scrollY;if(b>h)h=b;}}
return Math.max(0,Math.round(h-S.top));}
function reportLayout(){var h=headerHeight();if(h===S.header)return;S.header=h;
try{AndroidChatBridge.postMessage(JSON.stringify({type:'rh_layout',header:h}));}catch(e){}}
var t=null;function run(){clearTimeout(t);t=setTimeout(function(){try{fixFixed();}catch(e){}try{fixContrast();}catch(e){}try{reportLayout();}catch(e){}},120);}
window.__rhSetSafeArea=function(top,bottom){S.top=top;S.bottom=bottom;S.header=-1;var st=document.documentElement.style;st.setProperty('--rh-safe-top',top+'px');st.setProperty('--rh-safe-bottom',bottom+'px');run();};
window.__rhTheme={dark:__DARK__};
document.addEventListener('DOMContentLoaded',function(){run();try{new MutationObserver(run).observe(document.body,{childList:true,subtree:true});}catch(e){}});
window.addEventListener('load',run);window.addEventListener('resize',run);
})();
""".trimIndent()

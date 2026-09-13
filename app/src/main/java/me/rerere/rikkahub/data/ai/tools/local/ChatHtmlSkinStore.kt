package me.rerere.rikkahub.data.ai.tools.local

import android.content.Context
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import me.rerere.rikkahub.AppScope
import java.io.File

/**
 * Standalone persistence for the AI-authored chat HTML skin.
 *
 * Why not Settings: PreferencesStore.kt is already a huge serialised blob where every
 * field add is a schema/migration concern; the skin toggle is a UI-layer concern that
 * must not take the whole Settings object hostage. A dedicated tiny DataStore keeps
 * the surface small and the settings migration path untouched.
 *
 * Access: created once at app start via [ChatHtmlSkinGlobal.init] (same pattern as
 * AgentWorkspace.init) and read from [ChatHtmlSkinGlobal.store] everywhere else. UI
 * and tool code never construct their own instance — two DataStore instances over one
 * file would corrupt the state file.
 */
private val Context.chatHtmlSkinDataStore by preferencesDataStore(name = "chat_html_skin")

data class ChatHtmlSkinState(
    val activeSkinId: String? = null,
    val htmlModeEnabled: Boolean = false,
)

object ChatHtmlSkinGlobal {
    @Volatile
    private var instance: ChatHtmlSkinStore? = null

    /** Must be called once from Application.onCreate, before any UI or tool reads it. */
    fun init(context: Context, scope: AppScope) {
        if (instance == null) {
            synchronized(this) {
                if (instance == null) {
                    instance = ChatHtmlSkinStore(context, scope)
                }
            }
        }
    }

    /** The single store instance; throws when accessed before [init]. */
    val store: ChatHtmlSkinStore
        get() = instance ?: error("ChatHtmlSkinGlobal not initialised; call init(context, scope) first")

    /** True when [init] has run — lets UI degrade gracefully instead of crashing. */
    val isReady: Boolean get() = instance != null
}

class ChatHtmlSkinStore(
    context: Context,
    private val scope: AppScope,
) {
    private val appContext = context.applicationContext

    private object Keys {
        val ACTIVE_SKIN = stringPreferencesKey("active_skin_id")
        val MODE_ENABLED = booleanPreferencesKey("html_mode_enabled")
    }

    private val _stateFlow = MutableStateFlow(ChatHtmlSkinState())
    val stateFlow: MutableStateFlow<ChatHtmlSkinState> = _stateFlow

    init {
        // DataStore stays authoritative across process death; _stateFlow gives Compose a
        // synchronous snapshot. collect never cancels — singleton lifetime, by design.
        scope.launch {
            appContext.chatHtmlSkinDataStore.data.collect { prefs ->
                _stateFlow.value = ChatHtmlSkinState(
                    activeSkinId = prefs[Keys.ACTIVE_SKIN],
                    htmlModeEnabled = prefs[Keys.MODE_ENABLED] ?: false,
                )
            }
        }
    }

    /** Directory holding skin files; created on demand. */
    fun skinsDir(): File = File(appContext.filesDir, "chat-html").apply { mkdirs() }

    /** Resolve a skin id to its file (no existence check). */
    fun skinFile(id: String): File = File(skinsDir(), "$id.html")

    /** List available skin ids (sorted). */
    fun listSkinIds(): List<String> =
        skinsDir().listFiles { f -> f.isFile && f.name.endsWith(".html") }
            ?.map { it.name.removeSuffix(".html") }
            ?.sorted()
            ?: emptyList()

    /** Activate [skinId] and enable html mode. */
    fun setActive(skinId: String) {
        scope.launch {
            appContext.chatHtmlSkinDataStore.edit { prefs ->
                prefs[Keys.ACTIVE_SKIN] = skinId
                prefs[Keys.MODE_ENABLED] = true
            }
        }
    }

    /** Toggle html mode; keeps the chosen skin id. */
    fun setMode(enabled: Boolean) {
        scope.launch {
            appContext.chatHtmlSkinDataStore.edit { prefs ->
                prefs[Keys.MODE_ENABLED] = enabled
            }
        }
    }

    /** Current skin file, or null when none is set or the file was deleted externally. */
    fun activeSkinFile(): File? {
        val id = stateFlow.value.activeSkinId ?: return null
        val f = skinFile(id)
        return if (f.isFile) f else null
    }
}

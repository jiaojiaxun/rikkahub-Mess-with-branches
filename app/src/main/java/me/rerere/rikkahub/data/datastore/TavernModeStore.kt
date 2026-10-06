package me.rerere.rikkahub.data.datastore

import android.content.Context

/**
 * rhTavernMode: 会话级酒馆模式开关(每个会话独立)。
 *
 * 用 SharedPreferences 按会话 ID 存一个 Boolean,而不是:
 *  - 改 Settings(全局,会串到别的会话)
 *  - 改数据库(升 Room 版本要同步 ImportedDatabaseReconciler 的
 *    EXPECTED_VERSION/IDENTITY_HASH,而 hash 要编译生成 schema json 才有 → 死循环)
 *
 * 故意独立文件,不碰任何在链 patch 改过的文件。ChatVM 和 ChatService 都有
 * Context,直接调用即可。
 */
object TavernModeStore {
    private const val PREFS_NAME = "tavern_mode_prefs"

    private fun prefs(context: Context) =
        context.applicationContext.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun isEnabled(context: Context, conversationId: String): Boolean =
        prefs(context).getBoolean(conversationId, false)

    fun setEnabled(context: Context, conversationId: String, enabled: Boolean) {
        prefs(context).edit().putBoolean(conversationId, enabled).apply()
    }
}

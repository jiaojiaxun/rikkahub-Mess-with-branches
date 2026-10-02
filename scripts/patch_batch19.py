from pathlib import Path

ROOT = Path.cwd()


def patch(path, replacements):
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    for old, new in replacements:
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"{path}: anchor count {count} != 1: {old[:100]!r}")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")


ONOPEN_OLD = """                override fun onOpen(db: SupportSQLiteDatabase) {
                    // Both steps below are best-effort FTS setup: a failure here (missing dict
                    // assets, FTS5 module unavailable, native lib not loaded yet) must degrade
                    // search, not crash every single app launch by throwing out of onOpen and
                    // failing the whole database open.
                    try {
                        val dictDir = SimpleDictManager.extractDict(context)
                        val cursor = db.query("SELECT jieba_dict(?)", arrayOf(dictDir.absolutePath))
                        cursor.use {
                            if (it.moveToFirst()) {
                                val result = it.getString(0)
                                val success = result?.trimEnd('/') == dictDir.absolutePath.trimEnd('/')
                                if (!success) {
                                    android.util.Log.e(
                                        "DataSourceModule",
                                        "jieba_dict failed: $result, path=${dictDir.absolutePath}"
                                    )
                                }
                            }
                        }
                    } catch (e: Exception) {
                        android.util.Log.e("DataSourceModule", "onOpen: jieba_dict setup failed", e)
                    }

                    try {
                        db.execSQL(me.rerere.rikkahub.data.db.fts.MESSAGE_FTS_CREATE_SQL.trimIndent())
                    } catch (e: Exception) {
                        android.util.Log.e("DataSourceModule", "onOpen: message_fts table creation failed", e)
                    }
                }
"""

ONOPEN_NEW = """                override fun onOpen(db: SupportSQLiteDatabase) {
                    // Best-effort FTS table creation only. jieba dict registration moved off
                    // the DB-open critical path: it now prewarms on background coroutine.
                    try {
                        db.execSQL(me.rerere.rikkahub.data.db.fts.MESSAGE_FTS_CREATE_SQL.trimIndent())
                    } catch (e: Exception) {
                        android.util.Log.e("DataSourceModule", "onOpen: message_fts table creation failed", e)
                    }
                }
"""

patch(
    "app/src/main/java/me/rerere/rikkahub/di/DataSourceModule.kt",
    [
        (
            "import kotlinx.serialization.json.Json\n",
            "import kotlinx.coroutines.Dispatchers\n"
            "import kotlinx.coroutines.launch\n"
            "import kotlinx.serialization.json.Json\n",
        ),
        (
            "    single {\n"
            "        val context: Context = get()\n"
            "        Room.databaseBuilder(context, AppDatabase::class.java, \"rikka_hub\")\n",
            "    single {\n"
            "        val context: Context = get()\n"
            "        val appScope: AppScope = get()\n"
            "        Room.databaseBuilder(context, AppDatabase::class.java, \"rikka_hub\")\n",
        ),
        (ONOPEN_OLD, ONOPEN_NEW),
        (
            "                    options\n"
            "                }\n"
            "            )))\n"
            "            .build()\n"
            "    }\n",
            "                    options\n"
            "                }\n"
            "            )))\n"
            "            .build()\n"
            "            .also { database ->\n"
            "                // 后台预热 jieba 词典：不再阻塞 Room 首次 open\n"
            "                appScope.launch(Dispatchers.IO) {\n"
            "                    SimpleDictManager.ensureRegistered(context, database.openHelper.writableDatabase)\n"
            "                }\n"
            "            }\n"
            "    }\n",
        ),
        (
            "    single {\n        MessageFtsManager(get())\n    }\n",
            "    single {\n        MessageFtsManager(get(), get<Context>())\n    }\n",
        ),
    ],
)

ENSURE_FUN = """
    @Volatile
    private var registered = false
    private val registerLock = Any()

    /**
     * 幂等、best-effort jieba 词典注册。首次调用解压词典并执行 SELECT jieba_dict(?)
     * (磁盘 IO + 整本词典加载)，因此从 Room onOpen 挪出：DataSourceModule 后台预热 +
     * 搜索/索引路径懒注册兜底。失败只记日志，下次冷启动重试。
     */
    fun ensureRegistered(context: Context, db: SupportSQLiteDatabase) {
        if (registered) return
        synchronized(registerLock) {
            if (registered) return
            try {
                val dictDir = extractDict(context)
                val cursor = db.query("SELECT jieba_dict(?)", arrayOf(dictDir.absolutePath))
                cursor.use {
                    if (it.moveToFirst()) {
                        val result = it.getString(0)
                        if (result?.trimEnd('/') != dictDir.absolutePath.trimEnd('/')) {
                            Log.e("SimpleDictManager", "jieba_dict failed: $result, path=${dictDir.absolutePath}")
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e("SimpleDictManager", "ensureRegistered failed", e)
            }
            registered = true
        }
    }
"""

patch(
    "app/src/main/java/me/rerere/rikkahub/data/db/fts/SimpleDictManager.kt",
    [
        (
            "import android.content.Context\nimport java.io.File\n",
            "import android.content.Context\n"
            "import android.util.Log\n"
            "import androidx.sqlite.db.SupportSQLiteDatabase\n"
            "import java.io.File\n",
        ),
        (
            "    private const val CURRENT_VERSION = 1\n",
            "    private const val CURRENT_VERSION = 1\n" + ENSURE_FUN,
        ),
    ],
)

LAZY = "        appContext?.let { SimpleDictManager.ensureRegistered(it, db) }\n"

patch(
    "app/src/main/java/me/rerere/rikkahub/data/db/fts/MessageFtsManager.kt",
    [
        (
            "class MessageFtsManager(private val database: AppDatabase) {\n",
            "class MessageFtsManager(\n"
            "    private val database: AppDatabase,\n"
            "    private val appContext: android.content.Context? = null,\n"
            ") {\n",
        ),
        (
            "    suspend fun dropAndRecreate() = withContext(Dispatchers.IO) {\n"
            "        db.execSQL(\"DROP TABLE IF EXISTS message_fts\")\n",
            "    suspend fun dropAndRecreate() = withContext(Dispatchers.IO) {\n"
            + LAZY +
            "        db.execSQL(\"DROP TABLE IF EXISTS message_fts\")\n",
        ),
        (
            "    suspend fun indexConversation(conversation: Conversation) = withContext(Dispatchers.IO) {\n"
            "        val conversationId = conversation.id.toString()\n",
            "    suspend fun indexConversation(conversation: Conversation) = withContext(Dispatchers.IO) {\n"
            + LAZY +
            "        val conversationId = conversation.id.toString()\n",
        ),
        (
            "    ): List<MessageSearchResult> = withContext(Dispatchers.IO) {\n"
            "        val results = mutableListOf<MessageSearchResult>()\n",
            "    ): List<MessageSearchResult> = withContext(Dispatchers.IO) {\n"
            + LAZY +
            "        val results = mutableListOf<MessageSearchResult>()\n",
        ),
    ],
)

print("batch19: jieba dict async prewarm + lazy fallback")

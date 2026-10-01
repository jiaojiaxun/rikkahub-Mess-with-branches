package me.rerere.rikkahub.data.sync.webdav

import android.database.sqlite.SQLiteDatabase
import android.util.Log
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import java.io.File
import java.util.UUID

/**
 * "Pure official" export: removes everything RikkaHub 2.4.14 does not know from an
 * official-compatible backup.
 *
 * The type / key lists below are copied from the official 2.4.14 sources
 * (schemas/24.json, PreferencesStore.kt, UIMessagePart.kt, Model.kt, LocalToolOption.kt,
 * SearchService.kt, TTSProviderSetting.kt, ASRProviderSetting.kt, McpConfig.kt,
 * Reasoning.kt). Unknown keys deeper inside known objects are left in place: the official
 * JSON config uses ignoreUnknownKeys, so they cannot break decoding. Unknown polymorphic
 * type names and enum values would, so those are removed or replaced.
 */
internal object OfficialPurifier {
    private const val TAG = "OfficialPurifier"
    private const val OFFICIAL_IDENTITY_HASH = "0ea1aaebfa031c7995c45a1e35822e1a"
    private val json = Json { ignoreUnknownKeys = true }

    // ------------------------------------------------------------------ database

    private class Col(
        val name: String,
        val integer: Boolean,
        val notNull: Boolean,
        val default: String? = null,
        /** SQL expression always written instead of the source value. */
        val force: String? = null,
    )

    private class Table(
        val name: String,
        /** Official CREATE TABLE; `%T%` is the table name. */
        val createSql: String,
        val columns: List<Col>,
        val indices: List<String> = emptyList(),
        val uniqueKeys: List<List<String>> = emptyList(),
    )

    private fun t(name: String, default: String? = null, force: String? = null) =
        Col(name, integer = false, notNull = true, default = default, force = force)

    private fun i(name: String, default: String? = null) =
        Col(name, integer = true, notNull = true, default = default)

    // Parent tables first (message_node references ConversationEntity).
    private val TABLES = listOf(
        Table(
            "ConversationEntity",
            "CREATE TABLE IF NOT EXISTS `%T%` (`id` TEXT NOT NULL, `assistant_id` TEXT NOT NULL DEFAULT '0950e2dc-9bd5-4801-afa3-aa887aa36b4e', `title` TEXT NOT NULL, `nodes` TEXT NOT NULL, `create_at` INTEGER NOT NULL, `update_at` INTEGER NOT NULL, `suggestions` TEXT NOT NULL DEFAULT '[]', `is_pinned` INTEGER NOT NULL DEFAULT 0, `custom_system_prompt` TEXT NOT NULL DEFAULT '', `mode_injection_ids` TEXT NOT NULL DEFAULT '[]', `lorebook_ids` TEXT NOT NULL DEFAULT '[]', `workspace_cwd` TEXT NOT NULL DEFAULT '', `folder_id` TEXT NOT NULL DEFAULT '', PRIMARY KEY(`id`))",
            listOf(
                t("id"), t("assistant_id", "'0950e2dc-9bd5-4801-afa3-aa887aa36b4e'"), t("title", "''"),
                // v24 keeps the message graph only in message_node.
                t("nodes", force = "'[]'"),
                i("create_at"), i("update_at"), t("suggestions", "'[]'"), i("is_pinned", "0"),
                t("custom_system_prompt", "''"), t("mode_injection_ids", "'[]'"), t("lorebook_ids", "'[]'"),
                t("workspace_cwd", "''"), t("folder_id", "''"),
            ),
        ),
        Table(
            "MemoryEntity",
            "CREATE TABLE IF NOT EXISTS `%T%` (`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, `assistant_id` TEXT NOT NULL, `content` TEXT NOT NULL)",
            listOf(i("id"), t("assistant_id", "''"), t("content", "''")),
        ),
        Table(
            "GenMediaEntity",
            "CREATE TABLE IF NOT EXISTS `%T%` (`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, `path` TEXT NOT NULL, `model_id` TEXT NOT NULL, `prompt` TEXT NOT NULL, `create_at` INTEGER NOT NULL, `type` TEXT NOT NULL DEFAULT 'image_generation', `source_paths` TEXT)",
            listOf(
                i("id"), t("path", "''"), t("model_id", "''"), t("prompt", "''"), i("create_at", "0"),
                t("type", "'image_generation'"), Col("source_paths", integer = false, notNull = false),
            ),
        ),
        Table(
            "message_node",
            "CREATE TABLE IF NOT EXISTS `%T%` (`id` TEXT NOT NULL, `conversation_id` TEXT NOT NULL, `node_index` INTEGER NOT NULL, `messages` TEXT NOT NULL, `select_index` INTEGER NOT NULL, PRIMARY KEY(`id`), FOREIGN KEY(`conversation_id`) REFERENCES `ConversationEntity`(`id`) ON UPDATE NO ACTION ON DELETE CASCADE )",
            listOf(t("id"), t("conversation_id"), i("node_index", "0"), t("messages", "'[]'"), i("select_index", "0")),
            indices = listOf("CREATE INDEX IF NOT EXISTS `index_message_node_conversation_id` ON `%T%` (`conversation_id`)"),
        ),
        Table(
            "managed_files",
            "CREATE TABLE IF NOT EXISTS `%T%` (`id` INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, `folder` TEXT NOT NULL, `relative_path` TEXT NOT NULL, `display_name` TEXT NOT NULL, `mime_type` TEXT NOT NULL, `size_bytes` INTEGER NOT NULL, `created_at` INTEGER NOT NULL, `updated_at` INTEGER NOT NULL)",
            listOf(
                i("id"), t("folder", "''"), t("relative_path", "''"), t("display_name", "''"),
                t("mime_type", "''"), i("size_bytes", "0"), i("created_at", "0"), i("updated_at", "0"),
            ),
            indices = listOf(
                "CREATE UNIQUE INDEX IF NOT EXISTS `index_managed_files_relative_path` ON `%T%` (`relative_path`)",
                "CREATE INDEX IF NOT EXISTS `index_managed_files_folder` ON `%T%` (`folder`)",
            ),
            uniqueKeys = listOf(listOf("relative_path")),
        ),
        Table(
            "favorites",
            "CREATE TABLE IF NOT EXISTS `%T%` (`id` TEXT NOT NULL, `type` TEXT NOT NULL, `ref_key` TEXT NOT NULL, `ref_json` TEXT NOT NULL, `snapshot_json` TEXT NOT NULL, `meta_json` TEXT, `created_at` INTEGER NOT NULL, `updated_at` INTEGER NOT NULL, PRIMARY KEY(`id`))",
            listOf(
                t("id"), t("type", "''"), t("ref_key", "''"), t("ref_json", "'{}'"), t("snapshot_json", "'{}'"),
                Col("meta_json", integer = false, notNull = false), i("created_at", "0"), i("updated_at", "0"),
            ),
            indices = listOf(
                "CREATE UNIQUE INDEX IF NOT EXISTS `index_favorites_ref_key` ON `%T%` (`ref_key`)",
                "CREATE INDEX IF NOT EXISTS `index_favorites_type` ON `%T%` (`type`)",
                "CREATE INDEX IF NOT EXISTS `index_favorites_created_at` ON `%T%` (`created_at`)",
            ),
            uniqueKeys = listOf(listOf("ref_key")),
        ),
        Table(
            "workspaces",
            "CREATE TABLE IF NOT EXISTS `%T%` (`id` TEXT NOT NULL, `name` TEXT NOT NULL, `root` TEXT NOT NULL, `shell_status` TEXT NOT NULL, `created_at` INTEGER NOT NULL, `updated_at` INTEGER NOT NULL, `last_access_at` INTEGER, `tool_approvals` TEXT NOT NULL DEFAULT '{}', PRIMARY KEY(`id`))",
            listOf(
                t("id"), t("name", "''"), t("root", "''"), t("shell_status", "''"), i("created_at", "0"),
                i("updated_at", "0"), Col("last_access_at", integer = true, notNull = false), t("tool_approvals", "'{}'"),
            ),
            indices = listOf(
                "CREATE UNIQUE INDEX IF NOT EXISTS `index_workspaces_root` ON `%T%` (`root`)",
                "CREATE INDEX IF NOT EXISTS `index_workspaces_updated_at` ON `%T%` (`updated_at`)",
            ),
            uniqueKeys = listOf(listOf("root")),
        ),
        Table(
            "conversation_folder",
            "CREATE TABLE IF NOT EXISTS `%T%` (`id` TEXT NOT NULL, `assistant_id` TEXT NOT NULL, `name` TEXT NOT NULL, `sort_index` INTEGER NOT NULL DEFAULT 0, `create_at` INTEGER NOT NULL, PRIMARY KEY(`id`))",
            listOf(t("id"), t("assistant_id", "''"), t("name", "''"), i("sort_index", "0"), i("create_at", "0")),
            indices = listOf("CREATE INDEX IF NOT EXISTS `index_conversation_folder_assistant_id` ON `%T%` (`assistant_id`)"),
        ),
    )

    /** Rewrites [file] (an official-compatible v24 snapshot) to exactly the official schema. */
    fun purifyDatabase(file: File) {
        SQLiteDatabase.openDatabase(file.absolutePath, null, SQLiteDatabase.OPEN_READWRITE).use { db ->
            db.execSQL("PRAGMA foreign_keys=OFF")
            db.beginTransaction()
            try {
                dropUnknownObjects(db)
                TABLES.forEach { rebuild(db, it) }
                db.execSQL(
                    "DELETE FROM `message_node` WHERE `conversation_id` NOT IN (SELECT `id` FROM `ConversationEntity`)"
                )
                sanitizeMessageRows(db)
                db.execSQL("CREATE TABLE IF NOT EXISTS room_master_table (id INTEGER PRIMARY KEY,identity_hash TEXT)")
                db.execSQL(
                    "INSERT OR REPLACE INTO room_master_table (id,identity_hash) VALUES(42, '$OFFICIAL_IDENTITY_HASH')"
                )
                db.version = 24
                db.setTransactionSuccessful()
            } finally {
                db.endTransaction()
            }
            runCatching { db.execSQL("VACUUM") }.onFailure { Log.w(TAG, "VACUUM after purify failed", it) }
        }
    }

    private fun dropUnknownObjects(db: SQLiteDatabase) {
        val keep = TABLES.map { it.name }.toSet() + setOf("room_master_table", "android_metadata", "sqlite_sequence")
        val virtualTables = mutableSetOf<String>()
        val tables = mutableListOf<String>()
        db.rawQuery("SELECT name, sql FROM sqlite_master WHERE type = 'table'", null).use { c ->
            while (c.moveToNext()) {
                val name = c.getString(0)
                if (c.getString(1).orEmpty().trimStart().startsWith("CREATE VIRTUAL", ignoreCase = true)) {
                    virtualTables += name
                }
                tables += name
            }
        }
        fun isVirtualOrShadow(name: String) = virtualTables.any { name == it || name.startsWith(it + "_") }
        tables
            .filter { it !in keep && !it.startsWith("sqlite_") && !isVirtualOrShadow(it) }
            .forEach { name ->
                Log.i(TAG, "drop non-official table $name")
                db.execSQL("DROP TABLE IF EXISTS `$name`")
            }
        // Fork-only virtual tables: dropping needs their module, which may not be loaded here.
        // The official app never reads them. message_fts is official (recreated on open).
        virtualTables.filter { it != "message_fts" }.forEach { name ->
            runCatching { db.execSQL("DROP TABLE IF EXISTS `$name`") }
                .onFailure { Log.w(TAG, "cannot drop virtual table $name, left in place", it) }
        }
        // The official v24 schema has no views or triggers.
        val extras = mutableListOf<Pair<String, String>>()
        db.rawQuery("SELECT type, name FROM sqlite_master WHERE type IN ('view', 'trigger')", null).use { c ->
            while (c.moveToNext()) extras += c.getString(0) to c.getString(1)
        }
        extras.forEach { (type, name) ->
            runCatching { db.execSQL("DROP ${type.uppercase()} IF EXISTS `$name`") }
                .onFailure { Log.w(TAG, "cannot drop $type $name", it) }
        }
    }

    private fun columnsOf(db: SQLiteDatabase, table: String): Set<String> =
        db.rawQuery("PRAGMA table_info(`$table`)", null).use { c ->
            val idx = c.getColumnIndex("name")
            buildSet { while (idx >= 0 && c.moveToNext()) add(c.getString(idx)) }
        }

    private fun rebuild(db: SQLiteDatabase, table: Table) {
        val tmp = "${table.name}__pure"
        db.execSQL("DROP TABLE IF EXISTS `$tmp`")
        db.execSQL(table.createSql.replace("%T%", tmp))
        val existing = columnsOf(db, table.name)
        if (existing.isNotEmpty()) {
            val targets = mutableListOf<String>()
            val values = mutableListOf<String>()
            table.columns.forEach { col ->
                val zero = col.default ?: if (col.integer) "0" else "''"
                when {
                    col.force != null -> {
                        targets += "`${col.name}`"; values += col.force
                    }
                    col.name in existing -> {
                        targets += "`${col.name}`"
                        values += if (col.notNull) "COALESCE(`${col.name}`, $zero)" else "`${col.name}`"
                    }
                    col.notNull && col.default == null -> {
                        targets += "`${col.name}`"; values += zero
                    }
                    // Missing column with an official default or nullable: the default applies.
                }
            }
            db.execSQL(
                "INSERT OR IGNORE INTO `$tmp` (${targets.joinToString()}) " +
                    "SELECT ${values.joinToString()} FROM `${table.name}`"
            )
            db.execSQL("DROP TABLE `${table.name}`")
        }
        db.execSQL("ALTER TABLE `$tmp` RENAME TO `${table.name}`")
        table.uniqueKeys.forEach { key ->
            val cols = key.joinToString { "`$it`" }
            db.execSQL(
                "DELETE FROM `${table.name}` WHERE rowid NOT IN " +
                    "(SELECT MIN(rowid) FROM `${table.name}` GROUP BY $cols)"
            )
        }
        table.indices.forEach { db.execSQL(it.replace("%T%", table.name)) }
    }

    private fun sanitizeMessageRows(db: SQLiteDatabase) {
        val updates = mutableListOf<Pair<String, String>>()
        db.rawQuery("SELECT `id`, `messages` FROM `message_node`", null).use { c ->
            while (c.moveToNext()) {
                val raw = c.getString(1) ?: continue
                val clean = sanitizeMessagesJson(raw)
                if (clean != raw) updates += c.getString(0) to clean
            }
        }
        updates.forEach { (id, messages) ->
            db.execSQL("UPDATE `message_node` SET `messages` = ? WHERE `id` = ?", arrayOf(messages, id))
        }
        Log.i(TAG, "sanitized ${updates.size} message nodes")
    }

    // ------------------------------------------------------------------ messages

    private val PART_TYPES = setOf(
        "text", "image", "video", "audio", "document", "reasoning", "search",
        "tool_call", "tool_result", "server_tool", "tool",
    )
    private val APPROVAL_TYPES = setOf("auto", "pending", "approved", "denied", "answered")
    private val REASONING_TYPES = setOf("reasoning_text", "summary_text")
    private val SERVER_TOOL_STATUS = setOf("in_progress", "completed", "failed")
    private const val DISPLAY_ONLY_COMPACTION_KEY = "rikkahub_display_only_context_compaction"

    private fun JsonObject.type(): String? = (this["type"] as? JsonPrimitive)?.contentOrNull
    private fun JsonObject.str(key: String): String? = (this[key] as? JsonPrimitive)?.contentOrNull
    private fun JsonArray.objects(): List<JsonObject> = mapNotNull { it as? JsonObject }
    private fun JsonObject.keepKeys(keys: Set<String>) = JsonObject(filterKeys { it in keys })
    private fun strings(values: List<String>) = JsonArray(values.map { JsonPrimitive(it) })

    internal fun sanitizeMessagesJson(raw: String): String {
        val array = runCatching { json.parseToJsonElement(raw) }.getOrNull() as? JsonArray ?: return raw
        return JsonArray(array.map { m -> (m as? JsonObject)?.let(::sanitizeMessage) ?: m }).toString()
    }

    private fun sanitizeMessage(message: JsonObject): JsonObject {
        val parts = message["parts"] as? JsonArray ?: return message
        return JsonObject(message + ("parts" to sanitizeParts(parts)))
    }

    private fun sanitizeParts(parts: JsonArray): JsonArray = JsonArray(
        parts.objects().mapNotNull { part ->
            val type = part.type() ?: return@mapNotNull null
            if (type !in PART_TYPES || isDisplayOnlyCompaction(type, part)) null else sanitizePart(type, part)
        }
    )

    private fun isDisplayOnlyCompaction(type: String, part: JsonObject): Boolean =
        type == "tool" &&
            ((part["metadata"] as? JsonObject)?.get(DISPLAY_ONLY_COMPACTION_KEY) as? JsonPrimitive)
                ?.booleanOrNull == true

    private fun sanitizePart(type: String, part: JsonObject): JsonObject {
        val out = part.toMutableMap()
        when (type) {
            "tool", "tool_call" -> {
                val approval = part["approvalState"] as? JsonObject
                if (approval != null && approval.type() !in APPROVAL_TYPES) {
                    out["approvalState"] = JsonObject(mapOf("type" to JsonPrimitive("auto")))
                }
                (part["output"] as? JsonArray)?.let { out["output"] = sanitizeParts(it) }
            }
            "reasoning" -> part.str("reasoningType")?.let { if (it !in REASONING_TYPES) out.remove("reasoningType") }
            "server_tool" -> part.str("status")?.let {
                if (it !in SERVER_TOOL_STATUS) out["status"] = JsonPrimitive("completed")
            }
        }
        return JsonObject(out)
    }

    // ------------------------------------------------------------------ settings

    private val SETTINGS_KEYS = setOf(
        "dynamicColor", "themeId", "customThemes", "developerMode", "displaySetting", "networkSetting",
        "favoriteModels", "chatModelId", "fastModelId", "titleModelId", "imageGenerationModelId",
        "titlePrompt", "translateModeId", "translatePrompt", "translateThinkingBudget", "enableSuggestion",
        "suggestionModelId", "suggestionPrompt", "ocrModelId", "ocrPrompt", "compressModelId",
        "compressPrompt", "assistantId", "providers", "assistants", "assistantTags", "searchServices",
        "searchCommonOptions", "searchServiceSelected", "mcpServers", "webDavConfig", "s3Config",
        "ttsProviders", "selectedTTSProviderId", "defaultTTSPlaybackSpeed", "asrProviders",
        "selectedASRProviderId", "modeInjections", "lorebooks", "quickMessages", "webServerEnabled",
        "webServerPort", "webServerJwtEnabled", "webServerAccessPassword", "webServerLocalhostOnly",
        "backupReminderConfig", "launchCount", "sponsorAlertDismissedAt",
    )
    private val DISPLAY_KEYS = setOf(
        "userAvatar", "userNickname", "useAppIconStyleLoadingIndicator", "showUserAvatar",
        "showAssistantBubble", "bubbleOpacity", "showModelIcon", "showModelName", "showDateTimeInMessage",
        "showTokenUsage", "showThinkingContent", "autoCloseThinking", "updateCheckDisabledUntilEpochMillis",
        "showMessageJumper", "messageJumperOnLeft", "fontSizeRatio", "enableMessageGenerationHapticEffect",
        "skipCropImage", "enableNotificationOnMessageGeneration", "enableLiveUpdateNotification",
        "codeBlockAutoWrap", "codeBlockAutoCollapse", "showLineNumbers", "ttsOnlyReadQuoted",
        "ttsOnlyReadOutsideBrackets", "autoPlayTTSAfterGeneration", "pasteLongTextAsFile",
        "pasteLongTextThreshold", "sendOnEnter", "enableAutoScroll", "enableLatexRendering",
        "enableBlurEffect", "chatFontFamily", "chatCustomFontPath", "chatCustomFontName",
        "enableVolumeKeyScroll", "volumeKeyScrollRatio",
    )
    private val NETWORK_KEYS = setOf("userAgent", "proxyUrl", "proxyUsername", "proxyPassword")
    private val WEBDAV_KEYS = setOf("url", "username", "password", "path", "items")
    private val REMINDER_KEYS = setOf("enabled", "intervalDays", "lastBackupTime")
    private val FONT_FAMILIES = setOf("default", "serif", "monospace", "custom")

    private val PROVIDER_TYPES = setOf("openai", "google", "claude")
    private val MODEL_TYPES = setOf("CHAT", "IMAGE", "EMBEDDING")
    private val MODALITIES = setOf("TEXT", "IMAGE")
    private val ABILITIES = setOf("TOOL", "REASONING")
    private val BUILTIN_TOOLS = setOf("search", "url_context", "image_generation")
    private val LOCAL_TOOLS = setOf(
        "javascript_engine", "time_info", "clipboard", "tts", "ask_user", "screen_time", "calendar",
    )
    private val REASONING_LEVELS = setOf("off", "auto", "low", "medium", "high", "xhigh", "max")
    private val REGEX_SCOPES = setOf("USER", "ASSISTANT")
    private val SEARCH_TYPES = setOf(
        "bing_local", "zhipu", "doubao", "tavily", "exa", "searxng", "linkup", "brave", "metaso",
        "ollama", "perplexity", "firecrawl", "jina", "bocha", "rikkahub", "grok", "tinyfish", "serper",
        "custom_js",
    )
    private val TTS_TYPES = setOf(
        "openai", "gemini", "system", "minimax", "qwen", "groq", "xai", "mimo", "elevenlabs", "step",
        "fish-audio",
    )
    private val ASR_TYPES = setOf("openai_realtime", "dashscope", "volcengine", "mimo", "step")
    private val MCP_TYPES = setOf("sse", "streamable_http")
    private val BACKUP_ITEMS = setOf("DATABASE", "FILES")

    /** Returns official-only settings JSON; on a parse failure the input is returned as is. */
    fun purifySettings(text: String): String {
        val root = runCatching { json.parseToJsonElement(text) }.getOrNull() as? JsonObject ?: return text
        val out = linkedMapOf<String, JsonElement>()
        root.forEach { (key, value) -> if (key in SETTINGS_KEYS) out[key] = value }

        (out["providers"] as? JsonArray)?.let { list ->
            out["providers"] = JsonArray(list.objects().filter { it.type() in PROVIDER_TYPES }.map(::sanitizeProvider))
        }
        (out["assistants"] as? JsonArray)?.let { list ->
            out["assistants"] = JsonArray(list.objects().map(::sanitizeAssistant))
        }
        (out["searchServices"] as? JsonArray)?.let { list ->
            val original = list.objects()
            val selectedIndex = (out["searchServiceSelected"] as? JsonPrimitive)?.intOrNull ?: 0
            val selectedId = original.getOrNull(selectedIndex)?.str("id")
            var kept = original.filter { it.type() in SEARCH_TYPES }
            if (kept.isEmpty()) {
                kept = listOf(
                    JsonObject(
                        mapOf(
                            "type" to JsonPrimitive("bing_local"),
                            "id" to JsonPrimitive(UUID.randomUUID().toString()),
                        )
                    )
                )
            }
            out["searchServices"] = JsonArray(kept)
            out["searchServiceSelected"] =
                JsonPrimitive(kept.indexOfFirst { it.str("id") == selectedId }.coerceAtLeast(0))
        }
        filterTyped(out, "ttsProviders", TTS_TYPES, selectedKey = "selectedTTSProviderId")
        filterTyped(out, "asrProviders", ASR_TYPES, selectedKey = "selectedASRProviderId")
        filterTyped(out, "mcpServers", MCP_TYPES)

        (out["displaySetting"] as? JsonObject)?.let { display ->
            val kept = display.keepKeys(DISPLAY_KEYS).toMutableMap()
            kept.str("chatFontFamily")?.let { if (it !in FONT_FAMILIES) kept.remove("chatFontFamily") }
            out["displaySetting"] = JsonObject(kept)
        }
        (out["networkSetting"] as? JsonObject)?.let { out["networkSetting"] = it.keepKeys(NETWORK_KEYS) }
        (out["backupReminderConfig"] as? JsonObject)?.let { out["backupReminderConfig"] = it.keepKeys(REMINDER_KEYS) }
        (out["webDavConfig"] as? JsonObject)?.let { webdav ->
            val kept = webdav.keepKeys(WEBDAV_KEYS).toMutableMap()
            (kept["items"] as? JsonArray)?.let { items ->
                kept["items"] = strings(items.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }.filter { it in BACKUP_ITEMS })
            }
            out["webDavConfig"] = JsonObject(kept)
        }
        return JsonObject(out).toString()
    }

    private fun Map<String, JsonElement>.str(key: String): String? = (this[key] as? JsonPrimitive)?.contentOrNull

    private fun filterTyped(
        out: MutableMap<String, JsonElement>,
        key: String,
        types: Set<String>,
        selectedKey: String? = null,
    ) {
        val list = out[key] as? JsonArray ?: return
        val kept = list.objects().filter { it.type() in types }
        out[key] = JsonArray(kept)
        if (selectedKey != null) {
            val selected = out.str(selectedKey)
            if (selected != null && kept.none { it.str("id") == selected }) out.remove(selectedKey)
        }
    }

    private fun sanitizeProvider(provider: JsonObject): JsonObject {
        val models = provider["models"] as? JsonArray ?: return provider
        return JsonObject(provider + ("models" to JsonArray(models.objects().map(::sanitizeModel))))
    }

    private fun sanitizeModel(model: JsonObject): JsonObject {
        val out = model.toMutableMap()
        model.str("type")?.let { if (it !in MODEL_TYPES) out["type"] = JsonPrimitive("CHAT") }
        fun enumList(key: String, allowed: Set<String>, fallback: List<String>?) {
            val array = model[key] as? JsonArray ?: return
            val kept = array.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }.filter { it in allowed }
            out[key] = strings(if (kept.isEmpty() && fallback != null) fallback else kept)
        }
        enumList("inputModalities", MODALITIES, listOf("TEXT"))
        enumList("outputModalities", MODALITIES, listOf("TEXT"))
        enumList("abilities", ABILITIES, null)
        (model["tools"] as? JsonArray)?.let { tools ->
            out["tools"] = JsonArray(tools.objects().filter { it.type() in BUILTIN_TOOLS })
        }
        (model["providerOverwrite"] as? JsonObject)?.let { overwrite ->
            if (overwrite.type() in PROVIDER_TYPES) {
                out["providerOverwrite"] = sanitizeProvider(overwrite)
            } else {
                out.remove("providerOverwrite")
            }
        }
        return JsonObject(out)
    }

    private fun sanitizeAssistant(assistant: JsonObject): JsonObject {
        val out = assistant.toMutableMap()
        (assistant["localTools"] as? JsonArray)?.let { tools ->
            out["localTools"] = JsonArray(tools.objects().filter { it.type() in LOCAL_TOOLS })
        }
        assistant.str("reasoningLevel")?.let { if (it !in REASONING_LEVELS) out["reasoningLevel"] = JsonPrimitive("auto") }
        (assistant["presetMessages"] as? JsonArray)?.let { messages ->
            out["presetMessages"] = JsonArray(messages.map { m -> (m as? JsonObject)?.let(::sanitizeMessage) ?: m })
        }
        (assistant["regexes"] as? JsonArray)?.let { regexes ->
            out["regexes"] = JsonArray(
                regexes.objects().map { regex ->
                    val scope = regex["affectingScope"] as? JsonArray ?: return@map regex
                    val kept = scope.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }.filter { it in REGEX_SCOPES }
                    JsonObject(regex + ("affectingScope" to strings(kept)))
                }
            )
        }
        return JsonObject(out)
    }
}

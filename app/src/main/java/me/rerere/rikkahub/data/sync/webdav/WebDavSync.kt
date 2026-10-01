package me.rerere.rikkahub.data.sync.webdav

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.util.Log
import androidx.sqlite.db.SupportSQLiteDatabase
import io.ktor.client.HttpClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import me.rerere.rikkahub.data.datastore.SettingsStore
import me.rerere.rikkahub.data.datastore.WebDavConfig
import me.rerere.rikkahub.data.files.FileFolders
import me.rerere.rikkahub.data.sync.AGENT_FULL_DB_ENTRY
import me.rerere.rikkahub.data.sync.AGENT_FULL_PREFIX
import me.rerere.rikkahub.data.sync.AGENT_FULL_SETTINGS_ENTRY
import me.rerere.rikkahub.data.sync.BackupExportFormat
import me.rerere.rikkahub.data.sync.BackupProgress
import me.rerere.rikkahub.data.sync.BackupRestoreMode
import me.rerere.rikkahub.data.sync.fileName
import me.rerere.rikkahub.data.sync.isBackupArchiveName
import me.rerere.rikkahub.utils.fileSizeToString
import me.rerere.workspace.WorkspaceManager
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.time.Instant
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

private const val TAG = "WebDavSync"
private const val COPY_BUFFER_SIZE = 16 * 1024

class WebDavSync(
    private val settingsStore: SettingsStore,
    private val json: Json,
    private val context: Context,
    private val httpClient: HttpClient,
    private val appDatabase: me.rerere.rikkahub.data.db.AppDatabase,
    private val workspaceManager: WorkspaceManager,
) {
    private fun getClient(config: WebDavConfig): WebDavClient = WebDavClient(config, httpClient)

    suspend fun testConnection(config: WebDavConfig) = withContext(Dispatchers.IO) {
        getClient(config).propfind(depth = 0).getOrThrow()
        Log.i(TAG, "testConnection: Connection successful")
    }

    suspend fun backup(
        config: WebDavConfig,
        onProgress: (BackupProgress) -> Unit = {},
    ) = withContext(Dispatchers.IO) {
        onProgress(BackupProgress("准备备份", detail = "读取本地设置和文件"))
        val file = prepareBackupFile(config, onProgress)
        try {
            val client = getClient(config)
            onProgress(BackupProgress("连接 WebDAV", detail = "确认远端目录"))
            client.ensureCollectionExists().getOrThrow()
            onProgress(
                BackupProgress(
                    "上传备份",
                    total = file.length(),
                    detail = file.name,
                    totalLabel = "实际 ZIP 文件",
                )
            )
            client.put(
                path = file.name,
                file = file,
                contentType = "application/zip",
                onProgress = { completed, total ->
                    onProgress(
                        BackupProgress(
                            phase = "上传备份",
                            completed = completed,
                            total = total.takeIf { it > 0L } ?: file.length(),
                            detail = "已上传 ${completed.fileSizeToString()}",
                            totalLabel = "实际 ZIP 文件",
                        )
                    )
                },
            ).getOrThrow()
            onProgress(
                BackupProgress(
                    "校验远端备份",
                    file.length(),
                    file.length(),
                    "确认 ${file.name} 已在云端可见",
                    "实际 ZIP 文件",
                )
            )
            client.verifyUploaded(file.name, file.length()).getOrThrow()
            onProgress(
                BackupProgress(
                    "备份完成",
                    file.length(),
                    file.length(),
                    "${file.name}，已确认云端存在，实际大小 ${file.length().fileSizeToString()}",
                    "实际 ZIP 文件",
                )
            )
        } finally {
            file.delete()
        }
    }

    suspend fun listBackupFiles(config: WebDavConfig): List<WebDavBackupItem> = withContext(Dispatchers.IO) {
        val client = getClient(config)
        client.ensureCollectionExists().getOrThrow()
        client.list().getOrThrow()
            .filter { !it.isCollection && isBackupArchiveName(it.displayName) }
            .map { resource ->
                WebDavBackupItem(
                    href = resource.href,
                    displayName = resource.displayName,
                    size = resource.contentLength,
                    lastModified = resource.lastModified ?: Instant.EPOCH,
                )
            }
            .sortedByDescending { it.lastModified }
    }

    suspend fun restore(
        config: WebDavConfig,
        item: WebDavBackupItem,
        mode: BackupRestoreMode = BackupRestoreMode.OVERWRITE,
        onProgress: (BackupProgress) -> Unit = {},
    ) = withContext(Dispatchers.IO) {
        val backupFile = resolveCacheFile(item.displayName)
            ?: throw IllegalArgumentException("不安全的备份文件名")
        try {
            val client = getClient(config)
            onProgress(BackupProgress("下载备份", total = item.size, detail = item.displayName))
            client.downloadToFile(item.displayName, backupFile) { completed, total ->
                onProgress(
                    BackupProgress(
                        phase = "下载备份",
                        completed = completed,
                        total = total.takeIf { it > 0L } ?: item.size,
                        detail = "已下载 ${completed.fileSizeToString()}",
                        totalLabel = "实际 ZIP 文件",
                    )
                )
            }.getOrThrow()
            restoreFromBackupFile(backupFile, config, mode, onProgress)
        } finally {
            backupFile.delete()
        }
    }

    suspend fun deleteBackupFile(config: WebDavConfig, item: WebDavBackupItem) = withContext(Dispatchers.IO) {
        getClient(config).delete(item.displayName).getOrThrow()
    }

    suspend fun restoreFromLocalFile(
        file: File,
        config: WebDavConfig,
        mode: BackupRestoreMode = BackupRestoreMode.OVERWRITE,
        onProgress: (BackupProgress) -> Unit = {},
    ) = withContext(Dispatchers.IO) {
        require(file.isFile && file.canRead()) { "备份文件不存在或不可读" }
        restoreFromBackupFile(file, config, mode, onProgress)
    }

    /**
     * Builds a backup ZIP.
     *
     * Both formats carry the RikkaHub 2.4.14-compatible core at the archive root: filtered
     * settings.json, a converted v24 database (rikka_hub.db plus empty sidecars) and top-level
     * uploads / fonts / skills. The official importer copies exactly these entries and skips
     * everything else.
     *
     * [BackupExportFormat.FULL] additionally stores this build's own data under
     * [AGENT_FULL_PREFIX]: a consistent snapshot of the live database, the unfiltered settings,
     * nested uploads, images, tool outputs and workspaces. This app restores those in place of
     * the core, so nothing fork-specific is lost.
     *
     * Database files are never copied raw while Room is open: snapshots come from
     * `VACUUM INTO` (or a WAL checkpoint plus copy), so committed data still in the WAL is
     * included.
     */
    suspend fun prepareBackupFile(
        config: WebDavConfig,
        onProgress: (BackupProgress) -> Unit = {},
        format: BackupExportFormat = BackupExportFormat.FULL,
    ): File = withContext(Dispatchers.IO) {
        val timestamp = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"))
        val backupFile = File(context.cacheDir, format.fileName(timestamp))
        backupFile.delete()
        val full = format == BackupExportFormat.FULL
        val includeDb = config.items.contains(WebDavConfig.BackupItem.DATABASE)
        val includeFiles = config.items.contains(WebDavConfig.BackupItem.FILES)

        val dbRoot = context.getDatabasePath("rikka_hub")
        var officialWarning: String? = null
        var officialDb: File? = null
        var agentDb: File? = null
        try {
            if (includeDb) {
                onProgress(BackupProgress("准备数据库", detail = "生成一致的数据库快照"))
                checkpointDatabase()
                officialDb = if (full) {
                    // The fork's own snapshot is what matters for a FULL backup; a failed
                    // conversion only drops the official-app compatibility of this archive.
                    runCatching { createOfficialDatabaseSnapshot(dbRoot) }
                        .onFailure {
                            Log.w(TAG, "official-compatible snapshot failed; FULL backup continues", it)
                            officialWarning = it.message
                        }
                        .getOrNull()
                } else {
                    createOfficialDatabaseSnapshot(dbRoot)
                }
                if (full) agentDb = createFullDatabaseSnapshot(dbRoot)
            }

            val officialSettings = createOfficialSettingsText().toByteArray()
            val agentSettings = if (full) {
                json.encodeToString(settingsStore.settingsFlow.value).toByteArray()
            } else null
            val dbEntries = buildList {
                officialDb?.let { db ->
                    // Official 2.4.14 restores all three database paths by blindly copying ZIP
                    // entries. The converted database is a standalone DELETE-journal snapshot,
                    // so its sidecars must be present as empty entries: otherwise the official
                    // importer leaves the user's previous WAL/SHM files beside the newly copied
                    // database, and the next Room open can observe the wrong database
                    // generation (or report a malformed database).
                    val wal = File(db.parentFile, "${db.name}-wal").apply { writeBytes(ByteArray(0)) }
                    val shm = File(db.parentFile, "${db.name}-shm").apply { writeBytes(ByteArray(0)) }
                    add(db to "rikka_hub.db")
                    add(wal to "rikka_hub-wal")
                    add(shm to "rikka_hub-shm")
                }
                agentDb?.let { add(it to AGENT_FULL_DB_ENTRY) }
            }
            val fileEntries = if (includeFiles) backupFileEntries(full) else emptyList()
            val totalBytes = (officialSettings.size + (agentSettings?.size ?: 0)).toLong() +
                dbEntries.sumOf { it.first.length() } + fileEntries.sumOf { it.first.length() }

            var completedBytes = 0L
            fun report(phase: String, detail: String) {
                onProgress(
                    BackupProgress(
                        phase = phase,
                        completed = completedBytes,
                        total = totalBytes.coerceAtLeast(1L),
                        detail = detail,
                        totalLabel = "压缩前输入数据",
                    )
                )
            }
            fun onBytes(phase: String, detail: String): (Long) -> Unit = { bytes ->
                completedBytes += bytes
                report(phase, detail)
            }

            ZipOutputStream(FileOutputStream(backupFile)).use { zip ->
                report("写入设置", "settings.json")
                addBytesToZip(zip, "settings.json", officialSettings)
                completedBytes += officialSettings.size
                agentSettings?.let {
                    addBytesToZip(zip, AGENT_FULL_SETTINGS_ENTRY, it)
                    completedBytes += it.size
                }
                report("写入设置", "已写入设置")

                dbEntries.forEach { (file, entry) ->
                    addFileToZip(zip, file, entry, onBytes("备份数据库", entry))
                }
                fileEntries.forEach { (file, entry) ->
                    addFileToZip(zip, file, entry, onBytes("备份文件", entry))
                }
            }

            val summary = (agentDb ?: officialDb)?.let { db ->
                SQLiteDatabase.openDatabase(db.absolutePath, null, SQLiteDatabase.OPEN_READONLY).use {
                    "${countRows(it, "ConversationEntity")} 个对话、${countRows(it, "message_node")} 个消息节点"
                }
            } ?: "未包含数据库"
            val warning = officialWarning?.let { "；官方兼容部分生成失败（$it），此备份只能由本分支恢复" }.orEmpty()
            report(
                "备份文件完成",
                "${backupFile.name}：$summary，${fileEntries.size} 个文件，ZIP ${backupFile.length().fileSizeToString()}$warning",
            )
            Log.i(TAG, "prepareBackupFile: ${backupFile.name} $summary files=${fileEntries.size}$warning")
            backupFile
        } finally {
            officialDb?.let(::deleteOfficialDatabaseSnapshot)
            agentDb?.let(::deleteOfficialDatabaseSnapshot)
        }
    }

    /**
     * Files to archive, as (file, entry name). RikkaHub 2.4.14 restores only top-level files of
     * uploads/ and fonts/ and aborts the whole import on a nested uploads path, so nested files
     * go under [AGENT_FULL_PREFIX] (this app maps them back; the official app skips them).
     */
    private fun backupFileEntries(full: Boolean): List<Pair<File, String>> = buildList {
        listOf(FileFolders.UPLOAD, FileFolders.FONTS).forEach { folder ->
            val root = File(context.filesDir, folder)
            root.walkTopDown().filter(File::isFile).forEach { file ->
                val relative = file.relativeTo(root).invariantSeparatorsPath
                when {
                    !relative.contains('/') -> add(file to "$folder/$relative")
                    full -> add(file to "$AGENT_FULL_PREFIX$folder/$relative")
                }
            }
        }
        val trees = if (full) {
            listOf(FileFolders.SKILLS, FileFolders.IMAGES, FileFolders.TOOL_OUTPUTS, "workspaces")
        } else {
            listOf(FileFolders.SKILLS)
        }
        trees.forEach { folder ->
            val root = File(context.filesDir, folder)
            root.walkTopDown().filter(File::isFile).forEach { file ->
                add(file to "$folder/${file.relativeTo(root).invariantSeparatorsPath}")
            }
        }
    }

    private suspend fun restoreFromBackupFile(
        file: File,
        config: WebDavConfig,
        mode: BackupRestoreMode,
        onProgress: (BackupProgress) -> Unit,
    ) {
        BackupArchiveRestorer(
            context = context,
            json = json,
            settingsStore = settingsStore,
            appDatabase = appDatabase,
            workspaceManager = workspaceManager,
        ).restore(file, config, mode, onProgress)
    }

    private fun checkpointDatabase() {
        runCatching {
            appDatabase.openHelper.writableDatabase.query("PRAGMA wal_checkpoint(TRUNCATE)").use { it.moveToFirst() }
        }.onFailure { Log.w(TAG, "WAL checkpoint failed; copying available database files", it) }
    }

    private fun addBytesToZip(zip: ZipOutputStream, entryName: String, bytes: ByteArray) {
        zip.putNextEntry(ZipEntry(entryName))
        zip.write(bytes)
        zip.closeEntry()
    }

    private fun addFileToZip(
        zip: ZipOutputStream,
        file: File,
        entryName: String,
        onBytes: (Long) -> Unit,
    ) {
        FileInputStream(file).use { input ->
            zip.putNextEntry(ZipEntry(entryName))
            val buffer = ByteArray(COPY_BUFFER_SIZE)
            while (true) {
                val read = input.read(buffer)
                if (read <= 0) break
                zip.write(buffer, 0, read)
                onBytes(read.toLong())
            }
            zip.closeEntry()
        }
    }

    /**
     * Standalone copy of the live database in this build's own schema. `VACUUM INTO` reads the
     * live connection's committed view, so data still sitting in the WAL is included; the old
     * raw copy of rikka_hub / -wal / -shm could miss it or capture a torn pair.
     */
    private fun createFullDatabaseSnapshot(source: File): File {
        require(source.isFile) { "数据库文件不存在，无法生成完整备份" }
        val snapshot = File(context.cacheDir, "agent_db_${System.nanoTime()}.db")
        val liveDb = appDatabase.openHelper.writableDatabase
        try {
            val escapedPath = snapshot.absolutePath.replace("'", "''")
            runCatching {
                liveDb.execSQL("VACUUM INTO '$escapedPath'")
            }.onFailure { error ->
                Log.w(TAG, "VACUUM INTO unavailable; using checkpoint + file copy", error)
                snapshot.delete()
                checkpointDatabase()
                source.copyTo(snapshot, overwrite = true)
                copyDatabaseSidecar(source, snapshot, "-wal")
                SQLiteDatabase.openDatabase(
                    snapshot.absolutePath,
                    null,
                    SQLiteDatabase.OPEN_READWRITE,
                ).use { copied ->
                    copied.rawQuery("PRAGMA wal_checkpoint(TRUNCATE)", null).use { it.moveToFirst() }
                }
                File(snapshot.parentFile, snapshot.name + "-wal").delete()
                File(snapshot.parentFile, snapshot.name + "-shm").delete()
            }
            require(snapshot.isFile && snapshot.length() > 0L) { "无法生成完整数据库快照" }
            val liveNodes = countRows(liveDb, "message_node")
            val snapshotNodes = SQLiteDatabase.openDatabase(
                snapshot.absolutePath,
                null,
                SQLiteDatabase.OPEN_READONLY,
            ).use { countRows(it, "message_node") }
            require(liveNodes == 0L || snapshotNodes > 0L) {
                "完整备份快照缺少聊天消息节点: live=$liveNodes snapshot=$snapshotNodes"
            }
            return snapshot
        } catch (error: Throwable) {
            deleteOfficialDatabaseSnapshot(snapshot)
            throw error
        }
    }

    private fun createOfficialSettingsText(): String {
        val current = json.parseToJsonElement(
            json.encodeToString(settingsStore.settingsFlow.value)
        ).jsonObject
        val officialProviderTypes = setOf("openai", "google", "claude")
        val providers = current["providers"]?.let { element ->
            element as? JsonArray
        }?.filter { provider ->
            provider.jsonObject["type"]?.jsonPrimitive?.content in officialProviderTypes
        } ?: emptyList()
        return json.encodeToString(
            buildJsonObject {
                current.forEach { (key, value) ->
                    if (key != "providers") put(key, value)
                }
                put("providers", JsonArray(providers))
            }
        )
    }

    private fun createOfficialDatabaseSnapshot(source: File): File {
        require(source.isFile) { "数据库文件不存在，无法生成官方兼容备份" }
        val snapshot = File(context.cacheDir, "official_db_${System.nanoTime()}.db")
        val liveDb = appDatabase.openHelper.writableDatabase
        try {
            // Room normally keeps committed writes in WAL. Copying only the main file can therefore
            // produce a database that opens successfully but contains zero message_node rows. VACUUM
            // INTO reads the live connection's committed view and emits a standalone database file.
            val escapedPath = snapshot.absolutePath.replace("'", "''")
            runCatching {
                liveDb.execSQL("VACUUM INTO '$escapedPath'")
            }.onFailure { error ->
                Log.w(TAG, "VACUUM INTO unavailable; falling back to a WAL-aware file copy", error)
                snapshot.delete()
                source.copyTo(snapshot, overwrite = true)
                copyDatabaseSidecar(source, snapshot, "-wal")
                copyDatabaseSidecar(source, snapshot, "-shm")
                SQLiteDatabase.openDatabase(
                    snapshot.absolutePath,
                    null,
                    SQLiteDatabase.OPEN_READWRITE,
                ).use { copied ->
                    copied.rawQuery("PRAGMA wal_checkpoint(TRUNCATE)", null).use { it.moveToFirst() }
                }
            }
            require(snapshot.isFile && snapshot.length() > 0L) { "无法生成官方兼容数据库快照" }
            val messageNodeCount = countRows(liveDb, "message_node")
            val memoryCount = countRows(liveDb, "MemoryEntity")
            val favoriteCount = countRows(liveDb, "favorites")
            val snapshotMessageNodeCount = SQLiteDatabase.openDatabase(
                snapshot.absolutePath,
                null,
                SQLiteDatabase.OPEN_READONLY,
            ).use { countRows(it, "message_node") }
            val snapshotMemoryCount = SQLiteDatabase.openDatabase(
                snapshot.absolutePath,
                null,
                SQLiteDatabase.OPEN_READONLY,
            ).use { countRows(it, "MemoryEntity") }
            val snapshotFavoriteCount = SQLiteDatabase.openDatabase(
                snapshot.absolutePath,
                null,
                SQLiteDatabase.OPEN_READONLY,
            ).use { countRows(it, "favorites") }
            require(messageNodeCount == 0L || snapshotMessageNodeCount > 0L) {
                "官方兼容快照缺少聊天消息节点: live=$messageNodeCount snapshot=$snapshotMessageNodeCount"
            }
            require(snapshotMemoryCount == memoryCount) {
                "官方兼容快照丢失记忆: live=$memoryCount snapshot=$snapshotMemoryCount"
            }
            require(snapshotFavoriteCount == favoriteCount) {
                "官方兼容快照丢失收藏: live=$favoriteCount snapshot=$snapshotFavoriteCount"
            }
            Log.i(
                TAG,
                "official snapshot captured conversations=${countRows(liveDb, "ConversationEntity")} " +
                    "messageNodes=$snapshotMessageNodeCount memories=$snapshotMemoryCount favorites=$snapshotFavoriteCount",
            )

            SQLiteDatabase.openDatabase(
                snapshot.absolutePath,
                null,
                SQLiteDatabase.OPEN_READWRITE,
            ).use { db ->
                val messageNodesBeforeConversion = countRows(db, "message_node")
                db.beginTransaction()
                try {
                    db.execSQL("PRAGMA foreign_keys=OFF")
                    // The current fork's compaction table and chat_model_id column are not part of
                    // official RikkaHub 2.4.14's v24 schema.
                    db.execSQL("DROP TABLE IF EXISTS `conversation_compaction`")
                    db.execSQL("DROP TABLE IF EXISTS `ConversationEntity_official`")
                    db.execSQL("""
                        CREATE TABLE `ConversationEntity_official` (
                            `id` TEXT NOT NULL,
                            `assistant_id` TEXT NOT NULL DEFAULT '0950e2dc-9bd5-4801-afa3-aa887aa36b4e',
                            `title` TEXT NOT NULL,
                            `nodes` TEXT NOT NULL,
                            `create_at` INTEGER NOT NULL,
                            `update_at` INTEGER NOT NULL,
                            `suggestions` TEXT NOT NULL DEFAULT '[]',
                            `is_pinned` INTEGER NOT NULL DEFAULT 0,
                            `custom_system_prompt` TEXT NOT NULL DEFAULT '',
                            `mode_injection_ids` TEXT NOT NULL DEFAULT '[]',
                            `lorebook_ids` TEXT NOT NULL DEFAULT '[]',
                            `workspace_cwd` TEXT NOT NULL DEFAULT '',
                            `folder_id` TEXT NOT NULL DEFAULT '',
                            PRIMARY KEY(`id`)
                        )
                    """.trimIndent())
                    copyConversationsToOfficialTable(db)
                    db.execSQL("DROP TABLE `ConversationEntity`")
                    db.execSQL("ALTER TABLE `ConversationEntity_official` RENAME TO `ConversationEntity`")

                    db.execSQL("DROP TABLE IF EXISTS `workspaces_official`")
                    db.execSQL("""
                        CREATE TABLE `workspaces_official` (
                            `id` TEXT NOT NULL,
                            `name` TEXT NOT NULL,
                            `root` TEXT NOT NULL,
                            `shell_status` TEXT NOT NULL,
                            `created_at` INTEGER NOT NULL,
                            `updated_at` INTEGER NOT NULL,
                            `last_access_at` INTEGER,
                            `tool_approvals` TEXT NOT NULL DEFAULT '{}',
                            PRIMARY KEY(`id`)
                        )
                    """.trimIndent())
                    if (tableExists(db, "workspaces")) {
                        val columns = tableColumns(db, "workspaces")
                        val shellExpression = if ("shell_status" in columns) "`shell_status`" else "''"
                        db.execSQL(
                            "INSERT INTO `workspaces_official` " +
                                "(`id`, `name`, `root`, `shell_status`, `created_at`, `updated_at`, `last_access_at`, `tool_approvals`) " +
                                "SELECT `id`, `name`, `root`, $shellExpression, `created_at`, `updated_at`, `last_access_at`, `tool_approvals` " +
                                "FROM `workspaces`"
                        )
                        db.execSQL("DROP TABLE `workspaces`")
                    }
                    db.execSQL("ALTER TABLE `workspaces_official` RENAME TO `workspaces`")
                    db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS `index_workspaces_root` ON `workspaces` (`root`)")
                    db.execSQL("CREATE INDEX IF NOT EXISTS `index_workspaces_updated_at` ON `workspaces` (`updated_at`)")
                    db.execSQL(
                        "CREATE TABLE IF NOT EXISTS room_master_table (id INTEGER PRIMARY KEY, identity_hash TEXT)"
                    )
                    db.execSQL(
                        "INSERT OR REPLACE INTO room_master_table (id, identity_hash) VALUES (42, ?)",
                        arrayOf("0ea1aaebfa031c7995c45a1e35822e1a"),
                    )
                    db.version = 24
                    db.setTransactionSuccessful()
                } finally {
                    db.endTransaction()
                }
                require(countRows(db, "message_node") == messageNodesBeforeConversion) {
                    "官方兼容转换意外改变聊天消息节点数量"
                }
                require(countRows(db, "MemoryEntity") == memoryCount) {
                    "官方兼容转换意外改变记忆数量"
                }
                require(countRows(db, "favorites") == favoriteCount) {
                    "官方兼容转换意外改变收藏数量"
                }
                require(messageNodesBeforeConversion == 0L || hasPopulatedMessageNodes(db)) {
                    "官方兼容转换未保留 message_node 消息节点"
                }
            }
            return snapshot
        } catch (error: Throwable) {
            deleteOfficialDatabaseSnapshot(snapshot)
            throw error
        }
    }

    private fun copyDatabaseSidecar(source: File, snapshot: File, suffix: String) {
        val sidecar = File(source.parentFile, source.name + suffix)
        if (sidecar.isFile) sidecar.copyTo(File(snapshot.parentFile, snapshot.name + suffix), overwrite = true)
    }

    private fun copyConversationsToOfficialTable(db: SQLiteDatabase) {
        db.query(
            "ConversationEntity",
            arrayOf(
                "id", "assistant_id", "title", "nodes", "create_at", "update_at", "suggestions",
                "is_pinned", "custom_system_prompt", "mode_injection_ids", "lorebook_ids",
                "workspace_cwd", "folder_id",
            ),
            null,
            null,
            null,
            null,
            null,
        ).use { conversations ->
            while (conversations.moveToNext()) {
                val id = conversations.getString(0)
                // Official v24 stores the message graph exclusively in message_node;
                // ConversationEntity.nodes is a legacy migration field and must stay empty.
                val nodes = "[]"
                db.execSQL(
                    """
                    INSERT INTO `ConversationEntity_official`
                    (`id`, `assistant_id`, `title`, `nodes`, `create_at`, `update_at`, `suggestions`,
                     `is_pinned`, `custom_system_prompt`, `mode_injection_ids`, `lorebook_ids`,
                     `workspace_cwd`, `folder_id`)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """.trimIndent(),
                    arrayOf(
                        id,
                        conversations.getString(1),
                        conversations.getString(2),
                        nodes,
                        conversations.getLong(4),
                        conversations.getLong(5),
                        conversations.getString(6),
                        conversations.getInt(7),
                        conversations.getString(8),
                        conversations.getString(9),
                        conversations.getString(10),
                        conversations.getString(11),
                        conversations.getString(12),
                    ),
                )
            }
        }
    }

    private fun hasPopulatedMessageNodes(db: SQLiteDatabase): Boolean {
        if (!tableExists(db, "ConversationEntity") || !tableExists(db, "message_node")) return false
        db.rawQuery(
            "SELECT 1 FROM ConversationEntity ce " +
                "WHERE EXISTS (SELECT 1 FROM message_node mn WHERE mn.conversation_id = ce.id) " +
                "AND ce.nodes = '[]' LIMIT 1",
            null,
        ).use { return it.moveToFirst() }
    }

    private fun deleteOfficialDatabaseSnapshot(snapshot: File) {
        snapshot.delete()
        File(snapshot.parentFile, snapshot.name + "-wal").delete()
        File(snapshot.parentFile, snapshot.name + "-shm").delete()
    }

    private fun countRows(db: SupportSQLiteDatabase, table: String): Long {
        if (!tableExists(db, table)) return 0L
        return db.query("SELECT COUNT(*) FROM `$table`").use { cursor ->
            if (cursor.moveToFirst()) cursor.getLong(0) else 0L
        }
    }

    private fun countRows(db: SQLiteDatabase, table: String): Long {
        if (!tableExists(db, table)) return 0L
        return db.rawQuery("SELECT COUNT(*) FROM `$table`", null).use { cursor ->
            if (cursor.moveToFirst()) cursor.getLong(0) else 0L
        }
    }

    private fun tableExists(db: SupportSQLiteDatabase, table: String): Boolean =
        db.query(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
            arrayOf(table),
        ).use { it.moveToFirst() }

    private fun tableExists(db: SQLiteDatabase, table: String): Boolean =
        db.rawQuery(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
            arrayOf(table),
        ).use { it.moveToFirst() }

    private fun tableColumns(db: SQLiteDatabase, table: String): Set<String> =
        db.rawQuery("PRAGMA table_info(`$table`)", null).use { cursor ->
            val nameIndex = cursor.getColumnIndex("name")
            if (nameIndex < 0) emptySet() else buildSet {
                while (cursor.moveToNext()) add(cursor.getString(nameIndex))
            }
        }

    private fun resolveCacheFile(displayName: String): File? {
        val name = File(displayName).name
        if (name.isBlank() || name == "." || name == "..") return null
        val cache = context.cacheDir.canonicalFile
        return File(cache, name).canonicalFile.takeIf { it.parentFile == cache }
    }
}

data class WebDavBackupItem(
    val href: String,
    val displayName: String,
    val size: Long,
    val lastModified: Instant,
)

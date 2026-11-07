package me.rerere.rikkahub.data.sync.webdav

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import me.rerere.rikkahub.data.datastore.Settings
import me.rerere.rikkahub.data.datastore.SettingsStore
import me.rerere.rikkahub.data.datastore.migration.SettingsJsonMigrator
import me.rerere.rikkahub.data.db.AppDatabase
import me.rerere.rikkahub.data.db.ImportedDatabaseReconciler
import me.rerere.rikkahub.data.sync.BackupProgress
import me.rerere.rikkahub.data.sync.BackupRestoreMode
import me.rerere.rikkahub.data.sync.SettingsBackupDecoder
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.jsonObject
import me.rerere.rikkahub.data.sync.merge.BackupMergeScanner
import me.rerere.rikkahub.data.sync.merge.MergeApplyResult
import me.rerere.rikkahub.data.sync.merge.MergeDecisionApplier
import me.rerere.rikkahub.data.sync.merge.MergePlan
import me.rerere.rikkahub.data.sync.merge.SettingsItemCategory
import me.rerere.rikkahub.data.sync.merge.SettingsItemDecision
import me.rerere.rikkahub.data.sync.merge.SettingsItemDiff
import me.rerere.rikkahub.data.sync.merge.SettingsMergeDiff
import me.rerere.rikkahub.utils.JsonInstant
import me.rerere.rikkahub.data.files.FileFolders
import me.rerere.workspace.WorkspaceManager
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption.ATOMIC_MOVE
import java.nio.file.StandardCopyOption.REPLACE_EXISTING
import java.nio.file.AtomicMoveNotSupportedException
import java.util.zip.ZipFile
import java.util.zip.ZipInputStream

/**
 * Restores a RikkaHub archive through a private staging directory. The live Room database is
 * never written while the archive is being decoded. Unknown entries are ignored, known entries
 * are canonicalized, and all extracted paths are confined to the staging directory or filesDir.
 */
class BackupArchiveRestorer(
    private val context: Context,
    private val json: Json,
    private val settingsStore: SettingsStore,
    private val appDatabase: AppDatabase,
    private val workspaceManager: WorkspaceManager,
) {
    suspend fun restore(
        archive: File,
        config: me.rerere.rikkahub.data.datastore.WebDavConfig,
        mode: BackupRestoreMode,
        onProgress: (BackupProgress) -> Unit = {},
    ) = withContext(Dispatchers.IO) {
        require(archive.isFile && archive.canRead()) { "备份文件不存在或不可读" }

        val staging = File(context.cacheDir, "backup-restore-${System.nanoTime()}").apply { mkdirs() }
        val stagedDb = File(staging, "rikka_hub")
        val stagedWal = File(staging, "rikka_hub-wal")
        val stagedShm = File(staging, "rikka_hub-shm")
        // rh-batch4:agent-full
        val stagedAgentDb = File(staging, "agent_rikka_hub.db")
        var agentSettings: Settings? = null
        var importedSettings: Settings? = null
        var processedBytes = 0L
        var totalUncompressedBytes = 0L
        var entryCount = 0
        val declaredTotal = archiveUncompressedSize(archive)
        require(declaredTotal == 0L || declaredTotal <= MAX_TOTAL_UNCOMPRESSED_BYTES) {
            "备份展开后超过允许大小"
        }
        val totalBytes = declaredTotal.takeIf { it > 0L } ?: archive.length().coerceAtLeast(1L)

        fun report(phase: String, detail: String, completed: Long = processedBytes) {
            onProgress(BackupProgress(phase, completed.coerceAtLeast(0L), totalBytes, detail))
        }

        fun consumeEntry(
            input: ZipInputStream,
            maxBytes: Long,
            phase: String,
            detail: String,
            sink: (ByteArray, Int) -> Unit = { _, _ -> },
        ) {
            var entryBytes = 0L
            val buffer = ByteArray(COPY_BUFFER_SIZE)
            while (true) {
                val read = input.read(buffer)
                if (read <= 0) break
                entryBytes += read
                require(entryBytes <= maxBytes) { "ZIP 条目超过允许大小: $detail" }
                totalUncompressedBytes += read
                require(totalUncompressedBytes <= MAX_TOTAL_UNCOMPRESSED_BYTES) {
                    "备份展开后超过允许大小"
                }
                sink(buffer, read)
                processedBytes = totalUncompressedBytes
                report(phase, detail)
            }
        }

        try {
            report("检查备份", archive.name, 0L)
            ZipInputStream(FileInputStream(archive)).use { input ->
                while (true) {
                    val entry = input.nextEntry ?: break
                    entryCount++
                    require(entryCount <= MAX_ENTRY_COUNT) { "备份条目数量超过允许上限" }
                    // FULL-format extras (see BackupExportFormat). They take precedence over the
                    // official-compatible core stored at the root of the same archive.
                    when (entry.name.replace('\\', '/').trim('/')) {
                        me.rerere.rikkahub.data.sync.AGENT_FULL_DB_ENTRY -> {
                            FileOutputStream(stagedAgentDb).use { output ->
                                consumeEntry(input, MAX_ENTRY_BYTES, "准备数据库", entry.name) { bytes, count ->
                                    output.write(bytes, 0, count)
                                }
                            }
                            input.closeEntry()
                            continue
                        }
                        me.rerere.rikkahub.data.sync.AGENT_FULL_SETTINGS_ENTRY -> {
                            val rawAgentSettings = ByteArrayOutputStream()
                            consumeEntry(input, MAX_SETTINGS_BYTES, "读取设置", entry.name) { bytes, count ->
                                rawAgentSettings.write(bytes, 0, count)
                            }
                            agentSettings = SettingsBackupDecoder.decode(
                                json,
                                rawAgentSettings.toByteArray().toString(Charsets.UTF_8),
                            )
                            if (agentSettings == null) {
                                Log.w(TAG, "agent_settings.json 无法解析，回退到包内兼容设置")
                            }
                            input.closeEntry()
                            continue
                        }
                    }
                    val safeName = normalizeEntryName(entry.name)
                    if (safeName == null) {
                        Log.w(TAG, "Skipping unsafe ZIP entry: ${entry.name}")
                        if (!entry.isDirectory) consumeEntry(input, MAX_ENTRY_BYTES, "检查备份", entry.name)
                        input.closeEntry()
                        continue
                    }
                    val target = when {
                        safeName == "settings.json" -> null
                        safeName == "rikka_hub.db" -> stagedDb
                        safeName == "rikka_hub-wal" -> stagedWal
                        safeName == "rikka_hub-shm" -> stagedShm
                        safeName.startsWith("${FileFolders.UPLOAD}/") -> resolveStagedFile(staging, safeName)
                        safeName.startsWith("${FileFolders.SKILLS}/") -> resolveStagedFile(staging, safeName)
                        safeName.startsWith("${FileFolders.FONTS}/") -> resolveStagedFile(staging, safeName)
                        safeName.startsWith("${FileFolders.IMAGES}/") -> resolveStagedFile(staging, safeName)
                        safeName.startsWith("${FileFolders.TOOL_OUTPUTS}/") -> resolveStagedFile(staging, safeName)
                            safeName.startsWith("scripts/") -> resolveStagedFile(staging, safeName) // rhBackupScripts265
                        safeName.startsWith("workspaces/") -> resolveStagedFile(staging, safeName)
                        else -> null
                    }

                    when {
                        entry.isDirectory -> Log.d(TAG, "Skipping directory entry $safeName")
                        safeName == "settings.json" -> {
                            val rawOutput = ByteArrayOutputStream()
                            consumeEntry(input, MAX_SETTINGS_BYTES, "读取设置", "settings.json") { bytes, count ->
                                rawOutput.write(bytes, 0, count)
                            }
                            val raw = rawOutput.toByteArray().toString(Charsets.UTF_8)
                            importedSettings = SettingsBackupDecoder.decode(json, raw)
                            if (importedSettings == null) {
                                Log.w(TAG, "settings.json 无法解析，跳过设置恢复，数据库与文件仍会继续")
                            }
                        }
                        target != null -> {
                            val phase = when {
                                safeName.startsWith("workspaces/") -> "恢复工作区"
                                safeName == "rikka_hub.db" || safeName.startsWith("rikka_hub-") -> "准备数据库"
                                safeName.startsWith("${FileFolders.SKILLS}/") -> "恢复技能"
                                else -> "恢复文件"
                            }
                            target.parentFile?.mkdirs()
                            FileOutputStream(target).use { output ->
                                consumeEntry(input, MAX_ENTRY_BYTES, phase, safeName) { bytes, count ->
                                    output.write(bytes, 0, count)
                                }
                            }
                        }
                        else -> {
                            // Future metadata is intentionally ignored, but still consumed under
                            // the same byte limits so a hidden ZIP bomb cannot bypass validation.
                            Log.i(TAG, "Skipping unknown ZIP entry $safeName")
                            consumeEntry(input, MAX_ENTRY_BYTES, "检查备份", safeName)
                        }
                    }
                    input.closeEntry()
                }
            }

            report("校验备份", "安全解压完成")
            if (stagedAgentDb.isFile) {
                // The FULL snapshot is a standalone database in this build's schema: it replaces
                // the converted core copy, and the core's empty sidecars must not be applied.
                moveReplacing(stagedAgentDb, stagedDb)
                stagedWal.delete()
                stagedShm.delete()
            }
            agentSettings?.let { importedSettings = it }
            if (config.items.contains(me.rerere.rikkahub.data.datastore.WebDavConfig.BackupItem.DATABASE) && stagedDb.isFile) {
                ImportedDatabaseReconciler.reconcileDatabaseFile(stagedDb)
                if (mode == BackupRestoreMode.MERGE) {
                    report("合并数据库", "按对话检查新增与分叉")
                    BackupDatabaseMerger(appDatabase, workspaceManager).merge(stagedDb) { done, total, title ->
                        onProgress(BackupProgress("合并数据库", done, total.coerceAtLeast(1L), title))
                    }
                } else {
                    report("覆盖数据库", "关闭 Room 后原子替换")
                    replaceDatabaseAtomically(stagedDb, stagedWal, stagedShm)
                    repairWorkspaceDirectoriesFromDatabase()
                }
            }

            importedSettings?.let { incoming ->
                report("恢复设置", if (mode == BackupRestoreMode.MERGE) "去重合并供应商、助手与 MCP" else "覆盖当前设置")
                settingsStore.update { current ->
                    if (mode == BackupRestoreMode.MERGE) mergeSettings(current, incoming) else incoming
                }
            }

            if (config.items.contains(me.rerere.rikkahub.data.datastore.WebDavConfig.BackupItem.FILES)) {
                copyStagedFilesToApp(staging, onProgress)
            }
            report("恢复完成", "数据库、设置和文件已处理", totalBytes)
        } finally {
            staging.deleteRecursively()
        }
    }

    private fun copyStagedFilesToApp(
        staging: File,
        onProgress: (BackupProgress) -> Unit,
    ) {
        val roots = listOf(
            FileFolders.UPLOAD,
            FileFolders.SKILLS,
            FileFolders.FONTS,
            FileFolders.IMAGES,
            FileFolders.TOOL_OUTPUTS,
            "workspaces",
        )
        val files = roots.flatMap { rootName ->
            val sourceRoot = File(staging, rootName)
            if (!sourceRoot.isDirectory) emptyList()
            else sourceRoot.walkTopDown().filter { it.isFile }.map { rootName to it }.toList()
        }
        val totalBytes = files.sumOf { it.second.length().coerceAtLeast(0L) }.coerceAtLeast(1L)
        var completedBytes = 0L
        files.forEach { (rootName, source) ->
                val relative = source.relativeTo(File(staging, rootName))
                val target = resolveAppFile(rootName, relative.invariantSeparatorsPath) ?: return@forEach
                target.parentFile?.mkdirs()
                val tmp = File(target.parentFile, ".${target.name}.restore-${System.nanoTime()}")
                FileInputStream(source).use { input ->
                    FileOutputStream(tmp).use { output ->
                        val buffer = ByteArray(COPY_BUFFER_SIZE)
                        while (true) {
                            val read = input.read(buffer)
                            if (read <= 0) break
                            output.write(buffer, 0, read)
                            completedBytes += read
                            onProgress(
                                BackupProgress(
                                    phase = "恢复文件",
                                    completed = completedBytes,
                                    total = totalBytes,
                                    detail = "$rootName/${relative.invariantSeparatorsPath}",
                                )
                            )
                        }
                    }
                }
                moveReplacing(tmp, target)
        }
        onProgress(BackupProgress("恢复文件", totalBytes, totalBytes, "文件恢复完成"))
    }

    private fun replaceDatabaseAtomically(stagedDb: File, stagedWal: File, stagedShm: File) {
                    try {
                appDatabase.close()
            } catch (error: Throwable) {
                throw IllegalStateException("无法关闭数据库连接，已停止覆盖恢复以保护原数据", error)
            }

        val db = context.getDatabasePath("rikka_hub")
        db.parentFile?.mkdirs()
        atomicReplace(stagedDb, db)
        val wal = File(db.parentFile, "rikka_hub-wal")
        val shm = File(db.parentFile, "rikka_hub-shm")
        if (stagedWal.isFile) atomicReplace(stagedWal, wal) else wal.delete()
        if (stagedShm.isFile) atomicReplace(stagedShm, shm) else shm.delete()
        ImportedDatabaseReconciler.reconcile(context)
    }

    private fun repairWorkspaceDirectoriesFromDatabase() {
        val db = context.getDatabasePath("rikka_hub")
        if (!db.isFile) return
        runCatching {
            SQLiteDatabase.openDatabase(db.absolutePath, null, SQLiteDatabase.OPEN_READONLY).use { source ->
                if (!tableExists(source, "workspaces")) return@use
                source.query("workspaces", arrayOf("root"), null, null, null, null, null, null).use { cursor ->
                    while (cursor.moveToNext()) {
                        val root = cursor.getString(0)
                        if (root.matches(ROOT_NAME_REGEX)) workspaceManager.ensureWorkspace(root)
                    }
                }
            }
        }.onFailure { Log.w(TAG, "恢复工作区目录骨架失败", it) }
    }

    private fun mergeSettings(current: Settings, incoming: Settings): Settings {
        val deletedBuiltInProviders = current.deletedBuiltInProviderIds + incoming.deletedBuiltInProviderIds
        val deletedProviders = current.deletedProviderIds + incoming.deletedProviderIds
        val deletedAssistants = current.deletedAssistantIds + incoming.deletedAssistantIds
        val deletedMcpServers = current.deletedMcpServerIds + incoming.deletedMcpServerIds
        val providers = (current.providers + incoming.providers)
            .associateBy { it.id }
            .values
            .filterNot { it.id in deletedProviders || it.id in deletedBuiltInProviders }
            .toList()
        val assistants = (current.assistants + incoming.assistants)
            .associateBy { it.id }
            .values
            .filterNot { it.id in deletedAssistants }
            .toList()
        val mcpServers = (current.mcpServers + incoming.mcpServers)
            .associateBy { it.id }
            .values
            .filterNot { it.id in deletedMcpServers }
            .toList()
        return incoming.copy(
            providers = providers,
            assistants = assistants,
            mcpServers = mcpServers,
            deletedBuiltInProviderIds = deletedBuiltInProviders,
            deletedProviderIds = deletedProviders,
            deletedAssistantIds = deletedAssistants,
            deletedMcpServerIds = deletedMcpServers,
        )
    }

    private fun normalizeEntryName(raw: String): String? {
        val canonical = raw.replace('\\', '/').trim('/')
        if (canonical.isBlank()) return null
        val parts = canonical.split('/').filter { it.isNotBlank() && it != "." }
        if (parts.any { it == ".." || it.contains('\u0000') }) return null

        // Official releases have used a stable filename, while some compatible exporters put the
        // database below a versioned directory or call it database.sqlite. Normalize only known
        // leaf names; every other metadata entry remains ignored.
        if (parts.none { it.lowercase() in setOf("upload", "uploads", "files", "skills", "skill", "fonts", "images", "tool_outputs", "tool-outputs", "workspaces", "workspace", "scripts", "script") }) when (parts.lastOrNull()?.lowercase()) {
            "settings.json" -> return "settings.json"
            "rikka_hub.db", "rikka_hub.sqlite", "rikkahub.db", "database.db", "database.sqlite" ->
                return "rikka_hub.db"
            "rikka_hub-wal", "rikka_hub.sqlite-wal", "database.db-wal" -> return "rikka_hub-wal"
            "rikka_hub-shm", "rikka_hub.sqlite-shm", "database.db-shm" -> return "rikka_hub-shm"
        }

        val rootAliases = mapOf(
            "upload" to FileFolders.UPLOAD,
            "uploads" to FileFolders.UPLOAD,
            "files" to FileFolders.UPLOAD,
            "skills" to FileFolders.SKILLS,
            "skill" to FileFolders.SKILLS,
            "fonts" to FileFolders.FONTS,
            "images" to FileFolders.IMAGES,
            "tool_outputs" to FileFolders.TOOL_OUTPUTS,
            "tool-outputs" to FileFolders.TOOL_OUTPUTS,
            "scripts" to "scripts", // rhBackupScripts265
            "script" to "scripts", // rhBackupScripts265
            "workspaces" to "workspaces",
            "workspace" to "workspaces",
        )
        val rootIndex = parts.indexOfFirst { it.lowercase() in rootAliases }
        if (rootIndex < 0 || rootIndex == parts.lastIndex) return null
        val root = rootAliases[parts[rootIndex].lowercase()] ?: return null
        val relativeParts = parts.drop(rootIndex + 1)
        if (relativeParts.any { it == ".." || it.contains(':') }) return null
        return listOf(root).plus(relativeParts).joinToString("/")
    }

    private fun resolveStagedFile(staging: File, relative: String): File? =
        resolveChild(staging, relative)

    private fun resolveAppFile(root: String, relative: String): File? =
        resolveChild(File(context.filesDir, root), relative)

    private fun resolveChild(root: File, relative: String): File? {
        val base = root.canonicalFile
        val target = File(base, relative).canonicalFile
        return target.takeIf { it == base || it.path.startsWith(base.path + File.separator) }
    }

    private fun atomicReplace(source: File, target: File) {
        target.parentFile?.mkdirs()
        val stagedTarget = File(target.parentFile, ".${target.name}.restore-${System.nanoTime()}")
        try {
            FileInputStream(source).use { input ->
                FileOutputStream(stagedTarget).use { output ->
                    input.copyTo(output, COPY_BUFFER_SIZE)
                    output.fd.sync()
                }
            }
            moveReplacing(stagedTarget, target)
        } finally {
            stagedTarget.delete()
        }
    }

    private fun moveReplacing(source: File, target: File) {
        target.parentFile?.mkdirs()
        try {
            Files.move(source.toPath(), target.toPath(), ATOMIC_MOVE, REPLACE_EXISTING)
        } catch (_: AtomicMoveNotSupportedException) {
            Files.move(source.toPath(), target.toPath(), REPLACE_EXISTING)
        }
    }

    private fun archiveUncompressedSize(archive: File): Long = runCatching {
        ZipFile(archive).use { zip ->
            zip.entries().asSequence().sumOf { it.size.takeIf { size -> size > 0L } ?: 0L }
        }
    }.getOrDefault(0L)

    private fun tableExists(db: SQLiteDatabase, table: String): Boolean =
        db.rawQuery(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND lower(name)=lower(?) LIMIT 1",
            arrayOf(table),
        ).use { it.moveToFirst() }


    // ------------------------------------------------------------ [batch155] 两阶段合并

    /**
     * 阶段一：解压 + 安全校验 + reconcile + 差异扫描，不写任何数据。
     * 返回的 [StagedMergeBackup] 持有 staging 目录；调用方必须在 applyStagedMerge 或
     * discardStagedMerge 中结束其生命周期。
     */
    suspend fun stageForMerge(
        archive: File,
        config: me.rerere.rikkahub.data.datastore.WebDavConfig,
        onProgress: (BackupProgress) -> Unit = {},
    ): Pair<StagedMergeBackup, MergePlan> = withContext(Dispatchers.IO) {
        require(archive.isFile && archive.canRead()) { "备份文件不存在或不可读" }

        val staging = File(context.cacheDir, "backup-merge-${System.nanoTime()}").apply { mkdirs() }
        val stagedDb = File(staging, "rikka_hub")
        val stagedWal = File(staging, "rikka_hub-wal")
        val stagedShm = File(staging, "rikka_hub-shm")
        val stagedAgentDb = File(staging, "agent_rikka_hub.db")
        var importedSettings: Settings? = null
        var agentSettings: Settings? = null
        var processedBytes = 0L
        var totalUncompressedBytes = 0L
        var entryCount = 0
        val declaredTotal = archiveUncompressedSize(archive)
        require(declaredTotal == 0L || declaredTotal <= MAX_TOTAL_UNCOMPRESSED_BYTES) { "备份展开后超过允许大小" }
        val totalBytes = declaredTotal.takeIf { it > 0L } ?: archive.length().coerceAtLeast(1L)

        fun report(phase: String, detail: String, completed: Long = processedBytes) {
            onProgress(BackupProgress(phase, completed.coerceAtLeast(0L), totalBytes, detail))
        }

        fun consumeEntry(
            input: ZipInputStream,
            maxBytes: Long,
            phase: String,
            detail: String,
            sink: (ByteArray, Int) -> Unit = { _, _ -> },
        ) {
            var entryBytes = 0L
            val buffer = ByteArray(COPY_BUFFER_SIZE)
            while (true) {
                val read = input.read(buffer)
                if (read <= 0) break
                entryBytes += read
                require(entryBytes <= maxBytes) { "ZIP 条目超过允许大小: $detail" }
                totalUncompressedBytes += read
                require(totalUncompressedBytes <= MAX_TOTAL_UNCOMPRESSED_BYTES) { "备份展开后超过允许大小" }
                sink(buffer, read)
                processedBytes = totalUncompressedBytes
                report(phase, detail)
            }
        }

        try {
            report("检查备份", archive.name, 0L)
            ZipInputStream(FileInputStream(archive)).use { input ->
                while (true) {
                    val entry = input.nextEntry ?: break
                    entryCount++
                    require(entryCount <= MAX_ENTRY_COUNT) { "备份条目数量超过允许上限" }
                    val safeName = normalizeEntryName(entry.name)
                    if (safeName == null) {
                        Log.w(TAG, "Skipping unsafe ZIP entry: ${entry.name}")
                        if (!entry.isDirectory) consumeEntry(input, MAX_ENTRY_BYTES, "检查备份", entry.name)
                        input.closeEntry()
                        continue
                    }
                    // FULL 格式的 agent 数据优先于根目录的兼容核心（与 restore() 的 batch4 逻辑一致）
                    val rawName = entry.name.replace('\\', '/').trim('/')
                    if (rawName == me.rerere.rikkahub.data.sync.AGENT_FULL_DB_ENTRY) {
                        FileOutputStream(stagedAgentDb).use { output ->
                            consumeEntry(input, MAX_ENTRY_BYTES, "准备数据库", entry.name) { bytes, count ->
                                output.write(bytes, 0, count)
                            }
                        }
                        input.closeEntry()
                        continue
                    }
                    if (rawName == me.rerere.rikkahub.data.sync.AGENT_FULL_SETTINGS_ENTRY) {
                        val rawOutput = ByteArrayOutputStream()
                        consumeEntry(input, MAX_SETTINGS_BYTES, "读取设置", entry.name) { bytes, count ->
                            rawOutput.write(bytes, 0, count)
                        }
                        agentSettings = json.decodeFromString(
                            SettingsJsonMigrator.migrate(rawOutput.toByteArray().toString(Charsets.UTF_8))
                        )
                        input.closeEntry()
                        continue
                    }
                    val target = when {
                        safeName == "settings.json" -> null
                        safeName == "rikka_hub.db" -> stagedDb
                        safeName == "rikka_hub-wal" -> stagedWal
                        safeName == "rikka_hub-shm" -> stagedShm
                        safeName.startsWith("${FileFolders.UPLOAD}/") -> resolveStagedFile(staging, safeName)
                        safeName.startsWith("${FileFolders.SKILLS}/") -> resolveStagedFile(staging, safeName)
                        safeName.startsWith("${FileFolders.FONTS}/") -> resolveStagedFile(staging, safeName)
                        safeName.startsWith("${FileFolders.IMAGES}/") -> resolveStagedFile(staging, safeName)
                        safeName.startsWith("${FileFolders.TOOL_OUTPUTS}/") -> resolveStagedFile(staging, safeName)
                            safeName.startsWith("scripts/") -> resolveStagedFile(staging, safeName) // rhBackupScripts265
                        safeName.startsWith("workspaces/") -> resolveStagedFile(staging, safeName)
                        else -> null
                    }
                    when {
                        entry.isDirectory -> Log.d(TAG, "Skipping directory entry $safeName")
                        safeName == "settings.json" -> {
                            val rawOutput = ByteArrayOutputStream()
                            consumeEntry(input, MAX_SETTINGS_BYTES, "读取设置", "settings.json") { bytes, count ->
                                rawOutput.write(bytes, 0, count)
                            }
                            val raw = rawOutput.toByteArray().toString(Charsets.UTF_8)
                            importedSettings = json.decodeFromString(SettingsJsonMigrator.migrate(raw))
                        }
                        target != null -> {
                            val phase = when {
                                safeName.startsWith("workspaces/") -> "恢复工作区"
                                safeName == "rikka_hub.db" || safeName.startsWith("rikka_hub-") -> "准备数据库"
                                safeName.startsWith("${FileFolders.SKILLS}/") -> "恢复技能"
                                else -> "恢复文件"
                            }
                            target.parentFile?.mkdirs()
                            FileOutputStream(target).use { output ->
                                consumeEntry(input, MAX_ENTRY_BYTES, phase, safeName) { bytes, count ->
                                    output.write(bytes, 0, count)
                                }
                            }
                        }
                        else -> {
                            Log.i(TAG, "Skipping unknown ZIP entry $safeName")
                            consumeEntry(input, MAX_ENTRY_BYTES, "检查备份", safeName)
                        }
                    }
                    input.closeEntry()
                }
            }

            // FULL 快照优先于兼容核心（batch4 逻辑）
            if (stagedAgentDb.isFile) {
                moveReplacing(stagedAgentDb, stagedDb)
                stagedWal.delete()
                stagedShm.delete()
            }
            agentSettings?.let { importedSettings = it }

            val hasDatabase = config.items.contains(
                me.rerere.rikkahub.data.datastore.WebDavConfig.BackupItem.DATABASE
            ) && stagedDb.isFile
            if (hasDatabase) {
                ImportedDatabaseReconciler.reconcileDatabaseFile(stagedDb)
            }

            report("扫描差异", "分析对话与设置差异")
            val scanner = BackupMergeScanner(appDatabase, settingsStore)
            val plan = if (hasDatabase) {
                scanner.scan(stagedDb, importedSettings)
            } else {
                MergePlan(
                    conversations = emptyList(),
                    settings = importedSettings?.let { scanner.diffSettings(it) },
                    memoriesToAdd = 0,
                    favoritesToAdd = 0,
                    workspacesToMerge = 0,
                )
            }
            StagedMergeBackup(staging, stagedDb.takeIf { it.isFile }, importedSettings, config) to plan
        } catch (error: Throwable) {
            staging.deleteRecursively()
            throw error
        }
    }

    /** 阶段二：按用户确认后的 [MergePlan] 应用合并（先设置后对话，兜底依赖合并后的助手集合），结束后清理 staging。 */
    suspend fun applyStagedMerge(
        staged: StagedMergeBackup,
        plan: MergePlan,
        onProgress: (BackupProgress) -> Unit = {},
    ): MergeApplyResult = withContext(Dispatchers.IO) {
        try {
            if (staged.importedSettings != null && plan.settings != null) {
                onProgress(BackupProgress("合并设置", detail = "按确认结果应用供应商、助手与偏好"))
                applyMergeSettings(staged.importedSettings, plan.settings)
            }
            var result = MergeApplyResult()
            if (staged.stagedDb != null && staged.config.items.contains(
                    me.rerere.rikkahub.data.datastore.WebDavConfig.BackupItem.DATABASE
                )
            ) {
                onProgress(BackupProgress("合并数据库", detail = "按确认结果写入对话"))
                val currentSettings = settingsStore.settingsFlow.value
                result = MergeDecisionApplier(appDatabase, workspaceManager).apply(
                    stagedDatabase = staged.stagedDb,
                    plan = plan,
                    validAssistantIds = currentSettings.assistants.map { it.id.toString() }.toSet(),
                    defaultAssistantId = currentSettings.assistantId.toString(),
                    validFolderIds = readFolderIds(),
                    onProgress = { done, total, title ->
                        onProgress(BackupProgress("合并数据库", done, total.coerceAtLeast(1L), title))
                    },
                )
            }
            if (staged.config.items.contains(me.rerere.rikkahub.data.datastore.WebDavConfig.BackupItem.FILES)) {
                copyStagedFilesToApp(staged.stagingDir, onProgress)
            }
            onProgress(BackupProgress("合并完成", detail = result.summary()))
            result
        } finally {
            staged.stagingDir.deleteRecursively()
        }
    }

    /** 放弃合并：清理 staging。 */
    fun discardStagedMerge(staged: StagedMergeBackup) {
        staged.stagingDir.deleteRecursively()
    }

    private fun readFolderIds(): Set<String> = runCatching {
        appDatabase.openHelper.readableDatabase.query("SELECT id FROM conversation_folder").use { cursor ->
            buildSet { while (cursor.moveToNext()) add(cursor.getString(0)) }
        }
    }.getOrDefault(emptySet())

    /** P5 修复：设置按用户决策逐项合并（条目级 + 标量级 + 删除标记重算）。 */
    private suspend fun applyMergeSettings(incoming: Settings, diff: SettingsMergeDiff) {
        settingsStore.update { current ->
            val currentMap = JsonInstant.encodeToJsonElement(current).jsonObject.toMutableMap()
            val incomingJson = JsonInstant.encodeToJsonElement(incoming).jsonObject

            val arrayKeys = mapOf(
                "providers" to SettingsItemCategory.PROVIDER,
                "assistants" to SettingsItemCategory.ASSISTANT,
                "mcpServers" to SettingsItemCategory.MCP_SERVER,
            )
            for ((arrayKey, category) in arrayKeys) {
                currentMap[arrayKey] = mergeItemArray(
                    currentMap[arrayKey],
                    incomingJson[arrayKey],
                    diff.items.filter { it.category == category },
                )
            }
            reconcileDeletedIds(currentMap, incomingJson, "providers", listOf("deletedProviderIds", "deletedBuiltInProviderIds"))
            reconcileDeletedIds(currentMap, incomingJson, "assistants", listOf("deletedAssistantIds"))
            reconcileDeletedIds(currentMap, incomingJson, "mcpServers", listOf("deletedMcpServerIds"))

            diff.scalarFields.filter { it.adoptBackup }.forEach { field ->
                val backupValue = incomingJson[field.fieldKey]
                if (backupValue != null) currentMap[field.fieldKey] = backupValue
            }

            JsonInstant.decodeFromJsonElement(JsonObject(currentMap))
        }
    }

    private fun mergeItemArray(
        currentElement: JsonElement?,
        incomingElement: JsonElement?,
        diffs: List<SettingsItemDiff>,
    ): JsonElement {
        val currentArray = currentElement as? JsonArray ?: JsonArray(emptyList())
        val incomingArray = incomingElement as? JsonArray ?: JsonArray(emptyList())
        val result = LinkedHashMap<String, JsonObject>()
        currentArray.forEach { element ->
            val obj = element as? JsonObject ?: return@forEach
            val id = (obj["id"] as? JsonPrimitive)?.contentOrNull ?: return@forEach
            result[id] = obj
        }
        val backupById = LinkedHashMap<String, JsonObject>()
        incomingArray.forEach { element ->
            val obj = element as? JsonObject ?: return@forEach
            val id = (obj["id"] as? JsonPrimitive)?.contentOrNull ?: return@forEach
            backupById[id] = obj
        }
        diffs.forEach { itemDiff ->
            when (itemDiff.decision) {
                SettingsItemDecision.IMPORT, SettingsItemDecision.USE_BACKUP ->
                    backupById[itemDiff.id]?.let { result[itemDiff.id] = it }
                SettingsItemDecision.DELETE -> result.remove(itemDiff.id)
                SettingsItemDecision.SKIP, SettingsItemDecision.KEEP, SettingsItemDecision.KEEP_LOCAL -> Unit
            }
        }
        return JsonArray(result.values.toList())
    }

    private fun reconcileDeletedIds(
        currentMap: MutableMap<String, JsonElement>,
        incomingJson: JsonObject,
        arrayKey: String,
        deletedKeys: List<String>,
    ) {
        val finalIds = (currentMap[arrayKey] as? JsonArray)
            ?.mapNotNull { ((it as? JsonObject)?.get("id") as? JsonPrimitive)?.contentOrNull }
            ?.toSet().orEmpty()
        deletedKeys.forEach { deletedKey ->
            val currentDeleted = (currentMap[deletedKey] as? JsonArray)
                ?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }?.toSet().orEmpty()
            val backupDeleted = (incomingJson[deletedKey] as? JsonArray)
                ?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }?.toSet().orEmpty()
            currentMap[deletedKey] = JsonArray(((currentDeleted + backupDeleted) - finalIds).map { JsonPrimitive(it) })
        }
    }

    companion object {
        private const val TAG = "BackupArchiveRestorer"
        private const val COPY_BUFFER_SIZE = 16 * 1024
        private const val MAX_SETTINGS_BYTES = 4L * 1024L * 1024L
        private const val MAX_ENTRY_BYTES = 512L * 1024L * 1024L
        private const val MAX_TOTAL_UNCOMPRESSED_BYTES = 2L * 1024L * 1024L * 1024L
        private const val MAX_ENTRY_COUNT = 20_000
        private val ROOT_NAME_REGEX = Regex("[A-Za-z0-9._-]+")
    }
}
/** [batch155] stageForMerge 的产物：已解压、校验并完成差异扫描的备份快照，等待用户确认。 */
class StagedMergeBackup(
    val stagingDir: File,
    val stagedDb: File?,
    val importedSettings: Settings?,
    val config: me.rerere.rikkahub.data.datastore.WebDavConfig,
)


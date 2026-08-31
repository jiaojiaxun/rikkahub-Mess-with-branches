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
                            importedSettings = json.decodeFromString<Settings>(SettingsJsonMigrator.migrate(raw))
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
        when (parts.lastOrNull()?.lowercase()) {
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

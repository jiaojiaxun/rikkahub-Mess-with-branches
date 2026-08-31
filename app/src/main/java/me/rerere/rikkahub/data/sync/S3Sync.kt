package me.rerere.rikkahub.data.sync

import android.content.Context
import android.util.Log
import io.ktor.client.HttpClient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import me.rerere.rikkahub.data.datastore.SettingsStore
import me.rerere.rikkahub.data.datastore.WebDavConfig
import me.rerere.rikkahub.data.sync.s3.S3Client
import me.rerere.rikkahub.data.sync.s3.S3Config
import me.rerere.rikkahub.data.sync.webdav.BackupArchiveRestorer
import me.rerere.rikkahub.data.sync.webdav.WebDavSync
import me.rerere.rikkahub.utils.fileSizeToString
import me.rerere.workspace.WorkspaceManager
import java.io.File
import java.time.Instant

private const val TAG = "S3Sync"

class S3Sync(
    private val settingsStore: SettingsStore,
    private val json: Json,
    private val context: Context,
    private val httpClient: HttpClient,
    private val appDatabase: me.rerere.rikkahub.data.db.AppDatabase,
    private val workspaceManager: WorkspaceManager,
    private val webDavSync: WebDavSync,
) {
    private fun getS3Client(config: S3Config): S3Client = S3Client(config, httpClient)

    suspend fun testS3(config: S3Config) = withContext(Dispatchers.IO) {
        getS3Client(config).listObjects(maxKeys = 1).getOrThrow()
        Log.i(TAG, "testS3: Connection successful")
    }

    suspend fun backupToS3(
        config: S3Config,
        onProgress: (BackupProgress) -> Unit = {},
    ) = withContext(Dispatchers.IO) {
        val file = webDavSync.prepareBackupFile(config.toWebDavConfig(), onProgress)
        try {
            val client = getS3Client(config)
            val key = "rikkahub_backups/${file.name}"
            onProgress(BackupProgress("上传备份", 0L, file.length(), file.name))
            client.putObject(
                key = key,
                file = file,
                contentType = "application/zip",
                onProgress = { completed, total ->
                    onProgress(
                        BackupProgress(
                            phase = "上传备份",
                            completed = completed,
                            total = total.takeIf { it > 0L } ?: file.length(),
                            detail = "已上传 ${completed.fileSizeToString()}",
                        )
                    )
                },
            ).getOrThrow()
            onProgress(BackupProgress("备份完成", file.length(), file.length(), file.name))
            Log.i(TAG, "backupToS3: Uploaded ${file.name} (${file.length().fileSizeToString()})")
        } finally {
            file.delete()
        }
    }

    suspend fun listBackupFiles(config: S3Config): List<S3BackupItem> = withContext(Dispatchers.IO) {
        getS3Client(config).listObjects(prefix = "rikkahub_backups/", maxKeys = 1000).getOrThrow()
            .objects
            .filter { it.key.startsWith("rikkahub_backups/backup_") && it.key.endsWith(".zip") }
            .map { obj ->
                S3BackupItem(
                    key = obj.key,
                    displayName = obj.key.substringAfterLast('/'),
                    size = obj.size,
                    lastModified = obj.lastModified ?: Instant.EPOCH,
                )
            }
            .sortedByDescending { it.lastModified }
    }

    suspend fun restoreFromS3(
        config: S3Config,
        item: S3BackupItem,
        mode: BackupRestoreMode = BackupRestoreMode.OVERWRITE,
        onProgress: (BackupProgress) -> Unit = {},
    ) = withContext(Dispatchers.IO) {
        val displayName = item.displayName
        require(displayName.isNotBlank() && File(displayName).name == displayName) {
            "不安全的 S3 备份文件名"
        }
        val backupFile = File(context.cacheDir, displayName)
        try {
            val client = getS3Client(config)
            onProgress(BackupProgress("下载备份", 0L, item.size, displayName))
            client.downloadObjectToFile(item.key, backupFile) { completed, total ->
                onProgress(
                    BackupProgress(
                        phase = "下载备份",
                        completed = completed,
                        total = total.takeIf { it > 0L } ?: item.size,
                        detail = "已下载 ${completed.fileSizeToString()}",
                    )
                )
            }.getOrThrow()

            BackupArchiveRestorer(
                context = context,
                json = json,
                settingsStore = settingsStore,
                appDatabase = appDatabase,
                workspaceManager = workspaceManager,
            ).restore(backupFile, config.toWebDavConfig(), mode, onProgress)
        } finally {
            backupFile.delete()
        }
    }

    suspend fun deleteS3BackupFile(config: S3Config, item: S3BackupItem) = withContext(Dispatchers.IO) {
        getS3Client(config).deleteObject(item.key).getOrThrow()
        Log.i(TAG, "deleteS3BackupFile: Deleted ${item.key}")
    }

    private fun S3Config.toWebDavConfig(): WebDavConfig = WebDavConfig(
        items = items.map {
            when (it) {
                S3Config.BackupItem.DATABASE -> WebDavConfig.BackupItem.DATABASE
                S3Config.BackupItem.FILES -> WebDavConfig.BackupItem.FILES
            }
        },
        )
}

data class S3BackupItem(
    val key: String,
    val displayName: String,
    val size: Long,
    val lastModified: Instant,
)

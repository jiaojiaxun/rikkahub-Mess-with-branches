package me.rerere.rikkahub.ui.pages.backup.tabs

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularWavyProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.dokar.sonner.ToastType
import kotlinx.coroutines.launch
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.File01
import me.rerere.hugeicons.stroke.FileImport
import me.rerere.rikkahub.R
import me.rerere.rikkahub.data.sync.BackupExportFormat
import me.rerere.rikkahub.data.sync.BackupProgress
import me.rerere.rikkahub.data.sync.BackupRestoreMode
import me.rerere.rikkahub.data.sync.displayName
import me.rerere.rikkahub.ui.components.ui.CardGroup
import me.rerere.rikkahub.ui.components.ui.StickyHeader
import me.rerere.rikkahub.ui.context.LocalToaster
import me.rerere.rikkahub.ui.pages.backup.BackupVM
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream

@Composable
fun ImportExportTab(
    vm: BackupVM,
    onShowRestartDialog: () -> Unit,
) {
    val toaster = LocalToaster.current
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val progress by vm.progress.collectAsStateWithLifecycle()
    var isExporting by remember { mutableStateOf(false) }
    var selectedExportFormat by remember { mutableStateOf(BackupExportFormat.FULL) }
    var isRestoring by remember { mutableStateOf(false) }
    var importType by remember { mutableStateOf("local") }
    var pendingRestoreFile by remember { mutableStateOf<File?>(null) }
    var showRestoreMode by remember { mutableStateOf(false) }

    fun showError(error: Throwable) {
        toaster.show(
            context.getString(R.string.backup_page_restore_failed, error.message ?: ""),
            type = ToastType.Error,
        )
    }

    fun restoreLocal(file: File, mode: BackupRestoreMode) {
        scope.launch {
            isRestoring = true
            runCatching { vm.restoreFromLocalFile(file, mode) }
                .onSuccess {
                    toaster.show(context.getString(R.string.backup_page_restore_success), type = ToastType.Success)
                    onShowRestartDialog()
                }
                .onFailure(::showError)
            file.delete()
            isRestoring = false
        }
    }

    val createDocumentLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.CreateDocument("application/zip"),
    ) { targetUri ->
        targetUri ?: return@rememberLauncherForActivityResult
        scope.launch {
            isExporting = true
            var exportFile: File? = null
            runCatching {
                exportFile = vm.exportToFile(selectedExportFormat)
                val source = requireNotNull(exportFile)
                context.contentResolver.openOutputStream(targetUri)?.use { output ->
                    FileInputStream(source).use { input ->
                        copyWithProgress(input, output, source.length()) { done, total ->
                            vm.reportProgress(
                                BackupProgress(
                                    phase = "导出文件",
                                    completed = done,
                                    total = total,
                                    detail = "写入用户选择的位置",
                                    totalLabel = "实际 ZIP 文件",
                                )
                            )
                        }
                    }
                } ?: error("无法打开导出目标")
            }.onSuccess {
                toaster.show(context.getString(R.string.backup_page_backup_success), type = ToastType.Success)
            }.onFailure(::showError)
            exportFile?.delete()
            vm.reportProgress(null)
            isExporting = false
        }
    }

    val openDocumentLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument(),
    ) { sourceUri ->
        sourceUri ?: return@rememberLauncherForActivityResult
        scope.launch {
            isRestoring = true
            runCatching {
                when (importType) {
                    "local" -> {
                        val temp = File(context.cacheDir, "temp_restore_${System.nanoTime()}.zip")
                        context.contentResolver.openInputStream(sourceUri)?.use { input ->
                            FileOutputStream(temp).use { output ->
                                copyWithProgress(input, output, contentLength(context, sourceUri)) { done, total ->
                                    vm.reportProgress(BackupProgress("复制备份", done, total, "准备导入 ZIP"))
                                }
                            }
                        } ?: error("无法读取备份文件")
                        pendingRestoreFile = temp
                        showRestoreMode = true
                    }
                    "chatbox" -> {
                        val temp = File(context.cacheDir, "temp_chatbox_${System.nanoTime()}.json")
                        context.contentResolver.openInputStream(sourceUri)?.use { input ->
                            FileOutputStream(temp).use { output -> input.copyTo(output) }
                        } ?: error("无法读取 Chatbox 文件")
                        vm.restoreFromChatBox(temp)
                        temp.delete()
                        toaster.show(context.getString(R.string.backup_page_restore_success), type = ToastType.Success)
                    }
                    "cherry" -> {
                        val temp = File(context.cacheDir, "temp_cherry_${System.nanoTime()}.zip")
                        context.contentResolver.openInputStream(sourceUri)?.use { input ->
                            FileOutputStream(temp).use { output -> input.copyTo(output) }
                        } ?: error("无法读取 Cherry Studio 文件")
                        vm.restoreFromCherryStudio(temp)
                        temp.delete()
                        toaster.show(context.getString(R.string.backup_page_restore_success), type = ToastType.Success)
                    }
                }
            }.onFailure(::showError)
            if (!showRestoreMode) isRestoring = false
            if (importType != "local") vm.reportProgress(null)
        }
    }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        verticalArrangement = Arrangement.spacedBy(16.dp),
        contentPadding = PaddingValues(16.dp),
    ) {
        progress?.let { value ->
            item { BackupProgressCard(value) }
        }
        stickyHeader { StickyHeader { Text(stringResource(R.string.backup_page_local_backup_export)) } }
        item {
            CardGroup {
                item(
                    onClick = if (!isExporting && !isRestoring) {
                        {
                            selectedExportFormat = BackupExportFormat.OFFICIAL
                            createDocumentLauncher.launch("rikkahub_official_backup.zip")
                        }
                    } else null,
                    headlineContent = { Text(stringResource(R.string.backup_page_local_backup_export_official)) },
                    supportingContent = {
                        Text(
                            if (isExporting && selectedExportFormat == BackupExportFormat.OFFICIAL) {
                                "正在导出：${progress?.detail.orEmpty()}"
                            } else stringResource(R.string.backup_page_local_backup_export_official_desc)
                        )
                    },
                    leadingContent = {
                        if (isExporting && selectedExportFormat == BackupExportFormat.OFFICIAL) {
                            CircularWavyProgressIndicator(modifier = Modifier.size(24.dp))
                        } else Icon(HugeIcons.File01, null)
                    },
                )
                item(
                    onClick = if (!isExporting && !isRestoring) {
                        {
                            selectedExportFormat = BackupExportFormat.FULL
                            createDocumentLauncher.launch("rikkahub_agent_backup.zip")
                        }
                    } else null,
                    headlineContent = { Text(stringResource(R.string.backup_page_local_backup_export_full)) },
                    supportingContent = {
                        Text(
                            if (isExporting && selectedExportFormat == BackupExportFormat.FULL) {
                                "正在导出：${progress?.detail.orEmpty()}"
                            } else stringResource(R.string.backup_page_local_backup_export_full_desc)
                        )
                    },
                    leadingContent = {
                        if (isExporting && selectedExportFormat == BackupExportFormat.FULL) {
                            CircularWavyProgressIndicator(modifier = Modifier.size(24.dp))
                        } else Icon(HugeIcons.FileImport, null)
                    },
                )
                item(
                    onClick = if (!isRestoring && !isExporting) {
                        {
                            importType = "local"
                            openDocumentLauncher.launch(arrayOf("application/zip", "application/octet-stream"))
                        }
                    } else null,
                    headlineContent = { Text(stringResource(R.string.backup_page_local_backup_import)) },
                    supportingContent = {
                        Text(if (isRestoring) "正在导入：${progress?.detail.orEmpty()}" else stringResource(R.string.backup_page_import_desc))
                    },
                    leadingContent = {
                        if (isRestoring) CircularWavyProgressIndicator(modifier = Modifier.size(24.dp))
                        else Icon(HugeIcons.FileImport, null)
                    },
                )
            }
        }
        stickyHeader { StickyHeader { Text(stringResource(R.string.backup_page_import_from_other_app)) } }
        item {
            CardGroup {
                item(
                    onClick = if (!isRestoring && !isExporting) {
                        { importType = "chatbox"; openDocumentLauncher.launch(arrayOf("application/json")) }
                    } else null,
                    headlineContent = { Text(stringResource(R.string.backup_page_import_from_chatbox)) },
                    supportingContent = { Text(stringResource(R.string.backup_page_import_chatbox_desc)) },
                    leadingContent = { Icon(HugeIcons.FileImport, null) },
                )
                item(
                    onClick = if (!isRestoring && !isExporting) {
                        { importType = "cherry"; openDocumentLauncher.launch(arrayOf("application/zip")) }
                    } else null,
                    headlineContent = { Text(stringResource(R.string.backup_page_import_from_cherry_studio)) },
                    supportingContent = { Text(stringResource(R.string.backup_page_import_cherry_studio_desc)) },
                    leadingContent = { Icon(HugeIcons.FileImport, null) },
                )
            }
        }
    }

    if (showRestoreMode) {
        AlertDialog(
            onDismissRequest = {
                pendingRestoreFile?.delete()
                pendingRestoreFile = null
                showRestoreMode = false
                isRestoring = false
                vm.reportProgress(null)
            },
            title = { Text("选择恢复方式") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("官方或旧版本 ZIP 会先经过兼容校验。请选择数据库如何写入当前应用。")
                    Text("合并：同一对话无分叉时采用较新的备份；有分叉时保留为新对话。")
                    Text("覆盖：关闭 Room 后原子替换数据库，并清理旧版禁用功能表。")
                }
            },
            confirmButton = {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TextButton(onClick = {
                        val file = pendingRestoreFile
                        pendingRestoreFile = null
                        showRestoreMode = false
                        if (file != null) restoreLocal(file, BackupRestoreMode.MERGE)
                    }) { Text(BackupRestoreMode.MERGE.displayName()) }
                    Button(onClick = {
                        val file = pendingRestoreFile
                        pendingRestoreFile = null
                        showRestoreMode = false
                        if (file != null) restoreLocal(file, BackupRestoreMode.OVERWRITE)
                    }) { Text(BackupRestoreMode.OVERWRITE.displayName()) }
                }
            },
            dismissButton = {
                TextButton(onClick = {
                    pendingRestoreFile?.delete()
                    pendingRestoreFile = null
                    showRestoreMode = false
                    isRestoring = false
                    vm.reportProgress(null)
                }) { Text("取消") }
            },
        )
    }
}

@Composable
private fun BackupProgressCard(progress: BackupProgress) {
    CardGroup {
        item(
            headlineContent = { Text(progress.phase) },
            supportingContent = {
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    val fraction = progress.fraction
                    if (fraction == null) LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                    else LinearProgressIndicator(
                        modifier = Modifier.fillMaxWidth(),
                        progress = { fraction },
                    )
                    Text("${progress.percent ?: 0}% · ${progress.detail}")
                    if (progress.total > 0L) {
                        Text("${progress.totalLabel}: ${formatBytes(progress.completed)} / ${formatBytes(progress.total)}")
                    }
                }
            },
        )
    }
}

private suspend fun copyWithProgress(
    input: java.io.InputStream,
    output: java.io.OutputStream,
    total: Long,
    onProgress: (Long, Long) -> Unit,
) {
    val buffer = ByteArray(16 * 1024)
    var completed = 0L
    while (true) {
        val read = input.read(buffer)
        if (read <= 0) break
        output.write(buffer, 0, read)
        completed += read
        onProgress(completed, total)
    }
}

private fun contentLength(context: android.content.Context, uri: android.net.Uri): Long =
    runCatching { context.contentResolver.openAssetFileDescriptor(uri, "r")?.use { it.length } ?: -1L }
        .getOrDefault(-1L)

private fun formatBytes(bytes: Long): String = when {
    bytes < 1024L -> "$bytes B"
    bytes < 1024L * 1024L -> "%.1f KB".format(bytes / 1024f)
    bytes < 1024L * 1024L * 1024L -> "%.1f MB".format(bytes / (1024f * 1024f))
    else -> "%.1f GB".format(bytes / (1024f * 1024f * 1024f))
}

package me.rerere.rikkahub.ui.components.message

import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.SheetValue
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.rememberBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import kotlinx.coroutines.launch
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonPrimitive
import me.rerere.ai.ui.UIMessagePart
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.File02
import me.rerere.hugeicons.stroke.FileImport
import me.rerere.hugeicons.stroke.Share08
import me.rerere.rikkahub.R
import me.rerere.rikkahub.data.model.Assistant
import me.rerere.rikkahub.data.repository.WorkspaceRepository
import me.rerere.workspace.WorkspaceStorageArea
import org.koin.compose.koinInject
import java.io.File
import androidx.compose.foundation.layout.fillMaxSize // rhAttachCardWorkspace
import androidx.compose.foundation.layout.Box // rhAttachCardWorkspace
import androidx.compose.foundation.shape.CircleShape // rhAttachCardWorkspace
import me.rerere.hugeicons.stroke.Download01 // rhAttachCardWorkspace

private const val DEFAULT_VISIBLE_COUNT = 3
private val WORKSPACE_FILE_TOOL_NAMES = setOf("workspace_write_file", "workspace_edit_file")

@OptIn(ExperimentalLayoutApi::class)
@Composable
internal fun EditedFilesList(
    parts: List<UIMessagePart>,
    assistant: Assistant?,
) {
    val workspaceId = assistant?.workspaceId?.toString() ?: return
    val editedFiles = remember(parts) {
        parts.filterIsInstance<UIMessagePart.Tool>()
            .filter { it.toolName in WORKSPACE_FILE_TOOL_NAMES && it.isExecuted }
            .mapNotNull { tool ->
(tool.inputAsJson() as? JsonObject)?.get("path")?.jsonPrimitive?.contentOrNull
            }
            .distinct()
    }
    if (editedFiles.isEmpty()) return

    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val workspaceRepository: WorkspaceRepository = koinInject()

    var selectedPath by remember { mutableStateOf<String?>(null) }
    var expanded by remember { mutableStateOf(false) }
    val visibleFiles = if (expanded) editedFiles else editedFiles.take(DEFAULT_VISIBLE_COUNT)
    val hasMore = editedFiles.size > DEFAULT_VISIBLE_COUNT

    val exportLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.CreateDocument("*/*"),
    ) { uri ->
        val path = selectedPath.also { selectedPath = null } ?: return@rememberLauncherForActivityResult
        if (uri == null) return@rememberLauncherForActivityResult
        val outputStream = context.contentResolver.openOutputStream(uri) ?: return@rememberLauncherForActivityResult
        scope.launch {
            runCatching {
                val (area, relativePath) = resolveWorkspacePath(path)
                outputStream.use { output ->
                    workspaceRepository.exportFile(workspaceId, area, relativePath, output)
                }
            }
        }
    }

    Column(  // rhAttachCardWorkspace: 大卡片需要纵向排列,不再 FlowRow 横排
        verticalArrangement = Arrangement.spacedBy(2.dp),
    ) {
        visibleFiles.forEach { path ->
            val fileName = remember(path) { path.substringAfterLast('/') }
            Surface(  // rhAttachCardWorkspace: 大卡片样式(对齐 batch120 用户消息附件)
                onClick = { selectedPath = path },
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                color = MaterialTheme.colorScheme.surfaceContainerHigh,
                tonalElevation = 2.dp,
            ) {
                Row(
                    modifier = Modifier.padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Surface(
                        modifier = Modifier.size(44.dp),
                        shape = RoundedCornerShape(12.dp),
                        color = MaterialTheme.colorScheme.surfaceContainerHigh,
                    ) {
                        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Icon(
                                imageVector = HugeIcons.File02,
                                contentDescription = null,
                                modifier = Modifier.size(24.dp),
                            )
                        }
                    }
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = fileName,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            style = MaterialTheme.typography.titleSmall,
                        )
                        Text(
                            text = "工作区文件",
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Surface(
                        modifier = Modifier.size(36.dp),
                        shape = CircleShape,
                        color = MaterialTheme.colorScheme.surfaceContainerHigh,
                    ) {
                        Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                            Icon(
                                imageVector = HugeIcons.Download01,
                                contentDescription = null,
                                modifier = Modifier.size(20.dp),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
        }
        if (hasMore && !expanded) {
            Surface(  // rhAttachCardWorkspace
                onClick = { expanded = true },
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(16.dp),
                color = MaterialTheme.colorScheme.surfaceContainerHigh,
            ) {
                Row(
                    modifier = Modifier.padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.Center,
                ) {
                    Text(
                        text = "+" + (editedFiles.size - DEFAULT_VISIBLE_COUNT).toString() + " 更多",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }

    if (selectedPath != null) {
        val path = selectedPath!!
        val fileName = remember(path) { path.substringAfterLast('/') }
        ModalBottomSheet(
            onDismissRequest = { selectedPath = null },
            sheetState = rememberBottomSheetState(
                initialValue = SheetValue.Hidden,
                enabledValues = setOf(SheetValue.Hidden, SheetValue.Expanded),
            ),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    text = fileName,
                    style = MaterialTheme.typography.titleMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Card(
                    onClick = {
                        val p = selectedPath ?: return@Card
                        exportLauncher.launch(p.substringAfterLast('/'))
                    },
                    shape = MaterialTheme.shapes.medium,
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(16.dp),
                        modifier = Modifier
                            .padding(16.dp)
                            .fillMaxWidth(),
                    ) {
                        Icon(
                            imageVector = HugeIcons.FileImport,
                            contentDescription = null,
                            modifier = Modifier.padding(4.dp),
                        )
                        Text(
                            text = stringResource(R.string.common_export),
                            style = MaterialTheme.typography.titleMedium,
                        )
                    }
                }
                Card(
                    onClick = {
                        val p = selectedPath ?: return@Card
                        selectedPath = null
                        scope.launch {
                            runCatching {
                                val (area, relativePath) = resolveWorkspacePath(p)
                                val dir = File(context.cacheDir, "workspace_share").apply { mkdirs() }
                                val file = File(dir, p.substringAfterLast('/'))
                                file.outputStream().use { output ->
                                    workspaceRepository.exportFile(workspaceId, area, relativePath, output)
                                }
                                val uri = FileProvider.getUriForFile(
                                    context,
                                    "${context.packageName}.fileprovider",
                                    file,
                                )
                                val intent = Intent(Intent.ACTION_SEND).apply {
                                    type = "application/octet-stream"
                                    putExtra(Intent.EXTRA_STREAM, uri)
                                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                                }
                                context.startActivity(Intent.createChooser(intent, null))
                            }
                        }
                    },
                    shape = MaterialTheme.shapes.medium,
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(16.dp),
                        modifier = Modifier
                            .padding(16.dp)
                            .fillMaxWidth(),
                    ) {
                        Icon(
                            imageVector = HugeIcons.Share08,
                            contentDescription = null,
                            modifier = Modifier.padding(4.dp),
                        )
                        Text(
                            text = stringResource(R.string.common_share),
                            style = MaterialTheme.typography.titleMedium,
                        )
                    }
                }
            }
        }
    }
}

private fun resolveWorkspacePath(path: String): Pair<WorkspaceStorageArea, String> {
    val trimmed = path.trimEnd('/')
    val relative = if (trimmed == "/workspace" || trimmed.startsWith("/workspace/")) {
        trimmed.removePrefix("/workspace").trimStart('/')
    } else {
        trimmed.trimStart('/')
    }
    return WorkspaceStorageArea.FILES to relative
}

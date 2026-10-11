package me.rerere.rikkahub.ui.pages.extensions.workspace

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import me.rerere.rikkahub.data.db.entity.WorkspaceEntity
import me.rerere.rikkahub.ui.theme.CustomColors
import me.rerere.workspace.WorkspaceShellStatus
import org.koin.androidx.compose.koinViewModel
import org.koin.core.parameter.parametersOf

@Composable
fun WorkspaceInstallCard(
    workspace: WorkspaceEntity?,
) {
    val workspaceId = workspace?.id ?: return
    val vm: WorkspaceInstallVM = koinViewModel(parameters = { parametersOf(workspaceId) })
    val installProgress by vm.installProgress.collectAsStateWithLifecycle()
    val installError by vm.installError.collectAsStateWithLifecycle()
    var showDialog by remember { mutableStateOf(false) }
    var url by remember {
        mutableStateOf("https://dl-cdn.alpinelinux.org/alpine/v3.22/releases/aarch64/alpine-minirootfs-3.22.0-aarch64.tar.gz")
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CustomColors.cardColorsOnSurfaceContainer,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = "Linux 环境（Shell）",
                style = MaterialTheme.typography.titleMedium,
            )
            Text(
                text = when (workspace.shellStatus) {
                    WorkspaceShellStatus.READY.name -> "已安装，可以使用 workspace_shell 等工具"
                    WorkspaceShellStatus.INSTALLING.name -> "正在安装…"
                    WorkspaceShellStatus.BROKEN.name -> "安装失败或文件缺失，请重新安装"
                    else -> "未安装——安装后 AI 就能在这个工作区里跑 Linux 命令"
                },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (installProgress != null) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }
            installError?.let { err ->
                Text(
                    text = err,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End,
            ) {
                Button(
                    onClick = { showDialog = true },
                    enabled = installProgress == null,
                ) {
                    Text(if (workspace.shellStatus == WorkspaceShellStatus.READY.name) "重新安装" else "安装 Rootfs")
                }
            }
        }
    }

    if (showDialog) {
        AlertDialog(
            onDismissRequest = { showDialog = false },
            title = { Text("安装 Linux Rootfs") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        text = "输入 rootfs 下载地址（tar.gz / tar.xz）。推荐 Alpine minirootfs（约 3MB）：",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    OutlinedTextField(
                        value = url,
                        onValueChange = { url = it },
                        modifier = Modifier.fillMaxWidth(),
                        singleLine = true,
                    )
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    showDialog = false
                    vm.install(url.trim())
                }) {
                    Text("安装")
                }
            },
            dismissButton = {
                TextButton(onClick = { showDialog = false }) {
                    Text("取消")
                }
            },
        )
    }
}

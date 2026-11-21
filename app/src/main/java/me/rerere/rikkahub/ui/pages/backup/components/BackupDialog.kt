package me.rerere.rikkahub.ui.pages.backup.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import me.rerere.rikkahub.R
import me.rerere.rikkahub.data.sync.PendingBackupDeleteStore
import kotlin.system.exitProcess

// rhBackupDel280: 恢复完成弹窗。勾选删除时先趁进程内授权有效立刻删, 删不掉才排队到下次启动。
@Composable
fun BackupDialog() {
    val context = LocalContext.current
    val candidateName = remember { PendingBackupDeleteStore.getCandidateName(context) }
    val hasCandidate = remember { PendingBackupDeleteStore.hasCandidate(context) }
    var deleteAfterRestore by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = {},
        title = { Text(stringResource(R.string.backup_page_restart_app)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(stringResource(R.string.backup_page_restart_desc))
                if (hasCandidate) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { deleteAfterRestore = !deleteAfterRestore }
                            .padding(vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Checkbox(
                            checked = deleteAfterRestore,
                            onCheckedChange = { deleteAfterRestore = it },
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = "删除本次恢复所用的备份包",
                                style = MaterialTheme.typography.bodyMedium,
                            )
                            Text(
                                text = candidateName ?: "上次恢复使用的备份文件",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    if (hasCandidate) {
                        if (deleteAfterRestore) {
                            if (!PendingBackupDeleteStore.deleteCandidateNow(context)) {
                                PendingBackupDeleteStore.queueForNextLaunch(context)
                            }
                        } else {
                            PendingBackupDeleteStore.clearCandidate(context)
                        }
                    }
                    exitProcess(0)
                }
            ) {
                Text(stringResource(R.string.backup_page_restart_app))
            }
        },
    )
}

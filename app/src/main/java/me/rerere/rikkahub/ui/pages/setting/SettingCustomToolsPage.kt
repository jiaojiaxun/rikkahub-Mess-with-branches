// rhCustomTools (batch213) — AI 自定义工具管理页：查看 / 开关 / 编辑 / 删除 / 新建
package me.rerere.rikkahub.ui.pages.setting

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.LargeFlexibleTopAppBar
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import me.rerere.rikkahub.data.ai.tools.custom.CustomToolDef
import me.rerere.rikkahub.data.ai.tools.custom.CustomToolStore
import me.rerere.rikkahub.ui.components.nav.BackButton
import me.rerere.rikkahub.ui.components.ui.CardGroup
import me.rerere.rikkahub.ui.theme.CustomColors
import me.rerere.rikkahub.utils.plus

@Composable
fun SettingCustomToolsPage() {
    val context = LocalContext.current
    val store = remember { CustomToolStore.get(context) }
    val tools by store.toolsFlow.collectAsStateWithLifecycle(initialValue = emptyList()) // rhCustomToolsCollectFix
    val scrollBehavior = TopAppBarDefaults.exitUntilCollapsedScrollBehavior()
    var editing by remember { mutableStateOf<CustomToolDef?>(null) }
    var creating by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            LargeFlexibleTopAppBar(
                title = { Text("AI 自定义工具") },
                navigationIcon = { BackButton() },
                actions = {
                    TextButton(onClick = { creating = true }) { Text("新建") }
                },
                scrollBehavior = scrollBehavior,
                colors = CustomColors.topBarColors,
            )
        },
        modifier = Modifier.nestedScroll(scrollBehavior.nestedScrollConnection),
        containerColor = CustomColors.topBarColors.containerColor,
    ) { contentPadding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = contentPadding + PaddingValues(8.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item("intro") {
                CardGroup(
                    modifier = Modifier.padding(horizontal = 8.dp),
                    title = { Text("这是什么") },
                ) {
                    item(
                        headlineContent = { Text("让 AI 自己写工具") },
                        supportingContent = {
                            Text("在助手的本地工具里开启「AI 自定义工具」后，AI 可以通过 manage_custom_tool 编写 JavaScript 工具并持久保存，之后的对话里按名字直接调用。代码在沙箱 WebView 里运行，可用 fetch 等浏览器能力，超时 60 秒。")
                        },
                    )
                }
            }

            item("tools") {
                CardGroup(
                    modifier = Modifier.padding(horizontal = 8.dp),
                    title = { Text("已创建的工具（" + tools.size + "）") },
                ) {
                    if (tools.isEmpty()) {
                        item(
                            headlineContent = { Text("还没有自定义工具") },
                            supportingContent = {
                                Text("在聊天里对 AI 说「帮我创建一个工具：……」，或点右上角新建")
                            },
                        )
                    } else {
                        tools.forEach { tool ->
                            item(
                                onClick = { editing = tool },
                                headlineContent = { Text(tool.name) },
                                supportingContent = {
                                    Column {
                                        if (tool.description.isNotBlank()) {
                                            Text(tool.description.take(80))
                                        }
                                        Text(
                                            text = "更新于 " + formatToolTime(tool.updatedAt),
                                            style = MaterialTheme.typography.labelSmall,
                                        )
                                    }
                                },
                                trailingContent = {
                                    Switch(
                                        checked = tool.enabled,
                                        onCheckedChange = { checked ->
                                            store.upsert(tool.copy(enabled = checked))
                                        },
                                    )
                                },
                            )
                        }
                    }
                }
            }
        }
    }

    editing?.let { tool ->
        CustomToolEditDialog(
            initial = tool,
            onDismiss = { editing = null },
            onSave = { updated ->
                store.upsert(updated)
                editing = null
            },
            onDelete = {
                store.delete(tool.id)
                editing = null
            },
        )
    }

    if (creating) {
        CustomToolEditDialog(
            initial = null,
            onDismiss = { creating = false },
            onSave = { updated ->
                store.upsert(updated)
                creating = false
            },
            onDelete = null,
        )
    }
}

@Composable
private fun CustomToolEditDialog(
    initial: CustomToolDef?,
    onDismiss: () -> Unit,
    onSave: (CustomToolDef) -> Unit,
    onDelete: (() -> Unit)?,
) {
    var name by remember { mutableStateOf(initial?.name ?: "") }
    var description by remember { mutableStateOf(initial?.description ?: "") }
    var code by remember { mutableStateOf(initial?.code ?: "") }
    val isCreate = initial == null

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (isCreate) "新建自定义工具" else ("编辑 " + (initial?.name ?: ""))) },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("工具名（小写字母/数字/下划线）") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it },
                    label = { Text("描述（AI 靠它决定何时调用）") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = code,
                    onValueChange = { code = it },
                    label = { Text("JavaScript 代码（需定义 main）") },
                    textStyle = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 6,
                )
                Text(
                    text = "代码约定：async function main(args) { ... return 文本; }，args 为模型传入的 JSON 对象。",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        },
        confirmButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                if (onDelete != null) {
                    TextButton(onClick = onDelete) {
                        Text("删除", color = MaterialTheme.colorScheme.error)
                    }
                }
                TextButton(
                    onClick = {
                        val base = initial
                        val def = CustomToolDef(
                            id = base?.id ?: "",
                            name = name.trim(),
                            description = description.trim(),
                            parameters = base?.parameters ?: kotlinx.serialization.json.buildJsonObject { },
                            code = code,
                            enabled = base?.enabled ?: true,
                            createdAt = base?.createdAt ?: 0L,
                        )
                        onSave(def)
                    },
                    enabled = name.trim().isNotEmpty() && code.isNotBlank(),
                ) {
                    Text("保存")
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        },
    )
}

private fun formatToolTime(millis: Long): String =
    if (millis <= 0L) {
        "未知时间"
    } else {
        java.text.SimpleDateFormat("MM-dd HH:mm", java.util.Locale.getDefault())
            .format(java.util.Date(millis))
    }

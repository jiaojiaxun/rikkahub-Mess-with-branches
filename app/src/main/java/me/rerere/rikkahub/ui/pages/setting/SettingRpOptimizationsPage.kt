package me.rerere.rikkahub.ui.pages.setting

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.ArrowRight01
import me.rerere.hugeicons.stroke.Delete02
import me.rerere.rikkahub.data.datastore.RpStyleRule
import me.rerere.rikkahub.ui.components.nav.BackButton
import me.rerere.rikkahub.ui.components.richtext.parseColorSafe
import me.rerere.rikkahub.ui.components.ui.CardGroup
import me.rerere.rikkahub.ui.theme.CustomColors
import me.rerere.rikkahub.utils.plus
import org.koin.androidx.compose.koinViewModel

/**
 * RP 优化 —— 自定义文本样式规则管理页。
 *
 * 用户定义规则: 让被特定 Markdown 模式包裹的文本以自定义颜色渲染。
 * 例如: pattern=* 时 *text* 显示为灰色(动作), pattern=** 时 **text** 显示为黄色(强调)。
 *
 * 规则存储在 DisplaySetting.rpStyleRules, 由 Markdown.kt 的 appendMarkdownNodeContent 消费。
 */
@Composable
fun SettingRpOptimizationsPage(vm: SettingVM = koinViewModel()) {
    val settings by vm.settings.collectAsStateWithLifecycle()
    var displaySetting by remember(settings) { mutableStateOf(settings.displaySetting) }
    val scrollBehavior = TopAppBarDefaults.exitUntilCollapsedScrollBehavior()
    var showAddDialog by remember { mutableStateOf(false) }
    var editingRule by remember { mutableStateOf<RpStyleRule?>(null) }

    fun updateRules(rules: List<RpStyleRule>) {
        val newDisplay = displaySetting.copy(rpStyleRules = rules)
        displaySetting = newDisplay
        vm.updateSettings(settings.copy(displaySetting = newDisplay))
    }

    Scaffold(
        topBar = {
            LargeFlexibleTopAppBar(
                title = { Text("RP 优化") },
                navigationIcon = { BackButton() },
                scrollBehavior = scrollBehavior,
                colors = CustomColors.topBarColors
            )
        },
        modifier = Modifier.nestedScroll(scrollBehavior.nestedScrollConnection),
        containerColor = CustomColors.topBarColors.containerColor
    ) { contentPadding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = contentPadding + PaddingValues(8.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // 说明
            item {
                CardGroup(
                    modifier = Modifier.padding(horizontal = 8.dp),
                    title = { Text("说明") },
                ) {
                    item(
                        headlineContent = { Text("自定义文本样式") },
                        supportingContent = {
                            Text("为特定 Markdown 模式指定自定义颜色。例如: * 对应斜体、** 对应粗体、~~ 对应删除线、` 对应行内代码。修改后即时生效。")
                        },
                    )
                }
            }

            // 规则列表
            item {
                CardGroup(
                    modifier = Modifier.padding(horizontal = 8.dp),
                    title = { Text("样式规则") },
                ) {
                    val rules = displaySetting.rpStyleRules
                    rules.forEach { rule ->
                        item(
                            onClick = { editingRule = rule },
                            leadingContent = {
                                Box(
                                    modifier = Modifier
                                        .size(24.dp)
                                        .clip(CircleShape)
                                        .background(
                                            parseColorSafe(rule.colorHex)
                                                ?: MaterialTheme.colorScheme.outline
                                        )
                                )
                            },
                            headlineContent = { Text(rule.pattern) },
                            supportingContent = { Text(rule.colorHex) },
                            trailingContent = {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Switch(
                                        checked = rule.enabled,
                                        onCheckedChange = { checked ->
                                            updateRules(
                                                rules.map {
                                                    if (it.id == rule.id) it.copy(enabled = checked) else it
                                                }
                                            )
                                        }
                                    )
                                    IconButton(
                                        onClick = {
                                            updateRules(rules.filter { it.id != rule.id })
                                        }
                                    ) {
                                        Icon(HugeIcons.Delete02, contentDescription = "删除")
                                    }
                                }
                            },
                        )
                    }
                    if (rules.isEmpty()) {
                        item(
                            headlineContent = { Text("暂无规则") },
                            supportingContent = { Text("点击下方按钮添加第一条规则") },
                        )
                    }
                }
            }

            // 添加按钮
            item {
                CardGroup(
                    modifier = Modifier.padding(horizontal = 8.dp),
                ) {
                    item(
                        onClick = { showAddDialog = true },
                        headlineContent = { Text("添加规则") },
                        trailingContent = {
                            Icon(HugeIcons.ArrowRight01, contentDescription = null)
                        },
                    )
                }
            }
        }
    }

    // 添加/编辑对话框
    if (showAddDialog || editingRule != null) {
        RpRuleEditDialog(
            rule = editingRule,
            onDismiss = {
                showAddDialog = false
                editingRule = null
            },
            onConfirm = { pattern, colorHex, enabled ->
                val editing = editingRule
                val newRules = if (editing != null) {
                    displaySetting.rpStyleRules.map {
                        if (it.id == editing.id) {
                            it.copy(pattern = pattern, colorHex = colorHex, enabled = enabled)
                        } else it
                    }
                } else {
                    displaySetting.rpStyleRules + RpStyleRule(
                        pattern = pattern,
                        colorHex = colorHex,
                        enabled = enabled
                    )
                }
                updateRules(newRules)
                showAddDialog = false
                editingRule = null
            }
        )
    }
}

@Composable
private fun RpRuleEditDialog(
    rule: RpStyleRule?,
    onDismiss: () -> Unit,
    onConfirm: (pattern: String, colorHex: String, enabled: Boolean) -> Unit,
) {
    var pattern by remember { mutableStateOf(rule?.pattern ?: "*") }
    var colorHex by remember { mutableStateOf(rule?.colorHex ?: "#808080") }
    var enabled by remember { mutableStateOf(rule?.enabled ?: true) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (rule == null) "添加规则" else "编辑规则") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedTextField(
                    value = pattern,
                    onValueChange = { pattern = it },
                    label = { Text("模式") },
                    placeholder = { Text("如 * 或 ** 或 ~~") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = colorHex,
                    onValueChange = { colorHex = it },
                    label = { Text("颜色 (Hex)") },
                    placeholder = { Text("#808080") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    leadingIcon = {
                        Box(
                            modifier = Modifier
                                .size(24.dp)
                                .clip(CircleShape)
                                .background(
                                    parseColorSafe(colorHex)
                                        ?: MaterialTheme.colorScheme.outline
                                )
                        )
                    }
                )
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Switch(checked = enabled, onCheckedChange = { enabled = it })
                    Text("启用")
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { onConfirm(pattern.trim(), colorHex.trim(), enabled) }) {
                Text("确定")
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) {
                Text("取消")
            }
        },
    )
}

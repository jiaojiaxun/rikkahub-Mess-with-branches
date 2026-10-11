#!/usr/bin/env python3
# batch157: 备份合并改造 8/10 —— 差异确认界面（MergeConfirmDialog）
# 设计: 全屏 Dialog 挂在 BackupPage 层; 对话差异按关系分组(需拍板/自动处理/无差异折叠);
#       每项展示双侧摘要(消息数/更新时间/首条用户消息/末条消息预览)——不只按名字区分;
#       设置条目按类别列出差异摘要+决策 chips; 标量偏好为 checkbox 列表。
#       文案硬编码中文(跟随 ImportExportTab「选择恢复方式」先例), 不碰 strings.xml。
# 变更: 仅新增一个文件, 不修改任何现有文件。
#   1) app/.../ui/pages/backup/MergeConfirmDialog.kt
# 幂等: 目标文件已存在且含 [batch157] 标记则跳过; 存在但无标记则 fail(防冲突)。

import io
import os
import sys

NL = chr(10)
MARK = "[batch157]"

UI_PATH = "app/src/main/java/me/rerere/rikkahub/ui/pages/backup/MergeConfirmDialog.kt"

UI_KT = r'''// [batch157] 备份合并改造：差异确认界面
// 扫描完成后弹出，逐项展示对话与设置的差异，用户拍板后才开始写库。
package me.rerere.rikkahub.ui.pages.backup

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import me.rerere.rikkahub.data.sync.merge.ConversationMergeDecision
import me.rerere.rikkahub.data.sync.merge.ConversationMergeItem
import me.rerere.rikkahub.data.sync.merge.ConversationMergeRelation
import me.rerere.rikkahub.data.sync.merge.ConversationSideSummary
import me.rerere.rikkahub.data.sync.merge.MergePlan
import me.rerere.rikkahub.data.sync.merge.SettingsItemCategory
import me.rerere.rikkahub.data.sync.merge.SettingsItemDecision
import me.rerere.rikkahub.data.sync.merge.SettingsItemDiff
import me.rerere.rikkahub.data.sync.merge.SettingsItemKind
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

@Composable
fun MergeConfirmDialog(
    plan: MergePlan,
    onConversationDecision: (String, ConversationMergeDecision) -> Unit,
    onSettingsItemDecision: (SettingsItemCategory, String, SettingsItemDecision) -> Unit,
    onToggleScalar: (String) -> Unit,
    onConfirm: () -> Unit,
    onCancel: () -> Unit,
) {
    Dialog(
        onDismissRequest = onCancel,
        properties = DialogProperties(usePlatformDefaultWidth = false),
    ) {
        Surface(modifier = Modifier.fillMaxSize()) {
            Column(modifier = Modifier.fillMaxSize()) {
                // 顶部标题与统计
                Column(modifier = Modifier.padding(horizontal = 20.dp, vertical = 12.dp)) {
                    Text("备份合并确认", style = MaterialTheme.typography.titleLarge)
                    Text(
                        text = "逐项确认差异的处理方式，确认后才会写入",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Spacer(modifier = Modifier.fillMaxWidth().height(1.dp).background(MaterialTheme.colorScheme.outlineVariant))

                LazyColumn(
                    modifier = Modifier.weight(1f),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    val diverged = plan.conversations.filter {
                        it.relation == ConversationMergeRelation.DIVERGED
                    }
                    val autoHandled = plan.conversations.filter {
                        it.relation == ConversationMergeRelation.NEW ||
                            it.relation == ConversationMergeRelation.BACKUP_AHEAD ||
                            it.relation == ConversationMergeRelation.LOCAL_AHEAD ||
                            it.relation == ConversationMergeRelation.VERSIONS_MODIFIED
                    }
                    val identical = plan.conversations.filter {
                        it.relation == ConversationMergeRelation.SAME
                    }

                    if (diverged.isNotEmpty()) {
                        item { SectionHeader("需要你来决定（${diverged.size} 个对话分叉）") }
                        items(diverged, key = { "div_" + it.conversationId }) { item ->
                            ConversationDiffCard(item, detailed = true, onConversationDecision)
                        }
                    }
                    if (autoHandled.isNotEmpty()) {
                        item { SectionHeader("自动处理（${autoHandled.size} 项，可点开修改）") }
                        items(autoHandled, key = { "auto_" + it.conversationId }) { item ->
                            ConversationDiffCard(item, detailed = false, onConversationDecision)
                        }
                    }
                    if (identical.isNotEmpty()) {
                        item {
                            Text(
                                "无差异：${identical.size} 个对话内容一致，不会改动",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }

                    val settingsDiff = plan.settings
                    if (settingsDiff != null && settingsDiff.items.isNotEmpty()) {
                        item { SectionHeader("设置条目差异（${settingsDiff.items.size}）") }
                        items(settingsDiff.items, key = { it.category.name + "_" + it.id }) { item ->
                            SettingsItemCard(item, onSettingsItemDecision)
                        }
                    }
                    if (settingsDiff != null && settingsDiff.scalarFields.isNotEmpty()) {
                        item { SectionHeader("偏好设置差异（勾选 = 采用备份值）") }
                        items(settingsDiff.scalarFields, key = { it.fieldKey }) { field ->
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Checkbox(
                                    checked = field.adoptBackup,
                                    onCheckedChange = { onToggleScalar(field.fieldKey) },
                                )
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(field.displayName, style = MaterialTheme.typography.bodyMedium)
                                    Text(
                                        "本地：" + field.localValuePreview,
                                        style = MaterialTheme.typography.bodySmall,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis,
                                    )
                                    Text(
                                        "备份：" + field.backupValuePreview,
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.primary,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis,
                                    )
                                }
                            }
                        }
                    }

                    if (plan.memoriesToAdd > 0 || plan.favoritesToAdd > 0 || plan.workspacesToMerge > 0) {
                        item { SectionHeader("其他数据（自动合并）") }
                        item {
                            Text(
                                "记忆 ${plan.memoriesToAdd} 条（自动去重） · " +
                                    "收藏 ${plan.favoritesToAdd} 条（引用有效才导入） · " +
                                    "工作区 ${plan.workspacesToMerge} 个",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.fillMaxWidth().height(1.dp).background(MaterialTheme.colorScheme.outlineVariant))
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 20.dp, vertical = 12.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp, Alignment.End),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    TextButton(onClick = onCancel) { Text("取消") }
                    Button(onClick = onConfirm) { Text("开始合并") }
                }
            }
        }
    }
}

@Composable
private fun SectionHeader(text: String) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleSmall,
        fontWeight = FontWeight.Bold,
        color = MaterialTheme.colorScheme.primary,
    )
}

@Composable
private fun ConversationDiffCard(
    item: ConversationMergeItem,
    detailed: Boolean,
    onDecision: (String, ConversationMergeDecision) -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(item.title.ifBlank { "（无标题）" }, style = MaterialTheme.typography.titleMedium)
            Text(
                relationLabel(item.relation) + " · " + item.relationNote,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (detailed) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    ConversationSideBox("本地", item.local, Modifier.weight(1f))
                    ConversationSideBox("备份", item.backup, Modifier.weight(1f))
                }
            } else {
                Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                    Text(
                        "本地：" + sideBrief(item.local),
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.weight(1f),
                    )
                    Text(
                        "备份：" + sideBrief(item.backup),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.weight(1f),
                    )
                }
            }
            DecisionChips(item, onDecision)
        }
    }
}

@Composable
private fun ConversationSideBox(
    label: String,
    summary: ConversationSideSummary?,
    modifier: Modifier = Modifier,
) {
    Column(modifier = modifier, verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(label, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
        if (summary == null) {
            Text("（不存在）", style = MaterialTheme.typography.bodySmall)
        } else {
            Text(
                "${summary.nodeCount} 节点 · ${summary.messageCount} 条 · ${formatTime(summary.updateAt)}",
                style = MaterialTheme.typography.bodySmall,
            )
            if (summary.firstUserMessagePreview.isNotBlank()) {
                Text(
                    "起：" + summary.firstUserMessagePreview,
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            if (summary.lastMessagePreview.isNotBlank()) {
                Text(
                    "末：" + summary.lastMessagePreview,
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun DecisionChips(
    item: ConversationMergeItem,
    onDecision: (String, ConversationMergeDecision) -> Unit,
) {
    val options: List<Pair<ConversationMergeDecision, String>> = when (item.relation) {
        ConversationMergeRelation.NEW -> listOf(
            ConversationMergeDecision.IMPORT to "导入",
            ConversationMergeDecision.SKIP to "不导入",
        )

        ConversationMergeRelation.VERSIONS_MODIFIED -> listOf(
            ConversationMergeDecision.MERGE_VERSIONS to "合并版本",
            ConversationMergeDecision.USE_BACKUP to "用备份",
            ConversationMergeDecision.KEEP_LOCAL to "保留本地",
            ConversationMergeDecision.KEEP_BOTH to "都保留",
        )

        else -> listOf(
            ConversationMergeDecision.KEEP_LOCAL to "保留本地",
            ConversationMergeDecision.USE_BACKUP to "用备份",
            ConversationMergeDecision.KEEP_BOTH to "都保留",
        )
    }
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEach { (decision, label) ->
            FilterChip(
                selected = item.decision == decision,
                onClick = { onDecision(item.conversationId, decision) },
                label = { Text(label, style = MaterialTheme.typography.labelSmall) },
            )
        }
    }
}

@Composable
private fun SettingsItemCard(
    item: SettingsItemDiff,
    onDecision: (SettingsItemCategory, String, SettingsItemDecision) -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    categoryLabel(item.category),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                )
                Spacer(modifier = Modifier.padding(horizontal = 4.dp))
                Text(item.displayName, style = MaterialTheme.typography.titleSmall)
            }
            Text(item.detail, style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
            val options: List<Pair<SettingsItemDecision, String>> = when (item.kind) {
                SettingsItemKind.ADDED_IN_BACKUP -> listOf(
                    SettingsItemDecision.IMPORT to "导入",
                    SettingsItemDecision.SKIP to "不导入",
                )

                SettingsItemKind.DELETED_LOCALLY -> listOf(
                    SettingsItemDecision.IMPORT to "恢复",
                    SettingsItemDecision.SKIP to "保持删除",
                )

                SettingsItemKind.REMOVED_IN_BACKUP -> listOf(
                    SettingsItemDecision.DELETE to "删除本地",
                    SettingsItemDecision.KEEP to "保留本地",
                )

                SettingsItemKind.MODIFIED -> listOf(
                    SettingsItemDecision.KEEP_LOCAL to "保留本地",
                    SettingsItemDecision.USE_BACKUP to "用备份",
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                options.forEach { (decision, label) ->
                    FilterChip(
                        selected = item.decision == decision,
                        onClick = { onDecision(item.category, item.id, decision) },
                        label = { Text(label, style = MaterialTheme.typography.labelSmall) },
                    )
                }
            }
        }
    }
}

private fun relationLabel(relation: ConversationMergeRelation): String = when (relation) {
    ConversationMergeRelation.NEW -> "新对话"
    ConversationMergeRelation.SAME -> "无差异"
    ConversationMergeRelation.BACKUP_AHEAD -> "备份更新"
    ConversationMergeRelation.LOCAL_AHEAD -> "本地更新"
    ConversationMergeRelation.VERSIONS_MODIFIED -> "版本变化"
    ConversationMergeRelation.DIVERGED -> "已分叉"
}

private fun categoryLabel(category: SettingsItemCategory): String = when (category) {
    SettingsItemCategory.PROVIDER -> "供应商"
    SettingsItemCategory.ASSISTANT -> "助手"
    SettingsItemCategory.MCP_SERVER -> "MCP 服务器"
}

private fun sideBrief(summary: ConversationSideSummary?): String =
    if (summary == null) "（不存在）" else "${summary.nodeCount} 节点 · ${formatTime(summary.updateAt)}"

private fun formatTime(epochMillis: Long): String =
    if (epochMillis <= 0L) "未知时间"
    else SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()).format(Date(epochMillis))
'''

REQUIRED_SNIPPETS = (
    (UI_PATH, "fun MergeConfirmDialog("),
    (UI_PATH, "private fun ConversationDiffCard("),
    (UI_PATH, "private fun SettingsItemCard("),
)


def fail(msg):
    print("::error::" + msg)
    sys.exit(1)


def write_new_file(path, content):
    if os.path.exists(path):
        with io.open(path, "r", encoding="utf-8") as f:
            existing = f.read()
        if MARK in existing:
            print("batch157: already applied, skip " + path)
            return
        fail("batch157: target exists without mark :: " + path)
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    try:
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as exc:
        fail("batch157: write failed :: " + path + " :: " + str(exc))
    print("batch157: wrote " + path)


def verify_file(path, needle):
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as exc:
        fail("batch157: verify read failed :: " + path + " :: " + str(exc))
    if needle not in content:
        fail("batch157: verify failed, missing " + needle + " in " + path)
    if MARK not in content:
        fail("batch157: verify failed, missing mark in " + path)


def main():
    write_new_file(UI_PATH, UI_KT)
    for path, needle in REQUIRED_SNIPPETS:
        verify_file(path, needle)
    print("batch157: merge confirm dialog written")


if __name__ == "__main__":
    main()

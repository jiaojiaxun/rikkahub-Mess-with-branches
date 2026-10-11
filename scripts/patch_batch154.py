#!/usr/bin/env python3
# batch154: 备份合并改造 5/10 —— 备份合并扫描器（scan 阶段，不写库）
# 职责: 读 staged 备份库 + 本地库(仅交集, P7 性能修复) → 逐对话关系判定 →
#       设置差异(JSON 层) → 产出 MergePlan 供 UI 确认。
# 变更: 仅新增一个文件, 不修改任何现有文件。
#   1) app/.../data/sync/merge/BackupMergeScanner.kt
# 幂等: 目标文件已存在且含 [batch154] 标记则跳过; 存在但无标记则 fail(防冲突)。

import io
import os
import sys

NL = chr(10)
MARK = "[batch154]"

SCANNER_PATH = "app/src/main/java/me/rerere/rikkahub/data/sync/merge/BackupMergeScanner.kt"

SCANNER_KT = r'''// [batch154] 备份合并改造：备份合并扫描器
// scan 阶段：只读不写。读取 staged 备份库与本地库的交集对话（P7：不再全库扫描），
// 逐对话用语义签名判定关系，计算设置差异，产出 MergePlan 交给 UI 确认。
package me.rerere.rikkahub.data.sync.merge

import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.jsonObject
import me.rerere.rikkahub.data.datastore.Settings
import me.rerere.rikkahub.data.datastore.SettingsStore
import me.rerere.rikkahub.data.db.AppDatabase
import me.rerere.rikkahub.data.db.entity.ConversationEntity
import me.rerere.rikkahub.data.db.entity.MessageNodeEntity
import me.rerere.rikkahub.utils.JsonInstant
import java.io.File

class BackupMergeScanner(
    private val appDatabase: AppDatabase,
    private val settingsStore: SettingsStore,
) {
    suspend fun scan(
        stagedDatabase: File,
        importedSettings: Settings?,
    ): MergePlan = withContext(Dispatchers.IO) {
        require(stagedDatabase.exists() && stagedDatabase.length() > 0L) { "备份数据库不存在或为空" }

        SQLiteDatabase.openDatabase(
            stagedDatabase.absolutePath,
            null,
            SQLiteDatabase.OPEN_READONLY,
        ).use { source ->
            val stagedConversations = readStagedConversations(source)
            val stagedIds = stagedConversations.map { it.id }.toSet()

            // P7：只加载备份里出现的对话的本地数据（旧逻辑是全库 N+1 扫描）
            val localEntities = stagedIds
                .mapNotNull { id -> appDatabase.conversationDao().getConversationById(id) }
                .associateBy { it.id }
            val localNodes = stagedIds.associateWith { id ->
                appDatabase.messageNodeDao().getNodesOfConversation(id)
            }

            val conversationItems = stagedConversations.map { backupConv ->
                val localEntity = localEntities[backupConv.id]
                val localSnapshot = localEntity?.let { entity ->
                    toSnapshot(entity, localNodes[backupConv.id].orEmpty())
                }
                val result = ConversationMergeAnalyzer.analyze(localSnapshot, backupConv)
                ConversationMergeItem(
                    conversationId = backupConv.id,
                    title = backupConv.title,
                    relation = result.relation,
                    local = localSnapshot?.let(ConversationMergeAnalyzer::summarize),
                    backup = ConversationMergeAnalyzer.summarize(backupConv),
                    defaultDecision = ConversationMergeAnalyzer.defaultDecision(
                        result.relation, localSnapshot, backupConv,
                    ),
                    relationNote = result.note,
                )
            }

            val settingsDiff = importedSettings?.let { incoming ->
                runCatching { diffSettings(incoming) }
                    .onFailure { Log.w(TAG, "设置差异计算失败，跳过设置合并", it) }
                    .getOrNull()
            }

            MergePlan(
                conversations = conversationItems,
                settings = settingsDiff,
                memoriesToAdd = countRows(source, "MemoryEntity").toInt(),
                favoritesToAdd = countRows(source, "favorites").toInt(),
                workspacesToMerge = countRows(source, "workspaces").toInt(),
            )
        }
    }

    /** 纯设置差异（无数据库备份项时使用）。公开供两阶段会话调用。 */
    fun diffSettings(incoming: Settings): SettingsMergeDiff {
        val current = settingsStore.settingsFlow.value
        val currentJson = JsonInstant.encodeToJsonElement(current).jsonObject
        val incomingJson = JsonInstant.encodeToJsonElement(incoming).jsonObject
        val currentDeleted = mapOf(
            SettingsItemCategory.PROVIDER to
                (current.deletedProviderIds + current.deletedBuiltInProviderIds).map { it.toString() }.toSet(),
            SettingsItemCategory.ASSISTANT to current.deletedAssistantIds.map { it.toString() }.toSet(),
            SettingsItemCategory.MCP_SERVER to current.deletedMcpServerIds.map { it.toString() }.toSet(),
        )
        val backupDeleted = mapOf(
            SettingsItemCategory.PROVIDER to
                (incoming.deletedProviderIds + incoming.deletedBuiltInProviderIds).map { it.toString() }.toSet(),
            SettingsItemCategory.ASSISTANT to incoming.deletedAssistantIds.map { it.toString() }.toSet(),
            SettingsItemCategory.MCP_SERVER to incoming.deletedMcpServerIds.map { it.toString() }.toSet(),
        )
        return SettingsMergeAnalyzer.diff(currentJson, incomingJson, currentDeleted, backupDeleted)
    }

    private fun toSnapshot(
        entity: ConversationEntity,
        nodes: List<MessageNodeEntity>,
    ): MergeConversationSnapshot = MergeConversationSnapshot(
        id = entity.id,
        title = entity.title,
        updateAt = entity.updateAt,
        nodes = nodes.map { MergeNodeSnapshot(it.id, it.nodeIndex, it.messages, it.selectIndex) },
    )

    private fun readStagedConversations(source: SQLiteDatabase): List<MergeConversationSnapshot> {
        if (!tableExists(source, "ConversationEntity")) return emptyList()
        return source.query("ConversationEntity", null, null, null, null, null, null).use { cursor ->
            val result = mutableListOf<MergeConversationSnapshot>()
            while (cursor.moveToNext()) {
                val id = cursor.string("id") ?: continue
                result += MergeConversationSnapshot(
                    id = id,
                    title = cursor.string("title").orEmpty(),
                    updateAt = cursor.long("update_at"),
                    nodes = readStagedNodes(source, id),
                )
            }
            result
        }
    }

    private fun readStagedNodes(source: SQLiteDatabase, conversationId: String): List<MergeNodeSnapshot> {
        if (!tableExists(source, "message_node")) return emptyList()
        return source.query(
            "message_node", null, "conversation_id = ?",
            arrayOf(conversationId), null, null, "node_index ASC",
        ).use { cursor ->
            val result = mutableListOf<MergeNodeSnapshot>()
            while (cursor.moveToNext()) {
                result += MergeNodeSnapshot(
                    nodeId = cursor.string("id") ?: continue,
                    nodeIndex = cursor.int("node_index"),
                    messagesJson = cursor.string("messages") ?: continue,
                    selectIndex = cursor.int("select_index"),
                )
            }
            result
        }
    }

    private fun countRows(db: SQLiteDatabase, table: String): Long {
        if (!tableExists(db, table)) return 0L
        return db.rawQuery("SELECT COUNT(*) FROM `$table`", null).use { cursor ->
            if (cursor.moveToFirst()) cursor.getLong(0) else 0L
        }
    }

    private fun tableExists(db: SQLiteDatabase, table: String): Boolean =
        db.rawQuery(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND lower(name) = lower(?) LIMIT 1",
            arrayOf(table),
        ).use { it.moveToFirst() }

    private fun Cursor.string(column: String): String? =
        getColumnIndex(column).takeIf { it >= 0 && !isNull(it) }?.let(::getString)

    private fun Cursor.long(column: String): Long = string(column)?.toLongOrNull() ?: 0L

    private fun Cursor.int(column: String): Int = string(column)?.toIntOrNull() ?: 0

    companion object {
        private const val TAG = "BackupMergeScanner"
    }
}
'''

REQUIRED_SNIPPETS = (
    (SCANNER_PATH, "class BackupMergeScanner"),
    (SCANNER_PATH, "suspend fun scan("),
    (SCANNER_PATH, "fun diffSettings("),
)


def fail(msg):
    print("::error::" + msg)
    sys.exit(1)


def write_new_file(path, content):
    if os.path.exists(path):
        with io.open(path, "r", encoding="utf-8") as f:
            existing = f.read()
        if MARK in existing:
            print("batch154: already applied, skip " + path)
            return
        fail("batch154: target exists without mark :: " + path)
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    try:
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as exc:
        fail("batch154: write failed :: " + path + " :: " + str(exc))
    print("batch154: wrote " + path)


def verify_file(path, needle):
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as exc:
        fail("batch154: verify read failed :: " + path + " :: " + str(exc))
    if needle not in content:
        fail("batch154: verify failed, missing " + needle + " in " + path)
    if MARK not in content:
        fail("batch154: verify failed, missing mark in " + path)


def main():
    write_new_file(SCANNER_PATH, SCANNER_KT)
    for path, needle in REQUIRED_SNIPPETS:
        verify_file(path, needle)
    print("batch154: backup merge scanner written")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# batch153: 备份合并改造 4/10 —— 合并决策应用器 + 节点版本合并器 + 单元测试
# 职责: 按 MergePlan 的用户决策写库。包含审查修复点:
#   P2 fork 时 favorites 的 refKey 同步 remap 到新节点 id(不再静默丢收藏)
#   P3 对话 assistantId/folderId 悬挂引用兜底(挂到默认助手/移出文件夹)
#   P6 单事务写入; MERGE_VERSIONS 所需本地数据在事务前预读(避免事务内 suspend DAO)
#   P7 扫描端只读交集(见 batch152), 应用端按决策精确写入
# 变更: 仅新增三个文件, 不修改任何现有文件。
#   1) app/.../data/sync/merge/NodeVersionMerger.kt      —— 版本数组合并(纯函数)
#   2) app/.../data/sync/merge/MergeDecisionApplier.kt   —— 决策应用器
#   3) app/src/test/.../merge/NodeVersionMergerTest.kt
# 幂等: 目标文件已存在且含 [batch153] 标记则跳过; 存在但无标记则 fail(防冲突)。

import io
import os
import sys

NL = chr(10)
MARK = "[batch153]"

MERGER_PATH = "app/src/main/java/me/rerere/rikkahub/data/sync/merge/NodeVersionMerger.kt"
APPLIER_PATH = "app/src/main/java/me/rerere/rikkahub/data/sync/merge/MergeDecisionApplier.kt"
TEST_PATH = "app/src/test/java/me/rerere/rikkahub/data/sync/merge/NodeVersionMergerTest.kt"

MERGER_KT = r'''// [batch153] 备份合并改造：节点消息版本合并器（纯函数，可单测）
// 场景：同一节点在两边各自重生成过（版本数组不同），用户选择"合并版本"时，
// 取两边消息版本的并集（按消息 id 去重，本地版本在前、备份新增版本追加在后），
// selectIndex 指向"较新一方"原来选中的那条消息。
package me.rerere.rikkahub.data.sync.merge

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull

object NodeVersionMerger {
    private val json = Json { ignoreUnknownKeys = true }

    /**
     * 合并同一节点两侧的消息版本数组。
     * @param preferBackupSelection true 时选中版本跟随备份，否则跟随本地。
     * @return 合并后的 (messagesJson, selectIndex)；无法合并（JSON 损坏）时返回 null，
     *         调用方应降级为保留本地。
     */
    fun merge(
        localMessagesJson: String,
        localSelectIndex: Int,
        backupMessagesJson: String,
        backupSelectIndex: Int,
        preferBackupSelection: Boolean,
    ): Pair<String, Int>? {
        val localMsgs = parseArray(localMessagesJson) ?: return null
        val backupMsgs = parseArray(backupMessagesJson) ?: return null
        if (localMsgs.isEmpty()) return backupMessagesJson to backupSelectIndex
        if (backupMsgs.isEmpty()) return localMessagesJson to localSelectIndex

        val localIds = localMsgs.mapNotNull(::messageId)
        val backupOnly = backupMsgs.filter { messageId(it)?.let { id -> id !in localIds } != false }
        val merged = localMsgs + backupOnly

        val selectIndex = if (preferBackupSelection) {
            val selectedId = backupMsgs.getOrNull(backupSelectIndex)?.let(::messageId)
            if (selectedId != null) {
                merged.indexOfFirst { messageId(it) == selectedId }.takeIf { it >= 0 }
                    ?: localSelectIndex.coerceIn(0, merged.size - 1)
            } else {
                localSelectIndex.coerceIn(0, merged.size - 1)
            }
        } else {
            localSelectIndex.coerceIn(0, merged.size - 1)
        }
        return JsonArray(merged).toString() to selectIndex
    }

    private fun parseArray(messagesJson: String): List<JsonElement>? {
        val array = runCatching { json.parseToJsonElement(messagesJson) as? JsonArray }.getOrNull()
        return array?.toList()
    }

    private fun messageId(element: JsonElement): String? =
        ((element as? JsonObject)?.get("id") as? JsonPrimitive)?.contentOrNull
}
'''

APPLIER_KT = r'''// [batch153] 备份合并改造：合并决策应用器
// 按 MergePlan 中用户的最终决策写库。与旧 BackupDatabaseMerger 的区别：
//  - 不做任何自动分叉判定（判定已在扫描阶段完成并经用户确认）
//  - fork（KEEP_BOTH）时同步 remap 收藏的节点引用，不再静默丢失（P2）
//  - 对话的 assistantId/folderId 悬挂引用兜底（P3）
//  - 全部写入在单个事务内完成（P6）
package me.rerere.rikkahub.data.sync.merge

import android.content.ContentValues
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.util.Log
import androidx.sqlite.db.SupportSQLiteDatabase
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import me.rerere.rikkahub.data.db.AppDatabase
import me.rerere.rikkahub.data.db.entity.MessageNodeEntity
import me.rerere.workspace.WorkspaceManager
import java.io.File
import kotlin.uuid.Uuid

/** 应用结果统计（用于完成提示）。 */
data class MergeApplyResult(
    val imported: Int = 0,
    val replaced: Int = 0,
    val keptLocal: Int = 0,
    val forked: Int = 0,
    val versionsMerged: Int = 0,
    val skipped: Int = 0,
) {
    fun summary(): String =
        "导入 $imported，替换 $replaced，保留本地 $keptLocal，并存 $forked，合并版本 $versionsMerged，跳过 $skipped"
}

/** fork 产生的 id 映射：原对话 id → (新对话 id, 旧节点 id → 新节点 id)。 */
private data class ForkMapping(
    val forkConversationId: String,
    val nodeIdMap: Map<String, String>,
)

class MergeDecisionApplier(
    private val appDatabase: AppDatabase,
    private val workspaceManager: WorkspaceManager,
) {
    /**
     * @param validAssistantIds 合并设置后生效的助手 id 集合（本地 + 用户选择导入的）
     * @param defaultAssistantId 兜底助手 id（当前默认助手）
     * @param validFolderIds 本地文件夹 id 集合
     */
    suspend fun apply(
        stagedDatabase: File,
        plan: MergePlan,
        validAssistantIds: Set<String>,
        defaultAssistantId: String,
        validFolderIds: Set<String>,
        onProgress: (Long, Long, String) -> Unit = { _, _, _ -> },
    ): MergeApplyResult = withContext(Dispatchers.IO) {
        require(stagedDatabase.exists() && stagedDatabase.length() > 0L) { "合并数据库不存在或为空" }

        SQLiteDatabase.openDatabase(
            stagedDatabase.absolutePath,
            null,
            SQLiteDatabase.OPEN_READONLY,
        ).use { source ->
            val importedConversations = readConversations(source)
            val importedMemories = readMemories(source)
            val importedFavorites = readFavorites(source)
            val importedWorkspaces = readWorkspaces(source)
            val decisions = plan.conversations.associateBy { it.conversationId }

            var imported = 0
            var replaced = 0
            var keptLocal = 0
            var forked = 0
            var versionsMerged = 0
            var skipped = 0
            val forkMappings = mutableMapOf<String, ForkMapping>()

            // 事务前预读 MERGE_VERSIONS 决策所需的本地数据（避免在事务内调 suspend Room DAO，
            // 非 WAL 模式下读会等事务锁 → 死锁）。
            val mergeLocalData = mutableMapOf<String, Pair<Long, List<MessageNodeEntity>>>()
            importedConversations.forEach { conv ->
                if (decisions[conv.entity.id]?.decision == ConversationMergeDecision.MERGE_VERSIONS) {
                    val localEntity = appDatabase.conversationDao().getConversationById(conv.entity.id)
                    val localNodes = appDatabase.messageNodeDao().getNodesOfConversation(conv.entity.id)
                    mergeLocalData[conv.entity.id] = (localEntity?.updateAt ?: 0L) to localNodes
                }
            }

            val target = appDatabase.openHelper.writableDatabase
            target.beginTransaction()
            try {
                importedConversations.forEachIndexed { index, importedConv ->
                    val item = decisions[importedConv.entity.id]
                    val decision = item?.decision ?: ConversationMergeDecision.IMPORT
                    val entity = sanitizeEntity(importedConv.entity, validAssistantIds, defaultAssistantId, validFolderIds)
                    when (decision) {
                        ConversationMergeDecision.IMPORT -> {
                            writeConversation(target, entity, importedConv.nodes, remapNodeIds = false)
                            imported++
                        }

                        ConversationMergeDecision.SKIP -> {
                            skipped++
                        }

                        ConversationMergeDecision.KEEP_LOCAL -> {
                            // SAME 关系不计入统计（无差异对话不应虚增数字）
                            if (item?.relation != ConversationMergeRelation.SAME) keptLocal++
                        }

                        ConversationMergeDecision.USE_BACKUP -> {
                            writeConversation(target, entity, importedConv.nodes, remapNodeIds = false)
                            replaced++
                        }

                        ConversationMergeDecision.KEEP_BOTH -> {
                            val mapping = writeForkConversation(target, entity, importedConv.nodes)
                            forkMappings[importedConv.entity.id] = mapping
                            forked++
                        }

                        ConversationMergeDecision.MERGE_VERSIONS -> {
                            val merged = mergeVersionsWithLocal(importedConv, mergeLocalData[importedConv.entity.id])
                            if (merged != null) {
                                writeConversation(target, entity, merged, remapNodeIds = false)
                                versionsMerged++
                            } else {
                                keptLocal++
                            }
                        }
                    }
                    onProgress(index + 1L, importedConversations.size.toLong(), importedConv.entity.title)
                }

                // P2：favorites 导入，fork 对话的引用同步 remap
                importFavorites(target, importedFavorites, forkMappings)
                mergeMemories(target, importedMemories)
                mergeWorkspaces(target, importedWorkspaces)
                target.setTransactionSuccessful()
            } finally {
                target.endTransaction()
            }

            repairWorkspaceDirectories(importedWorkspaces)
            MergeApplyResult(
                imported = imported,
                replaced = replaced,
                keptLocal = keptLocal,
                forked = forked,
                versionsMerged = versionsMerged,
                skipped = skipped,
            )
        }
    }

    /** P3：悬挂引用兜底——助手不存在则挂到默认助手，文件夹不存在则移出。 */
    private fun sanitizeEntity(
        entity: ConversationRow,
        validAssistantIds: Set<String>,
        defaultAssistantId: String,
        validFolderIds: Set<String>,
    ): ConversationRow {
        var fixed = entity
        if (fixed.assistantId !in validAssistantIds) {
            Log.w(TAG, "对话 ${fixed.id} 的助手 ${fixed.assistantId} 不存在，挂到默认助手")
            fixed = fixed.copy(assistantId = defaultAssistantId)
        }
        if (fixed.folderId.isNotEmpty() && fixed.folderId !in validFolderIds) {
            fixed = fixed.copy(folderId = "")
        }
        return fixed
    }

    /** MERGE_VERSIONS：用事务前预读的本地节点做版本并集；结构已变则返回 null（降级保留本地）。 */
    private fun mergeVersionsWithLocal(
        importedConv: ImportedConversation,
        localData: Pair<Long, List<MessageNodeEntity>>?,
    ): List<ImportedNode>? {
        if (localData == null) return null
        val (localUpdateAt, localNodes) = localData
        val localById = localNodes.associateBy { it.id }
        val backupIds = importedConv.nodes.map { it.id }.toSet()
        if (localNodes.map { it.id }.toSet() != backupIds) {
            Log.w(TAG, "MERGE_VERSIONS: 本地结构已变化，降级保留本地 conv=${importedConv.entity.id}")
            return null
        }
        val backupNewer = importedConv.entity.updateAt > localUpdateAt
        return importedConv.nodes.map { backupNode ->
            val localNode = localById.getValue(backupNode.id)
            val merged = NodeVersionMerger.merge(
                localMessagesJson = localNode.messages,
                localSelectIndex = localNode.selectIndex,
                backupMessagesJson = backupNode.messages,
                backupSelectIndex = backupNode.selectIndex,
                preferBackupSelection = backupNewer,
            )
            if (merged == null) {
                backupNode
            } else {
                backupNode.copy(messages = merged.first, selectIndex = merged.second)
            }
        }
    }

    // ------------------------------------------------------------------ fork

    /** KEEP_BOTH：写入 fork 对话，节点全量换新 id，返回映射供 favorites remap。 */
    private fun writeForkConversation(
        target: SupportSQLiteDatabase,
        entity: ConversationRow,
        nodes: List<ImportedNode>,
    ): ForkMapping {
        val forkId = Uuid.random().toString()
        val forkTitle = nextForkTitle(target, entity.title)
        val forkEntity = entity.copy(id = forkId, title = forkTitle)
        insertConversationRow(target, forkEntity)
        val nodeIdMap = mutableMapOf<String, String>()
        nodes.forEach { node ->
            val newNodeId = Uuid.random().toString()
            nodeIdMap[node.id] = newNodeId
            insertNodeRow(target, node.copy(id = newNodeId, conversationId = forkId))
        }
        Log.i(TAG, "KEEP_BOTH: fork ${entity.id} -> $forkId ($forkTitle)")
        return ForkMapping(forkId, nodeIdMap)
    }

    // ------------------------------------------------------------------ favorites（P2）

    private fun importFavorites(
        target: SupportSQLiteDatabase,
        favorites: List<ImportedFavorite>,
        forkMappings: Map<String, ForkMapping>,
    ) {
        favorites.forEach { favorite ->
            var refKey = favorite.refKey
            if (favorite.type == "node") {
                val parts = refKey.split(':')
                if (parts.size == 3) {
                    val mapping = forkMappings[parts[1]]
                    if (mapping != null) {
                        val newNodeId = mapping.nodeIdMap[parts[2]]
                        if (newNodeId == null) return@forEach // fork 里无此节点，丢弃
                        refKey = parts[0] + ":" + mapping.forkConversationId + ":" + newNodeId
                    }
                }
            }
            if (!isFavoriteReferencePresent(target, favorite.type, refKey)) return@forEach
            target.query(
                "SELECT 1 FROM favorites WHERE ref_key = ? LIMIT 1",
                arrayOf(refKey),
            ).use { existing ->
                if (existing.moveToFirst()) return@forEach
            }
            val values = ContentValues().apply {
                put("id", favorite.id)
                put("type", favorite.type)
                put("ref_key", refKey)
                put("ref_json", favorite.refJson)
                put("snapshot_json", favorite.snapshotJson)
                favorite.metaJson?.let { put("meta_json", it) } ?: putNull("meta_json")
                put("created_at", favorite.createdAt)
                put("updated_at", favorite.updatedAt)
            }
            if (target.insert("favorites", SQLiteDatabase.CONFLICT_IGNORE, values) == -1L) {
                values.put("id", favorite.id + "-" + Uuid.random().toString())
                target.insert("favorites", SQLiteDatabase.CONFLICT_IGNORE, values)
            }
        }
    }

    private fun isFavoriteReferencePresent(
        target: SupportSQLiteDatabase,
        type: String,
        refKey: String,
    ): Boolean {
        if (type != "node") return true
        val parts = refKey.split(':')
        if (parts.size != 3) return false
        val conversationId = parts[1]
        val nodeId = parts[2]
        target.query(
            "SELECT 1 FROM ConversationEntity WHERE id = ? LIMIT 1",
            arrayOf(conversationId),
        ).use { conversation ->
            if (!conversation.moveToFirst()) return false
        }
        target.query(
            "SELECT 1 FROM message_node WHERE id = ? AND conversation_id = ? LIMIT 1",
            arrayOf(nodeId, conversationId),
        ).use { node ->
            return node.moveToFirst()
        }
    }

    // ------------------------------------------------------------------ memories / workspaces

    private fun mergeMemories(target: SupportSQLiteDatabase, memories: List<ImportedMemory>) {
        memories.forEach { memory ->
            target.query(
                "SELECT 1 FROM MemoryEntity WHERE assistant_id = ? AND content = ? LIMIT 1",
                arrayOf(memory.assistantId, memory.content),
            ).use { existing ->
                if (existing.moveToFirst()) return@forEach
            }
            target.insert(
                "MemoryEntity",
                SQLiteDatabase.CONFLICT_IGNORE,
                ContentValues().apply {
                    put("assistant_id", memory.assistantId)
                    put("content", memory.content)
                },
            )
        }
    }

    private fun mergeWorkspaces(target: SupportSQLiteDatabase, workspaces: List<WorkspaceRow>) {
        workspaces.forEach { workspace ->
            val values = ContentValues().apply {
                put("id", workspace.id)
                put("name", workspace.name)
                put("root", workspace.root)
                put("created_at", workspace.createdAt)
                put("updated_at", workspace.updatedAt)
                workspace.lastAccessAt?.let { put("last_access_at", it) } ?: putNull("last_access_at")
                put("tool_approvals", workspace.toolApprovals)
            }
            target.insert("workspaces", SQLiteDatabase.CONFLICT_REPLACE, values)
        }
    }

    private suspend fun repairWorkspaceDirectories(workspaces: List<WorkspaceRow>) {
        workspaces.forEach { workspace ->
            runCatching { workspaceManager.ensureWorkspace(workspace.root) }
                .onFailure { Log.w(TAG, "无法修复工作区目录 ${workspace.id}", it) }
        }
    }

    // ------------------------------------------------------------------ 读取 staged 库

    private fun readConversations(source: SQLiteDatabase): List<ImportedConversation> {
        if (!tableExists(source, "ConversationEntity")) return emptyList()
        return source.query("ConversationEntity", null, null, null, null, null, null).use { cursor ->
            val result = mutableListOf<ImportedConversation>()
            while (cursor.moveToNext()) {
                val id = cursor.string("id") ?: continue
                result += ImportedConversation(
                    entity = ConversationRow(
                        id = id,
                        assistantId = cursor.string("assistant_id").orEmpty(),
                        title = cursor.string("title").orEmpty(),
                        nodes = cursor.string("nodes") ?: "[]",
                        createAt = cursor.long("create_at"),
                        updateAt = cursor.long("update_at"),
                        chatSuggestions = cursor.string("suggestions") ?: "[]",
                        isPinned = cursor.bool("is_pinned"),
                        customSystemPrompt = cursor.string("custom_system_prompt").orEmpty(),
                        modeInjectionIds = cursor.string("mode_injection_ids") ?: "[]",
                        lorebookIds = cursor.string("lorebook_ids") ?: "[]",
                        workspaceCwd = cursor.string("workspace_cwd").orEmpty(),
                        folderId = cursor.string("folder_id").orEmpty(),
                        chatModelId = cursor.string("chat_model_id").orEmpty(),
                    ),
                    nodes = readNodes(source, id),
                )
            }
            result
        }
    }

    private fun readNodes(source: SQLiteDatabase, conversationId: String): List<ImportedNode> {
        if (!tableExists(source, "message_node")) return emptyList()
        return source.query(
            "message_node", null, "conversation_id = ?",
            arrayOf(conversationId), null, null, "node_index ASC",
        ).use { cursor ->
            val result = mutableListOf<ImportedNode>()
            while (cursor.moveToNext()) {
                val messages = cursor.string("messages") ?: continue
                result += ImportedNode(
                    id = cursor.string("id") ?: Uuid.random().toString(),
                    conversationId = conversationId,
                    nodeIndex = cursor.int("node_index"),
                    messages = messages,
                    selectIndex = cursor.int("select_index"),
                )
            }
            result
        }
    }

    private fun readMemories(source: SQLiteDatabase): List<ImportedMemory> {
        if (!tableExists(source, "MemoryEntity")) return emptyList()
        return source.query("MemoryEntity", null, null, null, null, null, null).use { cursor ->
            val result = mutableListOf<ImportedMemory>()
            while (cursor.moveToNext()) {
                val assistantId = cursor.string("assistant_id") ?: continue
                result += ImportedMemory(
                    assistantId = assistantId,
                    content = cursor.string("content").orEmpty(),
                )
            }
            result
        }
    }

    private fun readFavorites(source: SQLiteDatabase): List<ImportedFavorite> {
        if (!tableExists(source, "favorites")) return emptyList()
        return source.query("favorites", null, null, null, null, null, null).use { cursor ->
            val result = mutableListOf<ImportedFavorite>()
            while (cursor.moveToNext()) {
                result += ImportedFavorite(
                    id = cursor.string("id") ?: continue,
                    type = cursor.string("type").orEmpty(),
                    refKey = cursor.string("ref_key") ?: continue,
                    refJson = cursor.string("ref_json").orEmpty(),
                    snapshotJson = cursor.string("snapshot_json").orEmpty(),
                    metaJson = cursor.string("meta_json"),
                    createdAt = cursor.long("created_at"),
                    updatedAt = cursor.long("updated_at"),
                )
            }
            result
        }
    }

    private fun readWorkspaces(source: SQLiteDatabase): List<WorkspaceRow> {
        if (!tableExists(source, "workspaces")) return emptyList()
        return source.query("workspaces", null, null, null, null, null, null).use { cursor ->
            val result = mutableListOf<WorkspaceRow>()
            while (cursor.moveToNext()) {
                val root = cursor.string("root") ?: continue
                if (!root.matches(ROOT_NAME_REGEX)) continue
                val row = WorkspaceRow(
                    id = cursor.string("id") ?: continue,
                    name = cursor.string("name").orEmpty().ifBlank { "Workspace" },
                    root = root,
                    createdAt = cursor.long("created_at"),
                    updatedAt = cursor.long("updated_at"),
                    lastAccessAt = cursor.longOrNull("last_access_at"),
                    toolApprovals = cursor.string("tool_approvals") ?: "{}",
                )
                result += row
            }
            result
        }
    }

    // ------------------------------------------------------------------ 写入

    private fun writeConversation(
        target: SupportSQLiteDatabase,
        entity: ConversationRow,
        nodes: List<ImportedNode>,
        remapNodeIds: Boolean,
    ) {
        target.delete("message_node", "conversation_id = ?", arrayOf(entity.id))
        insertConversationRow(target, entity)
        nodes.forEach { node ->
            val row = if (remapNodeIds) {
                node.copy(id = Uuid.random().toString(), conversationId = entity.id)
            } else {
                node.copy(conversationId = entity.id)
            }
            insertNodeRow(target, row)
        }
    }

    private fun insertConversationRow(target: SupportSQLiteDatabase, entity: ConversationRow) {
        val values = ContentValues().apply {
            put("id", entity.id)
            put("assistant_id", entity.assistantId)
            put("title", entity.title)
            put("nodes", entity.nodes)
            put("create_at", entity.createAt)
            put("update_at", entity.updateAt)
            put("suggestions", entity.chatSuggestions)
            put("is_pinned", if (entity.isPinned) 1 else 0)
            put("custom_system_prompt", entity.customSystemPrompt)
            put("mode_injection_ids", entity.modeInjectionIds)
            put("lorebook_ids", entity.lorebookIds)
            put("workspace_cwd", entity.workspaceCwd)
            put("folder_id", entity.folderId)
            put("chat_model_id", entity.chatModelId)
        }
        target.insert("ConversationEntity", SQLiteDatabase.CONFLICT_REPLACE, values)
    }

    private fun insertNodeRow(target: SupportSQLiteDatabase, node: ImportedNode) {
        val values = ContentValues().apply {
            put("id", node.id)
            put("conversation_id", node.conversationId)
            put("node_index", node.nodeIndex)
            put("messages", node.messages)
            put("select_index", node.selectIndex)
        }
        target.insert("message_node", SQLiteDatabase.CONFLICT_REPLACE, values)
    }

    private fun nextForkTitle(target: SupportSQLiteDatabase, baseTitle: String): String {
        val base = baseTitle.ifBlank { "导入对话" }
        var index = 1
        while (true) {
            val candidate = base + "+" + index
            target.query(
                "SELECT 1 FROM ConversationEntity WHERE title = ? LIMIT 1",
                arrayOf(candidate),
            ).use {
                if (!it.moveToFirst()) return candidate
            }
            index++
        }
    }

    private fun tableExists(db: SQLiteDatabase, table: String): Boolean =
        db.rawQuery(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND lower(name) = lower(?) LIMIT 1",
            arrayOf(table),
        ).use { it.moveToFirst() }

    // ------------------------------------------------------------------ 行模型与游标扩展

    data class ConversationRow(
        val id: String,
        val assistantId: String,
        val title: String,
        val nodes: String,
        val createAt: Long,
        val updateAt: Long,
        val chatSuggestions: String,
        val isPinned: Boolean,
        val customSystemPrompt: String,
        val modeInjectionIds: String,
        val lorebookIds: String,
        val workspaceCwd: String,
        val folderId: String,
        val chatModelId: String,
    )

    data class ImportedNode(
        val id: String,
        val conversationId: String,
        val nodeIndex: Int,
        val messages: String,
        val selectIndex: Int,
    )

    data class ImportedConversation(
        val entity: ConversationRow,
        val nodes: List<ImportedNode>,
    )

    data class ImportedMemory(
        val assistantId: String,
        val content: String,
    )

    data class ImportedFavorite(
        val id: String,
        val type: String,
        val refKey: String,
        val refJson: String,
        val snapshotJson: String,
        val metaJson: String?,
        val createdAt: Long,
        val updatedAt: Long,
    )

    data class WorkspaceRow(
        val id: String,
        val name: String,
        val root: String,
        val createdAt: Long,
        val updatedAt: Long,
        val lastAccessAt: Long?,
        val toolApprovals: String,
    )

    private fun Cursor.string(column: String): String? =
        getColumnIndex(column).takeIf { it >= 0 && !isNull(it) }?.let(::getString)

    private fun Cursor.long(column: String): Long = string(column)?.toLongOrNull() ?: 0L

    private fun Cursor.longOrNull(column: String): Long? = string(column)?.toLongOrNull()

    private fun Cursor.int(column: String): Int = string(column)?.toIntOrNull() ?: 0

    private fun Cursor.bool(column: String): Boolean = long(column) != 0L

    companion object {
        private const val TAG = "MergeDecisionApplier"
        private val ROOT_NAME_REGEX = Regex("[A-Za-z0-9._-]+")
    }
}
'''

TEST_KT = r'''// [batch153] 备份合并改造：节点版本合并器单元测试
package me.rerere.rikkahub.data.sync.merge

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class NodeVersionMergerTest {

    private fun node(messagesJson: String) = messagesJson

    @Test
    fun unionKeepsLocalOrderAndAppendsBackupOnlyVersions() {
        val local = node("""[{"id":"m1"},{"id":"m2"}]""")
        val backup = node("""[{"id":"m1"},{"id":"m3"}]""")
        val result = NodeVersionMerger.merge(local, 0, backup, 1, preferBackupSelection = false)
        assertNotNull(result)
        val (json, select) = result!!
        assertTrue(json.indexOf("m1") < json.indexOf("m2"))
        assertTrue(json.indexOf("m2") < json.indexOf("m3"))
        assertEquals(3, json.split("id").size - 1)
        assertEquals(0, select)
    }

    @Test
    fun backupSelectionFollowsSelectedMessageId() {
        val local = node("""[{"id":"m1"},{"id":"m2"}]""")
        val backup = node("""[{"id":"m1"},{"id":"m3"}]""")
        // 备份选中 m3（index 1）；合并后 m3 在 index 2
        val result = NodeVersionMerger.merge(local, 0, backup, 1, preferBackupSelection = true)
        assertNotNull(result)
        assertEquals(2, result!!.second)
    }

    @Test
    fun identicalArraysKeepLocalSelection() {
        val local = node("""[{"id":"m1"},{"id":"m2"}]""")
        val result = NodeVersionMerger.merge(local, 1, local, 0, preferBackupSelection = false)
        assertNotNull(result)
        assertEquals(1, result!!.second)
    }

    @Test
    fun emptyLocalUsesBackup() {
        val backup = node("""[{"id":"m1"}]""")
        val result = NodeVersionMerger.merge("[]", 0, backup, 0, preferBackupSelection = true)
        assertNotNull(result)
        assertEquals(backup, result!!.first)
        assertEquals(0, result.second)
    }

    @Test
    fun malformedJsonReturnsNull() {
        assertNull(NodeVersionMerger.merge("not-json", 0, "[]", 0, preferBackupSelection = false))
    }

    @Test
    fun selectionOutOfRangeIsClamped() {
        val local = node("""[{"id":"m1"}]""")
        val backup = node("""[{"id":"m2"}]""")
        val result = NodeVersionMerger.merge(local, 99, backup, 0, preferBackupSelection = false)
        assertNotNull(result)
        assertEquals(1, result!!.second) // clamp 到 merged.size-1 = 1
    }
}
'''

REQUIRED_SNIPPETS = (
    (MERGER_PATH, "object NodeVersionMerger"),
    (APPLIER_PATH, "class MergeDecisionApplier"),
    (APPLIER_PATH, "writeForkConversation"),
    (APPLIER_PATH, "importFavorites"),
    (TEST_PATH, "class NodeVersionMergerTest"),
)


def fail(msg):
    print("::error::" + msg)
    sys.exit(1)


def write_new_file(path, content):
    if os.path.exists(path):
        with io.open(path, "r", encoding="utf-8") as f:
            existing = f.read()
        if MARK in existing:
            print("batch153: already applied, skip " + path)
            return
        fail("batch153: target exists without mark :: " + path)
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    try:
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as exc:
        fail("batch153: write failed :: " + path + " :: " + str(exc))
    print("batch153: wrote " + path)


def verify_file(path, needle):
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as exc:
        fail("batch153: verify read failed :: " + path + " :: " + str(exc))
    if needle not in content:
        fail("batch153: verify failed, missing " + needle + " in " + path)
    if MARK not in content:
        fail("batch153: verify failed, missing mark in " + path)


def main():
    write_new_file(MERGER_PATH, MERGER_KT)
    write_new_file(APPLIER_PATH, APPLIER_KT)
    write_new_file(TEST_PATH, TEST_KT)
    for path, needle in REQUIRED_SNIPPETS:
        verify_file(path, needle)
    print("batch153: node version merger + decision applier + tests written")


if __name__ == "__main__":
    main()

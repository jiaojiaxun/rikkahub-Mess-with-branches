package me.rerere.rikkahub.data.sync.webdav

import android.content.ContentValues
import android.database.Cursor
import android.database.sqlite.SQLiteDatabase
import android.util.Log
import androidx.sqlite.db.SupportSQLiteDatabase
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import me.rerere.rikkahub.data.db.AppDatabase
import me.rerere.rikkahub.data.db.entity.ConversationEntity
import me.rerere.rikkahub.data.db.entity.MessageNodeEntity
import me.rerere.rikkahub.data.db.entity.WorkspaceEntity
import me.rerere.workspace.WorkspaceManager
import java.io.File
import kotlin.uuid.Uuid

/**
 * Applies a staged database to the live Room database without replacing the live file.
 *
 * The merger deliberately works on the two tables that define a conversation rather than
 * copying only ConversationEntity: message_node is the actual history payload. A common prefix
 * means the backup is simply newer/older; incompatible content at the same node is a fork and is
 * retained under a new conversation and node IDs.
 */
class BackupDatabaseMerger(
    private val appDatabase: AppDatabase,
    private val workspaceManager: WorkspaceManager,
) {
    suspend fun merge(
        stagedDatabase: File,
        onProgress: (Long, Long, String) -> Unit = { _, _, _ -> },
    ) = withContext(Dispatchers.IO) {
        if (!stagedDatabase.exists() || stagedDatabase.length() == 0L) {
            throw IllegalArgumentException("合并数据库不存在或为空")
        }

        SQLiteDatabase.openDatabase(
            stagedDatabase.absolutePath,
            null,
            SQLiteDatabase.OPEN_READONLY,
        ).use { source ->
            val importedConversations = readConversations(source)
            val importedWorkspaces = readWorkspaces(source)
            val importedMemories = readMemories(source)
            val importedFavorites = readFavorites(source)
            val currentConversations = appDatabase.conversationDao().getAllIds().associateWith { id ->
                appDatabase.conversationDao().getConversationById(id)
            }.filterValues { it != null }.mapValues { it.value!! }
            val currentNodes = currentConversations.keys.associateWith { id ->
                appDatabase.messageNodeDao().getNodesOfConversation(id)
            }

            val target = appDatabase.openHelper.writableDatabase
            target.beginTransaction()
            try {
                importedConversations.forEachIndexed { index, imported ->
                    val current = currentConversations[imported.entity.id]
                    val currentConversationNodes = currentNodes[imported.entity.id].orEmpty()
                    when {
                        current == null -> {
                            writeConversation(
                                target = target,
                                entity = imported.entity,
                                nodes = imported.nodes,
                                remapNodeIds = false,
                            )
                        }

                        nodesEqual(currentConversationNodes, imported.nodes) -> {
                            if (imported.entity.updateAt > current.updateAt) {
                                writeConversation(target, imported.entity, imported.nodes, remapNodeIds = false)
                            }
                        }

                        isPrefixLocalToImported(currentConversationNodes, imported.nodes) -> {
                            // The backup contains only appended history: it is the newer branch.
                            writeConversation(target, imported.entity, imported.nodes, remapNodeIds = false)
                        }

                        isPrefixImportedToLocal(imported.nodes, currentConversationNodes) -> {
                            // The local branch already contains everything in the backup.
                        }

                        else -> {
                            val forkId = Uuid.random().toString()
                            val forkTitle = nextForkTitle(target, imported.entity.title)
                            writeConversation(
                                target = target,
                                entity = imported.entity.copy(id = forkId, title = forkTitle),
                                nodes = imported.nodes,
                                remapNodeIds = true,
                            )
                            Log.i(TAG, "Created fork conversation $forkId from ${imported.entity.id}")
                        }
                    }
                    onProgress(index + 1L, importedConversations.size.toLong(), imported.entity.title)
                }

                importedWorkspaces.forEach { workspace ->
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
                mergeMemories(target, importedMemories)
                mergeFavorites(target, importedFavorites)
                target.setTransactionSuccessful()
            } finally {
                target.endTransaction()
            }

            repairWorkspaceDirectories(importedWorkspaces)
        }
    }

    private fun readConversations(source: SQLiteDatabase): List<ImportedConversation> {
        if (!tableExists(source, "ConversationEntity")) return emptyList()
        return source.query("ConversationEntity", null, null, null, null, null, null).use { cursor ->
            val result = mutableListOf<ImportedConversation>()
            while (cursor.moveToNext()) {
                val id = cursor.string("id") ?: continue
                val nodes = readNodes(source, id)
                result += ImportedConversation(
                    entity = ConversationEntity(
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
                    nodes = nodes,
                )
            }
            result
        }
    }

    private fun readNodes(source: SQLiteDatabase, conversationId: String): List<ImportedNode> {
        if (!tableExists(source, "message_node")) return emptyList()
        return source.query(
            "message_node",
            null,
            "conversation_id = ?",
            arrayOf(conversationId),
            null,
            null,
            "node_index ASC",
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

    private fun readWorkspaces(source: SQLiteDatabase): List<WorkspaceEntity> {
        if (!tableExists(source, "workspaces")) return emptyList()
        return source.query("workspaces", null, null, null, null, null, null).use { cursor ->
            val result = mutableListOf<WorkspaceEntity>()
            while (cursor.moveToNext()) {
                val root = cursor.string("root") ?: continue
                if (!root.matches(ROOT_NAME_REGEX)) continue
                result += WorkspaceEntity(
                    id = cursor.string("id") ?: continue,
                    name = cursor.string("name").orEmpty().ifBlank { "Workspace" },
                    root = root,
                    createdAt = cursor.long("created_at"),
                    updatedAt = cursor.long("updated_at"),
                    lastAccessAt = cursor.longOrNull("last_access_at"),
                    toolApprovals = cursor.string("tool_approvals") ?: "{}",
                )
            }
            result
        }
    }

    private fun writeConversation(
        target: SupportSQLiteDatabase,
        entity: ConversationEntity,
        nodes: List<ImportedNode>,
        remapNodeIds: Boolean,
    ) {
        target.delete("message_node", "conversation_id = ?", arrayOf(entity.id))
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
        nodes.forEach { node ->
            val nodeValues = ContentValues().apply {
                put("id", if (remapNodeIds) Uuid.random().toString() else node.id)
                put("conversation_id", entity.id)
                put("node_index", node.nodeIndex)
                put("messages", node.messages)
                put("select_index", node.selectIndex)
            }
            target.insert("message_node", SQLiteDatabase.CONFLICT_REPLACE, nodeValues)
        }
    }

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

    private fun mergeFavorites(target: SupportSQLiteDatabase, favorites: List<ImportedFavorite>) {
        favorites.forEach { favorite ->
            if (!isFavoriteReferencePresent(target, favorite.type, favorite.refKey)) return@forEach
            target.query(
                "SELECT 1 FROM favorites WHERE ref_key = ? LIMIT 1",
                arrayOf(favorite.refKey),
            ).use { existing ->
                if (existing.moveToFirst()) return@forEach
            }
            val values = ContentValues().apply {
                put("id", favorite.id)
                put("type", favorite.type)
                put("ref_key", favorite.refKey)
                put("ref_json", favorite.refJson)
                put("snapshot_json", favorite.snapshotJson)
                favorite.metaJson?.let { put("meta_json", it) } ?: putNull("meta_json")
                put("created_at", favorite.createdAt)
                put("updated_at", favorite.updatedAt)
            }
            if (target.insert("favorites", SQLiteDatabase.CONFLICT_IGNORE, values) == -1L) {
                // `id` is normally the ref key, but older backups may use a colliding id.
                // Preserve the unique reference with a new local primary key.
                values.put("id", "${favorite.id}-${Uuid.random()}")
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

    private suspend fun repairWorkspaceDirectories(workspaces: List<WorkspaceEntity>) {
        workspaces.forEach { workspace ->
            runCatching {
                workspaceManager.ensureWorkspace(workspace.root)
            }.onFailure {
                Log.w(TAG, "Unable to repair workspace ${workspace.id}", it)
            }
        }
    }

    private fun nextForkTitle(target: SupportSQLiteDatabase, baseTitle: String): String {
        val base = baseTitle.ifBlank { "导入对话" }
        var index = 1
        while (true) {
            val candidate = "$base+$index"
            target.query("SELECT 1 FROM ConversationEntity WHERE title = ? LIMIT 1", arrayOf(candidate)).use {
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

    private fun nodesEqual(local: List<MessageNodeEntity>, imported: List<ImportedNode>): Boolean =
        local.size == imported.size && local.indices.all { index ->
            val left = local[index]
            val right = imported[index]
            left.nodeIndex == right.nodeIndex &&
                left.messages == right.messages &&
                left.selectIndex == right.selectIndex
        }

    private fun isPrefixLocalToImported(shorter: List<MessageNodeEntity>, longer: List<ImportedNode>): Boolean =
        shorter.size <= longer.size && shorter.indices.all { index ->
            val left = shorter[index]
            val right = longer[index]
            left.nodeIndex == right.nodeIndex &&
                left.messages == right.messages &&
                left.selectIndex == right.selectIndex
        }

    private fun isPrefixImportedToLocal(shorter: List<ImportedNode>, longer: List<MessageNodeEntity>): Boolean =
        shorter.size <= longer.size && shorter.indices.all { index ->
            val left = shorter[index]
            val right = longer[index]
            left.nodeIndex == right.nodeIndex &&
                left.messages == right.messages &&
                left.selectIndex == right.selectIndex
        }

    private data class ImportedMemory(
        val assistantId: String,
        val content: String,
    )

    private data class ImportedFavorite(
        val id: String,
        val type: String,
        val refKey: String,
        val refJson: String,
        val snapshotJson: String,
        val metaJson: String?,
        val createdAt: Long,
        val updatedAt: Long,
    )

    private data class ImportedConversation(
        val entity: ConversationEntity,
        val nodes: List<ImportedNode>,
    )

    private data class ImportedNode(
        val id: String,
        val conversationId: String,
        val nodeIndex: Int,
        val messages: String,
        val selectIndex: Int,
    )

    private fun Cursor.string(column: String): String? =
        getColumnIndex(column).takeIf { it >= 0 && !isNull(it) }?.let(::getString)

    private fun Cursor.long(column: String): Long = string(column)?.toLongOrNull() ?: 0L

    private fun Cursor.longOrNull(column: String): Long? = string(column)?.toLongOrNull()

    private fun Cursor.int(column: String): Int = string(column)?.toIntOrNull() ?: 0

    private fun Cursor.bool(column: String): Boolean = long(column) != 0L

    companion object {
        private const val TAG = "BackupDatabaseMerger"
        private val ROOT_NAME_REGEX = Regex("[A-Za-z0-9._-]+")
    }
}

// [batch151] 备份合并改造：对话关系判定
// 判定输入是"节点快照"（id + messages JSON + selectIndex），与数据库表结构解耦，
// 便于单元测试。对齐键是节点 id（UUID，全局稳定），不是列表位置——
// 位置对齐在"删除中间节点后 nodeIndex 重排"时会整体错位，id 对齐天然免疫。
package me.rerere.rikkahub.data.sync.merge

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull

/** 合并判定用的最小节点快照。 */
data class MergeNodeSnapshot(
    val nodeId: String,
    val nodeIndex: Int,
    val messagesJson: String,
    val selectIndex: Int,
)

/** 合并判定用的最小对话快照。 */
data class MergeConversationSnapshot(
    val id: String,
    val title: String,
    val updateAt: Long,
    val nodes: List<MergeNodeSnapshot>,
)

/** 关系判定的完整结果（含 UI 展示所需的统计数据）。 */
data class ConversationRelationResult(
    val relation: ConversationMergeRelation,
    val note: String,
    val localOnlyCount: Int,
    val backupOnlyCount: Int,
    val versionChangedNodeCount: Int,
)

object ConversationMergeAnalyzer {
    private val json = Json { ignoreUnknownKeys = true }
    private const val PREVIEW_MAX = 80

    /** 判定本地与备份对话的语义关系。local 为 null 表示本地没有该对话。 */
    fun analyze(
        local: MergeConversationSnapshot?,
        backup: MergeConversationSnapshot,
    ): ConversationRelationResult {
        if (local == null) {
            return ConversationRelationResult(
                relation = ConversationMergeRelation.NEW,
                note = "本地没有该对话",
                localOnlyCount = 0,
                backupOnlyCount = backup.nodes.size,
                versionChangedNodeCount = 0,
            )
        }
        if (local.nodes.isEmpty() && backup.nodes.isEmpty()) {
            return ConversationRelationResult(ConversationMergeRelation.SAME, "内容一致", 0, 0, 0)
        }
        if (local.nodes.isEmpty()) {
            return ConversationRelationResult(
                ConversationMergeRelation.BACKUP_AHEAD, "备份包含全部内容，本地为空",
                0, backup.nodes.size, 0,
            )
        }
        if (backup.nodes.isEmpty()) {
            return ConversationRelationResult(
                ConversationMergeRelation.LOCAL_AHEAD, "本地包含全部内容，备份为空",
                local.nodes.size, 0, 0,
            )
        }

        val localById = local.nodes.associateBy { it.nodeId }
        val backupById = backup.nodes.associateBy { it.nodeId }
        val commonIds = local.nodes.map { it.nodeId }.filter { backupById.containsKey(it) }.toSet()
        val localOnly = local.nodes.filter { it.nodeId !in backupById }
        val backupOnly = backup.nodes.filter { it.nodeId !in localById }

        var hasContentDiff = false
        var versionChanged = 0
        for (id in commonIds) {
            when (
                MessageSignatureParser.compareNodeMessages(
                    localById.getValue(id).messagesJson,
                    backupById.getValue(id).messagesJson,
                )
            ) {
                NodeContentRelation.EQUAL -> Unit
                NodeContentRelation.LOCAL_EXTRA_VERSIONS,
                NodeContentRelation.BACKUP_EXTRA_VERSIONS,
                -> versionChanged++
                NodeContentRelation.CONTENT_DIFF -> hasContentDiff = true
            }
        }

        if (commonIds.isEmpty()) {
            return ConversationRelationResult(
                ConversationMergeRelation.DIVERGED, "两边没有共同节点，内容完全不同",
                localOnly.size, backupOnly.size, versionChanged,
            )
        }
        if (hasContentDiff) {
            return ConversationRelationResult(
                ConversationMergeRelation.DIVERGED, "共有节点的消息内容不同",
                localOnly.size, backupOnly.size, versionChanged,
            )
        }

        // 尾部追加判定：独有节点必须全部位于"最后一个共有节点"之后。
        val lastCommonPosLocal = local.nodes.indexOfLast { it.nodeId in commonIds }
        val lastCommonPosBackup = backup.nodes.indexOfLast { it.nodeId in commonIds }
        val localOnlyIsTail = localOnly.all { node ->
            local.nodes.indexOfFirst { it.nodeId == node.nodeId } > lastCommonPosLocal
        }
        val backupOnlyIsTail = backupOnly.all { node ->
            backup.nodes.indexOfFirst { it.nodeId == node.nodeId } > lastCommonPosBackup
        }

        return when {
            localOnly.isEmpty() && backupOnly.isEmpty() -> {
                if (versionChanged > 0) {
                    ConversationRelationResult(
                        ConversationMergeRelation.VERSIONS_MODIFIED,
                        "$versionChanged 个节点的消息版本数发生变化",
                        0, 0, versionChanged,
                    )
                } else {
                    ConversationRelationResult(ConversationMergeRelation.SAME, "内容一致", 0, 0, 0)
                }
            }

            backupOnly.isNotEmpty() && localOnly.isEmpty() && backupOnlyIsTail && versionChanged == 0 ->
                ConversationRelationResult(
                    ConversationMergeRelation.BACKUP_AHEAD,
                    "备份多出 ${backupOnly.size} 个节点",
                    0, backupOnly.size, 0,
                )

            localOnly.isNotEmpty() && backupOnly.isEmpty() && localOnlyIsTail && versionChanged == 0 ->
                ConversationRelationResult(
                    ConversationMergeRelation.LOCAL_AHEAD,
                    "本地多出 ${localOnly.size} 个节点",
                    localOnly.size, 0, 0,
                )

            else -> ConversationRelationResult(
                ConversationMergeRelation.DIVERGED,
                buildString {
                    append("两边分别有新内容")
                    if (localOnly.isNotEmpty()) append("（本地独有 ${localOnly.size} 个节点")
                    if (backupOnly.isNotEmpty()) append("，备份独有 ${backupOnly.size} 个节点")
                    if (localOnly.isNotEmpty() || backupOnly.isNotEmpty()) append("）")
                    if (versionChanged > 0) append("，且 $versionChanged 个节点版本数变化")
                },
                localOnly.size, backupOnly.size, versionChanged,
            )
        }
    }

    /** 各关系的默认决策。DIVERGED 时按 updateAt 推荐较新一方。 */
    fun defaultDecision(
        relation: ConversationMergeRelation,
        local: MergeConversationSnapshot?,
        backup: MergeConversationSnapshot,
    ): ConversationMergeDecision = when (relation) {
        ConversationMergeRelation.NEW -> ConversationMergeDecision.IMPORT
        ConversationMergeRelation.SAME -> ConversationMergeDecision.KEEP_LOCAL
        ConversationMergeRelation.BACKUP_AHEAD -> ConversationMergeDecision.USE_BACKUP
        ConversationMergeRelation.LOCAL_AHEAD -> ConversationMergeDecision.KEEP_LOCAL
        ConversationMergeRelation.VERSIONS_MODIFIED -> ConversationMergeDecision.MERGE_VERSIONS
        ConversationMergeRelation.DIVERGED ->
            if (backup.updateAt > (local?.updateAt ?: 0L)) {
                ConversationMergeDecision.USE_BACKUP
            } else {
                ConversationMergeDecision.KEEP_LOCAL
            }
    }

    /** 生成一侧的展示摘要。 */
    fun summarize(snapshot: MergeConversationSnapshot): ConversationSideSummary {
        var messageCount = 0
        var firstUser: String? = null
        var lastText: String? = null
        snapshot.nodes.forEach { node ->
            val messages = parseArray(node.messagesJson)
            messageCount += messages.size
            val selected = messages.getOrNull(node.selectIndex) ?: messages.lastOrNull()
            if (firstUser == null) {
                for (msg in messages) {
                    val role = (msg["role"] as? JsonPrimitive)?.contentOrNull
                    if (role == "user" || role == "USER") {
                        val text = messageText(msg)
                        if (text.isNotBlank()) {
                            firstUser = text
                            break
                        }
                    }
                }
            }
            val tail = selected?.let(::messageText)
            if (!tail.isNullOrBlank()) lastText = tail
        }
        return ConversationSideSummary(
            nodeCount = snapshot.nodes.size,
            messageCount = messageCount,
            updateAt = snapshot.updateAt,
            firstUserMessagePreview = firstUser.orEmpty().take(PREVIEW_MAX),
            lastMessagePreview = lastText.orEmpty().take(PREVIEW_MAX),
        )
    }

    private fun parseArray(messagesJson: String): List<JsonObject> {
        val array = runCatching { json.parseToJsonElement(messagesJson) as? JsonArray }
            .getOrNull() ?: return emptyList()
        return array.mapNotNull { it as? JsonObject }
    }

    /** 取消息的第一个 text part 文本（预览用，忽略其余 part 类型）。 */
    private fun messageText(message: JsonObject): String {
        val parts = message["parts"] as? JsonArray ?: return ""
        for (part in parts) {
            val obj = part as? JsonObject ?: continue
            val text = (obj["text"] as? JsonPrimitive)?.contentOrNull
            if (!text.isNullOrBlank()) return text.replace('\n', ' ').trim()
        }
        return ""
    }
}

// [batch153] 备份合并改造：节点消息版本合并器（纯函数，可单测）
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

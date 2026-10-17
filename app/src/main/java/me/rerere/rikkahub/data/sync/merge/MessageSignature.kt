// [batch150] 备份合并改造：消息语义签名
// 核心思想：消息的"身份"是 UIMessage.id，"内容"是 role + parts。
// translation / usage / finishedAt / createdAt / modelId / annotations 属于运行期
// 可变元数据（翻译一条消息不应让对话被判分叉）；Tool part 的审批状态/输出同理。
// 比较前先把这些字段从 JSON 里剔除，再对剩余结构做规范化比较。
package me.rerere.rikkahub.data.sync.merge

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull

/** 单条消息的语义签名。normalizedJson 已剔除全部可变元数据字段。 */
data class MessageSignature(
    val id: String,
    val role: String,
    val normalizedJson: String,
)

/** 同一节点两侧消息列表的语义关系。 */
enum class NodeContentRelation {
    /** 消息列表逐项等价。 */
    EQUAL,

    /** 本地消息 id 集合是备份的超集（本地多了重生成版本），且共有消息内容一致。 */
    LOCAL_EXTRA_VERSIONS,

    /** 备份消息 id 集合是本地的超集，且共有消息内容一致。 */
    BACKUP_EXTRA_VERSIONS,

    /** 其他一切情况：共有 id 内容不同，或版本集合互不包含。 */
    CONTENT_DIFF,
}

object MessageSignatureParser {
    /** 消息级运行期可变字段：剔除后参与比较。 */
    private val MESSAGE_VOLATILE_KEYS = setOf(
        "translation",
        "usage",
        "finishedAt",
        "createdAt",
        "modelId",
        "annotations",
    )

    /** part 级运行期可变字段（工具审批状态/输出/执行时间戳等）。 */
    private val PART_VOLATILE_KEYS = setOf(
        "approvalState",
        "output",
        "executionStartedAt",
        "metadata",
    )

    private val json = Json { ignoreUnknownKeys = true }

    /** 解析 message_node.messages（JSON 数组）为签名列表；解析失败返回空列表。 */
    fun parse(messagesJson: String): List<MessageSignature> {
        val array = runCatching { json.parseToJsonElement(messagesJson) as? JsonArray }
            .getOrNull() ?: return emptyList()
        return array.mapNotNull { element ->
            val obj = element as? JsonObject ?: return@mapNotNull null
            val id = (obj["id"] as? JsonPrimitive)?.contentOrNull ?: return@mapNotNull null
            val role = (obj["role"] as? JsonPrimitive)?.contentOrNull ?: ""
            MessageSignature(id = id, role = role, normalizedJson = normalizeMessage(obj))
        }
    }

    /** 比较同一节点两侧的消息 JSON，给出语义关系。 */
    fun compareNodeMessages(localJson: String, backupJson: String): NodeContentRelation {
        val local = parse(localJson)
        val backup = parse(backupJson)
        if (local.size == backup.size && local.indices.all { local[it] == backup[it] }) {
            return NodeContentRelation.EQUAL
        }
        val localIds = local.map { it.id }.toSet()
        val backupIds = backup.map { it.id }.toSet()
        val commonIds = localIds.intersect(backupIds)
        val localById = local.associateBy { it.id }
        val backupById = backup.associateBy { it.id }
        val commonEqual = commonIds.all { localById[it] == backupById[it] }
        if (!commonEqual) return NodeContentRelation.CONTENT_DIFF
        return when {
            localIds.size > backupIds.size && localIds.containsAll(backupIds) ->
                NodeContentRelation.LOCAL_EXTRA_VERSIONS
            backupIds.size > localIds.size && backupIds.containsAll(localIds) ->
                NodeContentRelation.BACKUP_EXTRA_VERSIONS
            else -> NodeContentRelation.CONTENT_DIFF
        }
    }

    /** 剔除消息级可变字段，并对 parts 数组逐项剔除 part 级可变字段。 */
    internal fun normalizeMessage(element: JsonObject): String {
        val cleaned = LinkedHashMap<String, JsonElement>()
        for ((key, value) in element) {
            if (key in MESSAGE_VOLATILE_KEYS) continue
            if (key == "parts" && value is JsonArray) {
                cleaned[key] = JsonArray(
                    value.map { part -> (part as? JsonObject)?.let(::normalizePart) ?: part }
                )
            } else {
                cleaned[key] = value
            }
        }
        return JsonObject(cleaned).toString()
    }

    private fun normalizePart(element: JsonObject): JsonObject {
        val cleaned = LinkedHashMap<String, JsonElement>()
        for ((key, value) in element) {
            if (key in PART_VOLATILE_KEYS) continue
            cleaned[key] = value
        }
        return JsonObject(cleaned)
    }
}

#!/usr/bin/env python3
# batch150: 备份合并改造 1/10 —— 新增合并计划数据结构 + 消息语义签名比较 + 单元测试
# 背景: 旧 BackupDatabaseMerger 的 fork 判定对 messages JSON 字符串全等零容忍,
#       翻译/usage/selectIndex 等元数据差异都会误判为分叉(两个都保留)。
#       本批次新增"消息语义签名"(比较时忽略可变元数据字段), 作为差异确认合并的地基。
# 变更: 仅新增三个文件, 不修改任何现有文件。
#   1) app/.../data/sync/merge/MergePlan.kt            —— 合并计划全部数据结构
#   2) app/.../data/sync/merge/MessageSignature.kt     —— 消息语义签名解析与比较
#   3) app/src/test/.../merge/MessageSignatureTest.kt  —— 语义签名单元测试
# 幂等: 目标文件已存在且含 [batch150] 标记则跳过; 存在但无标记则 fail(防冲突)。

import io
import os
import sys

NL = chr(10)
MARK = "[batch150]"

MERGE_PLAN_PATH = "app/src/main/java/me/rerere/rikkahub/data/sync/merge/MergePlan.kt"
SIGNATURE_PATH = "app/src/main/java/me/rerere/rikkahub/data/sync/merge/MessageSignature.kt"
TEST_PATH = "app/src/test/java/me/rerere/rikkahub/data/sync/merge/MessageSignatureTest.kt"

MERGE_PLAN_KT = r'''// [batch150] 备份合并改造：合并计划数据结构
// 扫描阶段产出 MergePlan（只读），UI 逐项展示并由用户确认决策，
// 最后由 MergeDecisionApplier 按计划执行。本批次不修改任何旧合并逻辑。
package me.rerere.rikkahub.data.sync.merge

/** 对话在备份与本地之间的语义关系。 */
enum class ConversationMergeRelation {
    /** 本地没有该对话。 */
    NEW,

    /** 语义相同（消息身份与内容一致；翻译/用量/选中版本等元数据可能有差异）。 */
    SAME,

    /** 备份 = 本地 + 尾部追加（备份更新）。 */
    BACKUP_AHEAD,

    /** 本地 = 备份 + 尾部追加（本地更新）。 */
    LOCAL_AHEAD,

    /** 共有节点上的消息版本集合发生变化（如重生成新增版本），可自动合并版本数组。 */
    VERSIONS_MODIFIED,

    /** 真分叉：两边存在互不包含的内容差异。 */
    DIVERGED,
}

/** 用户对单个对话差异的决策。 */
enum class ConversationMergeDecision {
    /** 用备份版本替换本地。 */
    USE_BACKUP,

    /** 保留本地版本，丢弃备份中的该对话。 */
    KEEP_LOCAL,

    /** 两个都保留：备份版本另存为新对话。 */
    KEEP_BOTH,

    /** 仅 NEW：导入该对话。 */
    IMPORT,

    /** 仅 NEW：不导入。 */
    SKIP,

    /** 仅 VERSIONS_MODIFIED：合并消息版本数组（并集，选中版本取较新方）。 */
    MERGE_VERSIONS,
}

/** 对话一侧（本地或备份）的展示摘要。 */
data class ConversationSideSummary(
    val nodeCount: Int,
    val messageCount: Int,
    val updateAt: Long,
    val firstUserMessagePreview: String,
    val lastMessagePreview: String,
)

/** 单个对话的合并项。 */
data class ConversationMergeItem(
    val conversationId: String,
    val title: String,
    val relation: ConversationMergeRelation,
    /** 本地摘要；NEW 时为 null。 */
    val local: ConversationSideSummary?,
    val backup: ConversationSideSummary,
    val defaultDecision: ConversationMergeDecision,
    /** 人类可读的关系说明（展示用）。 */
    val relationNote: String,
    val decision: ConversationMergeDecision = defaultDecision,
)

/** 设置条目类别。 */
enum class SettingsItemCategory { PROVIDER, ASSISTANT, MCP_SERVER }

/** 设置条目差异类型。 */
enum class SettingsItemKind {
    /** 备份有、本地没有（且本地未删除过）→ 询问是否导入。 */
    ADDED_IN_BACKUP,

    /** 备份有、本地删除标记里有 → 询问是否恢复。 */
    DELETED_LOCALLY,

    /** 本地有、备份删除标记里有 → 询问是否删除本地。 */
    REMOVED_IN_BACKUP,

    /** 两边都有但内容不同 → 询问用哪边。 */
    MODIFIED,
}

/** 设置条目决策。 */
enum class SettingsItemDecision { IMPORT, SKIP, DELETE, KEEP, USE_BACKUP, KEEP_LOCAL }

/** 单个设置条目的差异。 */
data class SettingsItemDiff(
    val category: SettingsItemCategory,
    val id: String,
    val displayName: String,
    /** 差异摘要（如 baseUrl、模型数量、提示词预览）。 */
    val detail: String,
    val kind: SettingsItemKind,
    val defaultDecision: SettingsItemDecision,
    val decision: SettingsItemDecision = defaultDecision,
)

/** 标量偏好字段差异（providers/assistants/mcpServers 之外的字段）。 */
data class ScalarFieldDiff(
    val fieldKey: String,
    val displayName: String,
    val localValuePreview: String,
    val backupValuePreview: String,
    /** 用户勾选：采用备份值覆盖本地。默认 false = 保留本地。 */
    val adoptBackup: Boolean = false,
)

/** 设置差异总表。 */
data class SettingsMergeDiff(
    val items: List<SettingsItemDiff>,
    val scalarFields: List<ScalarFieldDiff>,
)

/** 合并计划（扫描产物，只读；用户决策通过 copy 更新条目）。 */
data class MergePlan(
    val conversations: List<ConversationMergeItem>,
    val settings: SettingsMergeDiff?,
    val memoriesToAdd: Int,
    val favoritesToAdd: Int,
    val workspacesToMerge: Int,
) {
    /** 需要用户拍板的分叉对话数量。 */
    val divergedCount: Int
        get() = conversations.count { it.relation == ConversationMergeRelation.DIVERGED }

    /** 有任何差异或新增内容时为 true；false 表示备份与本地语义等价。 */
    val hasChanges: Boolean
        get() = conversations.any { it.relation != ConversationMergeRelation.SAME } ||
            (settings?.items?.isNotEmpty() == true) ||
            (settings?.scalarFields?.isNotEmpty() == true) ||
            memoriesToAdd > 0 || favoritesToAdd > 0 || workspacesToMerge > 0
}
'''

MESSAGE_SIGNATURE_KT = r'''// [batch150] 备份合并改造：消息语义签名
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
'''

MESSAGE_SIGNATURE_TEST_KT = r'''// [batch150] 备份合并改造：消息语义签名单元测试
package me.rerere.rikkahub.data.sync.merge

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class MessageSignatureTest {

    @Test
    fun translationDifferenceIsEquivalent() {
        val withTranslation = """
            [{"id":"m1","role":"user","parts":[{"type":"text","text":"hi"}],"translation":"你好"}]
        """.trimIndent()
        val without = """
            [{"id":"m1","role":"user","parts":[{"type":"text","text":"hi"}]}]
        """.trimIndent()
        assertEquals(
            MessageSignatureParser.parse(withTranslation),
            MessageSignatureParser.parse(without),
        )
    }

    @Test
    fun usageAndFinishedAtDifferenceIsEquivalent() {
        val a = """
            [{"id":"m1","role":"assistant","parts":[{"type":"text","text":"ok"}],
              "usage":{"promptTokens":10,"completionTokens":5},"finishedAt":"2026-01-01T00:00:01"}]
        """.trimIndent()
        val b = """
            [{"id":"m1","role":"assistant","parts":[{"type":"text","text":"ok"}]}]
        """.trimIndent()
        assertEquals(MessageSignatureParser.parse(a), MessageSignatureParser.parse(b))
    }

    @Test
    fun contentDifferenceIsNotEquivalent() {
        val a = """[{"id":"m1","role":"user","parts":[{"type":"text","text":"hi"}]}]"""
        val b = """[{"id":"m1","role":"user","parts":[{"type":"text","text":"hello"}]}]"""
        assertNotEquals(MessageSignatureParser.parse(a), MessageSignatureParser.parse(b))
    }

    @Test
    fun toolApprovalDifferenceIsEquivalent() {
        val pending = """
            [{"id":"m1","role":"assistant","parts":[{"type":"tool","toolCallId":"t1","toolName":"search",
              "input":"q","approvalState":"pending"}]}]
        """.trimIndent()
        val approved = """
            [{"id":"m1","role":"assistant","parts":[{"type":"tool","toolCallId":"t1","toolName":"search",
              "input":"q","approvalState":"approved","output":[{"type":"text","text":"result"}]}]}]
        """.trimIndent()
        assertEquals(MessageSignatureParser.parse(pending), MessageSignatureParser.parse(approved))
    }

    @Test
    fun localExtraVersionDetected() {
        val backup = """[{"id":"m1","role":"assistant","parts":[{"type":"text","text":"v1"}]}]"""
        val local = """
            [{"id":"m1","role":"assistant","parts":[{"type":"text","text":"v1"}]},
             {"id":"m2","role":"assistant","parts":[{"type":"text","text":"v2"}]}]
        """.trimIndent()
        assertEquals(
            NodeContentRelation.LOCAL_EXTRA_VERSIONS,
            MessageSignatureParser.compareNodeMessages(local, backup),
        )
    }

    @Test
    fun backupExtraVersionDetected() {
        val local = """[{"id":"m1","role":"assistant","parts":[{"type":"text","text":"v1"}]}]"""
        val backup = """
            [{"id":"m1","role":"assistant","parts":[{"type":"text","text":"v1"}]},
             {"id":"m2","role":"assistant","parts":[{"type":"text","text":"v2"}]}]
        """.trimIndent()
        assertEquals(
            NodeContentRelation.BACKUP_EXTRA_VERSIONS,
            MessageSignatureParser.compareNodeMessages(local, backup),
        )
    }

    @Test
    fun sameIdDifferentContentIsContentDiff() {
        val local = """[{"id":"m1","role":"user","parts":[{"type":"text","text":"edited"}]}]"""
        val backup = """[{"id":"m1","role":"user","parts":[{"type":"text","text":"original"}]}]"""
        assertEquals(
            NodeContentRelation.CONTENT_DIFF,
            MessageSignatureParser.compareNodeMessages(local, backup),
        )
    }

    @Test
    fun disjointVersionSetsAreContentDiff() {
        val local = """[{"id":"m2","role":"assistant","parts":[{"type":"text","text":"v2"}]}]"""
        val backup = """[{"id":"m1","role":"assistant","parts":[{"type":"text","text":"v1"}]}]"""
        assertEquals(
            NodeContentRelation.CONTENT_DIFF,
            MessageSignatureParser.compareNodeMessages(local, backup),
        )
    }

    @Test
    fun equalNodesAreEqual() {
        val a = """[{"id":"m1","role":"user","parts":[{"type":"text","text":"hi"}]}]"""
        assertEquals(
            NodeContentRelation.EQUAL,
            MessageSignatureParser.compareNodeMessages(a, a),
        )
    }

    @Test
    fun malformedJsonYieldsEmptyList() {
        assertEquals(emptyList<MessageSignature>(), MessageSignatureParser.parse("not json"))
    }
}
'''

REQUIRED_SNIPPETS = (
    (MERGE_PLAN_PATH, "enum class ConversationMergeRelation"),
    (MERGE_PLAN_PATH, "data class MergePlan"),
    (SIGNATURE_PATH, "object MessageSignatureParser"),
    (SIGNATURE_PATH, "fun compareNodeMessages"),
    (TEST_PATH, "class MessageSignatureTest"),
)


def fail(msg):
    print("::error::" + msg)
    sys.exit(1)


def write_new_file(path, content):
    if os.path.exists(path):
        with io.open(path, "r", encoding="utf-8") as f:
            existing = f.read()
        if MARK in existing:
            print("batch150: already applied, skip " + path)
            return
        fail("batch150: target exists without mark :: " + path)
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    try:
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as exc:
        fail("batch150: write failed :: " + path + " :: " + str(exc))
    print("batch150: wrote " + path)


def verify_file(path, needle):
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as exc:
        fail("batch150: verify read failed :: " + path + " :: " + str(exc))
    if needle not in content:
        fail("batch150: verify failed, missing " + needle + " in " + path)
    if MARK not in content:
        fail("batch150: verify failed, missing mark in " + path)


def main():
    write_new_file(MERGE_PLAN_PATH, MERGE_PLAN_KT)
    write_new_file(SIGNATURE_PATH, MESSAGE_SIGNATURE_KT)
    write_new_file(TEST_PATH, MESSAGE_SIGNATURE_TEST_KT)
    for path, needle in REQUIRED_SNIPPETS:
        verify_file(path, needle)
    print("batch150: merge plan + message signature + tests written")


if __name__ == "__main__":
    main()

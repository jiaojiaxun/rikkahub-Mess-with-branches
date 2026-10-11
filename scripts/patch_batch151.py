#!/usr/bin/env python3
# batch151: 备份合并改造 2/10 —— 对话关系判定器 + 摘要生成 + 单元测试
# 核心算法: 按节点 id 对齐(不再按位置比较字符串), 消息级用语义签名比较,
#           selectIndex 永不触发分叉; 仅元数据差异(翻译/用量) → SAME。
# 变更: 仅新增两个文件, 不修改任何现有文件。
#   1) app/.../data/sync/merge/ConversationMergeAnalyzer.kt
#   2) app/src/test/.../merge/ConversationMergeAnalyzerTest.kt
# 幂等: 目标文件已存在且含 [batch151] 标记则跳过; 存在但无标记则 fail(防冲突)。

import io
import os
import sys

NL = chr(10)
MARK = "[batch151]"

ANALYZER_PATH = "app/src/main/java/me/rerere/rikkahub/data/sync/merge/ConversationMergeAnalyzer.kt"
TEST_PATH = "app/src/test/java/me/rerere/rikkahub/data/sync/merge/ConversationMergeAnalyzerTest.kt"

ANALYZER_KT = r'''// [batch151] 备份合并改造：对话关系判定
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
'''

TEST_KT = r'''// [batch151] 备份合并改造：对话关系判定单元测试
package me.rerere.rikkahub.data.sync.merge

import org.junit.Assert.assertEquals
import org.junit.Test

class ConversationMergeAnalyzerTest {

    private fun node(id: String, index: Int, vararg messageIds: String, selectIndex: Int = 0): MergeNodeSnapshot {
        val messages = messageIds.joinToString(",") { mid ->
            """{"id":"$mid","role":"user","parts":[{"type":"text","text":"text-of-$mid"}]}"""
        }
        return MergeNodeSnapshot(nodeId = id, nodeIndex = index, messagesJson = "[$messages]", selectIndex = selectIndex)
    }

    private fun conversation(
        id: String = "conv1",
        updateAt: Long = 100L,
        nodes: List<MergeNodeSnapshot>,
    ) = MergeConversationSnapshot(id = id, title = "T", updateAt = updateAt, nodes = nodes)

    @Test
    fun newWhenLocalMissing() {
        val backup = conversation(nodes = listOf(node("n1", 0, "m1")))
        val result = ConversationMergeAnalyzer.analyze(null, backup)
        assertEquals(ConversationMergeRelation.NEW, result.relation)
        assertEquals(
            ConversationMergeDecision.IMPORT,
            ConversationMergeAnalyzer.defaultDecision(result.relation, null, backup),
        )
    }

    @Test
    fun sameWhenIdentical() {
        val local = conversation(nodes = listOf(node("n1", 0, "m1"), node("n2", 1, "m2")))
        val backup = conversation(nodes = listOf(node("n1", 0, "m1"), node("n2", 1, "m2")))
        val result = ConversationMergeAnalyzer.analyze(local, backup)
        assertEquals(ConversationMergeRelation.SAME, result.relation)
    }

    @Test
    fun sameWhenOnlySelectIndexDiffers() {
        // 用户切换了消息版本：selectIndex 不同但消息集合相同 → SAME，绝不分叉
        val local = conversation(nodes = listOf(node("n1", 0, "m1", "m2", selectIndex = 0)))
        val backup = conversation(nodes = listOf(node("n1", 0, "m1", "m2", selectIndex = 1)))
        val result = ConversationMergeAnalyzer.analyze(local, backup)
        assertEquals(ConversationMergeRelation.SAME, result.relation)
    }

    @Test
    fun sameWhenOnlyTranslationDiffers() {
        // 用户主诉场景：本地翻译过一条消息 → 元数据差异，不得判分叉
        val local = conversation(
            nodes = listOf(
                MergeNodeSnapshot(
                    nodeId = "n1", nodeIndex = 0, selectIndex = 0,
                    messagesJson = """[{"id":"m1","role":"assistant","parts":[{"type":"text","text":"hi"}],"translation":"你好"}]""",
                ),
            ),
        )
        val backup = conversation(nodes = listOf(node("n1", 0, "m1")))
        val result = ConversationMergeAnalyzer.analyze(local, backup)
        assertEquals(ConversationMergeRelation.SAME, result.relation)
    }

    @Test
    fun backupAheadWhenTailAppended() {
        val local = conversation(nodes = listOf(node("n1", 0, "m1")))
        val backup = conversation(updateAt = 200L, nodes = listOf(node("n1", 0, "m1"), node("n2", 1, "m2")))
        val result = ConversationMergeAnalyzer.analyze(local, backup)
        assertEquals(ConversationMergeRelation.BACKUP_AHEAD, result.relation)
        assertEquals(
            ConversationMergeDecision.USE_BACKUP,
            ConversationMergeAnalyzer.defaultDecision(result.relation, local, backup),
        )
    }

    @Test
    fun localAheadWhenTailAppended() {
        val local = conversation(updateAt = 200L, nodes = listOf(node("n1", 0, "m1"), node("n2", 1, "m2")))
        val backup = conversation(nodes = listOf(node("n1", 0, "m1")))
        val result = ConversationMergeAnalyzer.analyze(local, backup)
        assertEquals(ConversationMergeRelation.LOCAL_AHEAD, result.relation)
        assertEquals(
            ConversationMergeDecision.KEEP_LOCAL,
            ConversationMergeAnalyzer.defaultDecision(result.relation, local, backup),
        )
    }

    @Test
    fun versionsModifiedWhenRegenerated() {
        // 重生成：同一节点 messages 数组多一个版本
        val local = conversation(nodes = listOf(node("n1", 0, "m1", "m2", selectIndex = 1)))
        val backup = conversation(nodes = listOf(node("n1", 0, "m1")))
        val result = ConversationMergeAnalyzer.analyze(local, backup)
        assertEquals(ConversationMergeRelation.VERSIONS_MODIFIED, result.relation)
        assertEquals(
            ConversationMergeDecision.MERGE_VERSIONS,
            ConversationMergeAnalyzer.defaultDecision(result.relation, local, backup),
        )
    }

    @Test
    fun divergedWhenBothAppended() {
        val local = conversation(nodes = listOf(node("n1", 0, "m1"), node("nA", 1, "ma")))
        val backup = conversation(nodes = listOf(node("n1", 0, "m1"), node("nB", 1, "mb")))
        val result = ConversationMergeAnalyzer.analyze(local, backup)
        assertEquals(ConversationMergeRelation.DIVERGED, result.relation)
    }

    @Test
    fun divergedWhenMiddleNodeRemoved() {
        // 本地删除中间节点 → nodeIndex 重排后按 id 对齐仍应识别为分叉（推荐本地，因 updateAt 新）
        val local = conversation(updateAt = 200L, nodes = listOf(node("n1", 0, "m1"), node("n3", 1, "m3")))
        val backup = conversation(nodes = listOf(node("n1", 0, "m1"), node("n2", 1, "m2"), node("n3", 2, "m3")))
        val result = ConversationMergeAnalyzer.analyze(local, backup)
        assertEquals(ConversationMergeRelation.DIVERGED, result.relation)
        assertEquals(
            ConversationMergeDecision.KEEP_LOCAL,
            ConversationMergeAnalyzer.defaultDecision(result.relation, local, backup),
        )
    }

    @Test
    fun divergedWhenMessageEdited() {
        // 同一消息 id 但内容被编辑 → 真分叉
        val local = conversation(
            nodes = listOf(
                MergeNodeSnapshot(
                    nodeId = "n1", nodeIndex = 0, selectIndex = 0,
                    messagesJson = """[{"id":"m1","role":"user","parts":[{"type":"text","text":"edited"}]}]""",
                ),
            ),
        )
        val backup = conversation(nodes = listOf(node("n1", 0, "m1")))
        val result = ConversationMergeAnalyzer.analyze(local, backup)
        assertEquals(ConversationMergeRelation.DIVERGED, result.relation)
    }

    @Test
    fun emptyLocalNodesTreatedAsBackupAhead() {
        val local = conversation(nodes = emptyList())
        val backup = conversation(nodes = listOf(node("n1", 0, "m1")))
        assertEquals(
            ConversationMergeRelation.BACKUP_AHEAD,
            ConversationMergeAnalyzer.analyze(local, backup).relation,
        )
    }

    @Test
    fun summaryExtractsPreviews() {
        val conv = conversation(
            nodes = listOf(
                node("n1", 0, "m1"),
                node("n2", 1, "m2", "m3", selectIndex = 1),
            ),
        )
        val summary = ConversationMergeAnalyzer.summarize(conv)
        assertEquals(2, summary.nodeCount)
        assertEquals(3, summary.messageCount)
        assertEquals("text-of-m1", summary.firstUserMessagePreview)
        assertEquals("text-of-m3", summary.lastMessagePreview)
    }
}
'''

REQUIRED_SNIPPETS = (
    (ANALYZER_PATH, "object ConversationMergeAnalyzer"),
    (ANALYZER_PATH, "fun analyze("),
    (ANALYZER_PATH, "fun summarize("),
    (TEST_PATH, "class ConversationMergeAnalyzerTest"),
)


def fail(msg):
    print("::error::" + msg)
    sys.exit(1)


def write_new_file(path, content):
    if os.path.exists(path):
        with io.open(path, "r", encoding="utf-8") as f:
            existing = f.read()
        if MARK in existing:
            print("batch151: already applied, skip " + path)
            return
        fail("batch151: target exists without mark :: " + path)
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    try:
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as exc:
        fail("batch151: write failed :: " + path + " :: " + str(exc))
    print("batch151: wrote " + path)


def verify_file(path, needle):
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as exc:
        fail("batch151: verify read failed :: " + path + " :: " + str(exc))
    if needle not in content:
        fail("batch151: verify failed, missing " + needle + " in " + path)
    if MARK not in content:
        fail("batch151: verify failed, missing mark in " + path)


def main():
    write_new_file(ANALYZER_PATH, ANALYZER_KT)
    write_new_file(TEST_PATH, TEST_KT)
    for path, needle in REQUIRED_SNIPPETS:
        verify_file(path, needle)
    print("batch151: conversation merge analyzer + tests written")


if __name__ == "__main__":
    main()

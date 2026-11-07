// [batch151] 备份合并改造：对话关系判定单元测试
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

// [batch153] 备份合并改造：节点版本合并器单元测试
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

// [batch150] 备份合并改造：消息语义签名单元测试
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

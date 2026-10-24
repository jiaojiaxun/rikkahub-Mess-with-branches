package me.rerere.rikkahub.data.ai.tools

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import me.rerere.ai.core.Tool
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** rhApprovalIdentity: 审批键规则的边界测试（动作级细化、MCP 服务器键、异常回落）。 */
class ToolApprovalIdentityTest {

    private fun dummyTool(name: String, key: ((JsonObject) -> String)? = null): Tool {
        return if (key == null) {
            Tool(name = name, description = "", execute = { emptyList() })
        } else {
            Tool(name = name, description = "", approvalKey = key, execute = { emptyList() })
        }
    }

    @Test
    fun `default key is the tool name`() {
        val tool = dummyTool("workspace_write_file")
        assertEquals("workspace_write_file", ToolApprovalIdentity.keyOf(tool, null))
        assertEquals("workspace_write_file", ToolApprovalIdentity.keyOfName("workspace_write_file", null))
    }

    @Test
    fun `apply change is action scoped`() {
        val args = JsonObject(mapOf("action" to JsonPrimitive("set_theme")))
        assertEquals(
            "rikkahub_apply_change@set_theme",
            ToolApprovalIdentity.keyOfName("rikkahub_apply_change", args),
        )
        assertEquals("other_tool", ToolApprovalIdentity.keyOfName("other_tool", args))
    }

    @Test
    fun `blank action falls back to the plain name`() {
        val args = JsonObject(mapOf("action" to JsonPrimitive("  ")))
        assertEquals("rikkahub_apply_change", ToolApprovalIdentity.keyOfName("rikkahub_apply_change", args))
        assertEquals("rikkahub_apply_change", ToolApprovalIdentity.keyOfName("rikkahub_apply_change", null))
    }

    @Test
    fun `override throwing falls back to the name`() {
        val tool = dummyTool("explosive") { throw IllegalStateException("boom") }
        assertEquals("explosive", ToolApprovalIdentity.keyOf(tool, JsonObject(emptyMap())))
    }

    @Test
    fun `override returning key is honored`() {
        val tool = dummyTool("custom") { args -> "custom@" + args["a"] }
        assertEquals("custom@1", ToolApprovalIdentity.keyOf(tool, JsonObject(mapOf("a" to JsonPrimitive(1)))))
    }

    @Test
    fun `mcp server key extraction`() {
        assertEquals(
            "mcp__1a8bc96f_luckin",
            ToolApprovalIdentity.mcpServerKeyOf("mcp__1a8bc96f_luckin__previewOrder"),
        )
        assertNull(ToolApprovalIdentity.mcpServerKeyOf("mcp_add"))
        assertNull(ToolApprovalIdentity.mcpServerKeyOf("workspace_shell"))
        assertNull(ToolApprovalIdentity.mcpServerKeyOf("rikkahub_apply_change"))
    }

    @Test
    fun `mcp server target round trip`() {
        val encoded = ToolApprovalIdentity.encodeMcpServerTarget("mcp__abc_x")
        assertTrue(encoded.startsWith("mcp_server::"))
        assertEquals("mcp__abc_x", ToolApprovalIdentity.decodeMcpServerTarget(encoded))
        assertNull(ToolApprovalIdentity.decodeMcpServerTarget("mcp__abc_x"))
        assertNull(ToolApprovalIdentity.decodeMcpServerTarget(null))
        assertNull(ToolApprovalIdentity.decodeMcpServerTarget("mcp_server::"))
    }

    @Test
    fun `workspace keys never leak into server grants`() {
        assertTrue(ToolApprovalIdentity.isWorkspaceKey("workspace_write_file"))
        assertFalse(ToolApprovalIdentity.isWorkspaceKey("mcp__abc_x"))
        assertNull(ToolApprovalIdentity.mcpServerKeyOf("workspace_abc"))
    }
}

package me.rerere.rikkahub.data.ai.tools

import me.rerere.workspace.WorkspaceTreeEntry
import me.rerere.workspace.WorkspaceTreeResult
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Coverage for the pure helpers and approval defaults of the file workspace tools. */
class WorkspaceToolsTest {
    @Test
    fun `workspace file tools are approval gated by default`() {
        assertFalse(resolveWorkspaceToolApproval("workspace_read_file", emptyMap()))
        assertFalse(resolveWorkspaceToolApproval("workspace_write_file", emptyMap()))
        assertFalse(resolveWorkspaceToolApproval("workspace_edit_file", emptyMap()))
        assertFalse(resolveWorkspaceToolApproval("workspace_create_folder", emptyMap()))
        assertFalse(resolveWorkspaceToolApproval("workspace_read_folder", emptyMap()))
        assertFalse(resolveWorkspaceToolApproval("workspace_shell", emptyMap()))
    }

    @Test
    fun `workspace approval override applies only to known file tools`() {
        assertTrue(resolveWorkspaceToolApproval("workspace_write_file", mapOf("workspace_write_file" to true)))
        assertFalse(resolveWorkspaceToolApproval("workspace_shell", mapOf("workspace_shell" to true)))
    }

    @Test
    fun `formatWorkspaceTree renders empty directory`() {
        val text = formatWorkspaceTree("/workspace", WorkspaceTreeResult(entries = emptyList(), truncated = false))
        assertEquals("/workspace/ (empty)", text)
    }

    @Test
    fun `formatWorkspaceTree indents nested entries by depth`() {
        val result = WorkspaceTreeResult(
            entries = listOf(
                WorkspaceTreeEntry(path = "src", name = "src", isDirectory = true, sizeBytes = 0, depth = 1),
                WorkspaceTreeEntry(path = "src/a.txt", name = "a.txt", isDirectory = false, sizeBytes = 12, depth = 2),
                WorkspaceTreeEntry(path = "b.txt", name = "b.txt", isDirectory = false, sizeBytes = 3, depth = 1),
            ),
            truncated = false,
        )

        val text = formatWorkspaceTree("/workspace", result)

        assertEquals(
            """
            /workspace/
              src/
                a.txt (12 bytes)
              b.txt (3 bytes)
            """.trimIndent(),
            text,
        )
    }

    @Test
    fun `formatWorkspaceTree appends a truncation notice when capped`() {
        val result = WorkspaceTreeResult(
            entries = listOf(
                WorkspaceTreeEntry(path = "a.txt", name = "a.txt", isDirectory = false, sizeBytes = 1, depth = 1),
            ),
            truncated = true,
        )

        val text = formatWorkspaceTree("/workspace", result)

        assertTrue(text.contains("truncated"))
        assertTrue(text.endsWith("truncated: showing 1 entries; narrow the path for a complete listing)"))
    }
}

package me.rerere.rikkahub.data.ai.tools

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Regression coverage for the slim build's removed accessibility intent surface. */
class ToolApprovalDefaultsTest {

    @Test
    fun `removed launch_activity is not an approval-gated registered tool`() {
        assertFalse(ToolApprovalDefaults.requiresApproval("launch_activity"))
        assertTrue(ToolApprovalDefaults.allowsAlwaysAllow("launch_activity"))
    }
}

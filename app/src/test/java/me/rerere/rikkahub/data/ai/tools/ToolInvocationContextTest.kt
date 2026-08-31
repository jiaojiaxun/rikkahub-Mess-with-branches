package me.rerere.rikkahub.data.ai.tools

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/**
 * Invocation context plumbing for ordinary local-tool dispatch. The context keeps the
 * caller identities and model image capability without carrying any remote execution mode.
 */
class ToolInvocationContextTest {

    @Test fun `EMPTY has no caller info`() {
        assertNull(ToolInvocationContext.EMPTY.callerAssistantId)
        assertNull(ToolInvocationContext.EMPTY.callerConversationId)
    }

    @Test fun `default constructor matches EMPTY`() {
        assertEquals(ToolInvocationContext(), ToolInvocationContext.EMPTY)
    }

    @Test fun `context preserves caller ids and image capability`() {
        val ctx = ToolInvocationContext(
            callerAssistantId = "asst-123",
            callerConversationId = "conv-456",
            modelCanSeeImages = false,
        )
        assertEquals("asst-123", ctx.callerAssistantId)
        assertEquals("conv-456", ctx.callerConversationId)
        assertEquals(false, ctx.modelCanSeeImages)
    }
}

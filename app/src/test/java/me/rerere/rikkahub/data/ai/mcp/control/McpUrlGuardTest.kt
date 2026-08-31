package me.rerere.rikkahub.data.ai.mcp.control

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class McpUrlGuardTest {

    @Test fun `https url accepted in any context`() {
        assertTrue(McpUrlGuard.check("https://example.com/sse", restrictLocalNetwork = false) is McpUrlGuard.Result.Ok)
        assertTrue(McpUrlGuard.check("https://example.com/sse", restrictLocalNetwork = true) is McpUrlGuard.Result.Ok)
    }

    @Test fun `http public host accepted in any context`() {
        assertTrue(McpUrlGuard.check("http://example.com:9090/sse", restrictLocalNetwork = false) is McpUrlGuard.Result.Ok)
        assertTrue(McpUrlGuard.check("http://example.com:9090/sse", restrictLocalNetwork = true) is McpUrlGuard.Result.Ok)
    }

    @Test fun `non-http schemes rejected`() {
        for (bad in listOf(
            "file:///etc/passwd",
            "ftp://example.com/path",
            "data:text/plain,abc",
            "javascript:alert(1)",
            "ws://example.com/sse",
            "tcp://example.com",
        )) {
            val r = McpUrlGuard.check(bad, restrictLocalNetwork = false)
            assertTrue("expected reject for $bad", r is McpUrlGuard.Result.Reject)
            val rej = r as McpUrlGuard.Result.Reject
            assertEquals("unsupported_url_scheme", rej.error)
        }
    }

    @Test fun `loopback rejected in restrictLocalNetwork context`() {
        for (lp in listOf(
            "http://localhost:9090/sse",
            "http://127.0.0.1:9090/sse",
            "http://127.0.42.99:9090/sse",
            "http://[::1]:9090/sse",
        )) {
            val r = McpUrlGuard.check(lp, restrictLocalNetwork = true)
            assertTrue("expected reject for $lp in restrictLocalNetwork", r is McpUrlGuard.Result.Reject)
            assertEquals("loopback_disallowed", (r as McpUrlGuard.Result.Reject).error)
        }
    }

    @Test fun `loopback allowed in interactive context`() {
        for (lp in listOf(
            "http://localhost:9090/sse",
            "http://127.0.0.1:9090/sse",
            "http://127.0.42.99:9090/sse",
            "http://[::1]:9090/sse",
        )) {
            assertTrue("expected ok for $lp interactive", McpUrlGuard.check(lp, restrictLocalNetwork = false) is McpUrlGuard.Result.Ok)
        }
    }

    @Test fun `empty url rejected`() {
        val r = McpUrlGuard.check("", restrictLocalNetwork = false)
        assertEquals("invalid_url", (r as McpUrlGuard.Result.Reject).error)
    }

    @Test fun `malformed url rejected`() {
        val r = McpUrlGuard.check("ht!tp:::nonsense", restrictLocalNetwork = false)
        assertTrue(r is McpUrlGuard.Result.Reject)
    }

    @Test fun `url missing host rejected`() {
        // "http:///path" has no authority — URI parses but host is null.
        val r = McpUrlGuard.check("http:///nohost", restrictLocalNetwork = false)
        assertTrue(r is McpUrlGuard.Result.Reject)
    }

    @Test fun `isLoopback recognizes all forms`() {
        assertTrue(McpUrlGuard.isLoopback("localhost"))
        assertTrue(McpUrlGuard.isLoopback("127.0.0.1"))
        assertTrue(McpUrlGuard.isLoopback("127.255.255.255"))
        assertTrue(McpUrlGuard.isLoopback("::1"))
    }

    @Test fun `isLoopback does not over-match`() {
        for (host in listOf(
            "127.example.com",
            "example.com",
            "192.168.1.1",
            "10.0.0.1",
            "myserver.local",
            "127a.0.0.1",
        )) {
            assertEquals(false, McpUrlGuard.isLoopback(host))
        }
    }

    /**
     * Bypass forms identified by the Phase 10 audit pass — every one of these MUST be
     * caught by the loopback guard so the LLM can't ferry them past the restrictLocalNetwork block.
     */
    @Test fun `isLoopback catches audit-bypass forms`() {
        assertTrue("trailing dot",
            McpUrlGuard.isLoopback("localhost."))
        assertTrue("uppercase",
            McpUrlGuard.isLoopback("LOCALHOST"))
        assertTrue("any-local 0_0_0_0",
            McpUrlGuard.isLoopback("0.0.0.0"))
        assertTrue("long-form IPv6 loopback",
            McpUrlGuard.isLoopback("0:0:0:0:0:0:0:1"))
        assertTrue("IPv4-mapped IPv6 loopback",
            McpUrlGuard.isLoopback("::ffff:127.0.0.1"))
        assertTrue("bracketed long-form IPv6",
            McpUrlGuard.isLoopback("[0:0:0:0:0:0:0:1]"))
    }

    @Test fun `audit bypass urls rejected in restrictLocalNetwork context`() {
        for (lp in listOf(
            "http://localhost.:9090/sse",
            "http://0.0.0.0:9090/sse",
            "http://[0:0:0:0:0:0:0:1]:9090/sse",
            "http://[::ffff:127.0.0.1]:9090/sse",
        )) {
            val r = McpUrlGuard.check(lp, restrictLocalNetwork = true)
            assertTrue(
                "expected reject for audit-bypass url $lp",
                r is McpUrlGuard.Result.Reject,
            )
        }
    }
}

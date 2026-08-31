package me.rerere.rikkahub.data.ai.mcp.control

import java.net.URI

/** Validates MCP server URLs before they enter persistent configuration. */
object McpUrlGuard {
    sealed class Result {
        data object Ok : Result()
        data class Reject(val error: String, val detail: String) : Result()
    }

    /**
     * Validate a candidate MCP URL. [restrictLocalNetwork] is used by callers that must not
     * connect to device-local services; ordinary in-app MCP setup leaves it false because a
     * local MCP proxy is a legitimate user-configured target.
     */
    fun check(url: String, restrictLocalNetwork: Boolean = false): Result {
        val trimmed = url.trim()
        if (trimmed.isEmpty()) return Result.Reject("invalid_url", "url is empty")
        val parsed = try {
            URI(trimmed)
        } catch (t: Throwable) {
            return Result.Reject("invalid_url", "could not parse url: ${t.message ?: t.javaClass.simpleName}")
        }
        val scheme = parsed.scheme?.lowercase()
        if (scheme != "http" && scheme != "https") {
            return Result.Reject(
                "unsupported_url_scheme",
                "only http and https are accepted; got '${scheme ?: "(none)"}'",
            )
        }
        val host = parsed.host?.lowercase()
        if (host.isNullOrBlank()) return Result.Reject("invalid_url", "url is missing a host component")
        if (restrictLocalNetwork && isLoopback(host)) {
            return Result.Reject(
                "loopback_disallowed",
                "loopback URL ($host) is not allowed in the restricted network context",
            )
        }
        return Result.Ok
    }

    /** True for localhost, IPv4 loopback/any-local and IPv6 loopback literals. */
    fun isLoopback(host: String): Boolean {
        val normalized = host.removePrefix("[").removeSuffix("]").trimEnd('.').lowercase()
        if (normalized.isEmpty()) return false
        if (normalized == "localhost") return true
        val looksLikeIpLiteral = normalized.contains(':') || normalized.matches(Regex("""[0-9.]+"""))
        if (looksLikeIpLiteral) {
            val addr = runCatching { java.net.InetAddress.getByName(normalized) }.getOrNull()
            if (addr != null && (addr.isLoopbackAddress || addr.isAnyLocalAddress)) return true
        }
        return false
    }
}

package me.rerere.rikkahub.data.ai.tools

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import me.rerere.ai.core.Tool

/**
 * rhApprovalIdentity: 审批身份（approval identity）的唯一数据源。
 *
 * 一个工具的「审批键」同时决定三件事：
 *  1. 「始终允许」存到哪里（ToolApprovalPreferences.always_allow_tool_names 的元素）；
 *  2. 自动放行判定查什么键（ChatService.isToolAutoApproved 的入参）；
 *  3. MCP 工具归到哪台服务器（服务器级授权的分组键）。
 *
 * 默认键 = 工具名，因此对绝大多数工具，行为与引入本机制前逐字节一致；
 * 只有复合工具（rikkahub_apply_change）细化到「工具名@子动作」，避免批一个动作就放行整个
 * App Control 写能力。
 */
object ToolApprovalIdentity {
    /** workspace_ 前缀工具按工作区隔离，任何全局/服务器级授权都不得命中。 */
    const val WORKSPACE_PREFIX = "workspace_"

    /**
     * 组级按钮把「服务器键」编码成伪工具名回传给 ChatService；真工具名不可能以这个
     * 前缀开头，所以不会与任何实际工具冲突。
     */
    const val MCP_SERVER_TARGET_PREFIX = "mcp_server::"

    /** 唯一需要动作级细化的工具。 */
    private const val APPLY_CHANGE_TOOL = "rikkahub_apply_change"

    /**
     * 动作级键规则。AppControlTools 的 approvalKey override 与 ChatService 的授权回写
     * 路径（那里只有工具名 + 入参 JSON，拿不到 Tool 定义）都调这一个实现，避免两份规则漂移。
     */
    fun actionScopedKey(toolName: String, args: JsonObject?): String {
        if (toolName != APPLY_CHANGE_TOOL) return toolName
        val action = (args?.get("action") as? JsonPrimitive)?.contentOrNull
        return if (action.isNullOrBlank()) toolName else toolName + "@" + action
    }

    /** 工具定义 + 入参 → 审批键。hook 抛异常时回落工具名，绝不打断审批流程。 */
    fun keyOf(tool: Tool, args: JsonObject?): String {
        return runCatching {
            tool.approvalKey(args ?: JsonObject(emptyMap()))
        }.getOrDefault(tool.name)
    }

    /** 只有工具名与入参时的审批键（授权回写路径使用，与 [keyOf] 同一规则）。 */
    fun keyOfName(toolName: String, args: JsonObject?): String {
        return runCatching { actionScopedKey(toolName, args) }.getOrDefault(toolName)
    }

    /** mcp__<slug>_<服务器名>__<工具名> → mcp__<slug>_<服务器名>；非 MCP 工具返回 null。 */
    fun mcpServerKeyOf(toolName: String): String? {
        if (!toolName.startsWith("mcp__")) return null
        if (toolName.indexOf("__", startIndex = 5) < 0) return null
        return toolName.substringBeforeLast("__")
    }

    fun isWorkspaceKey(key: String): Boolean = key.startsWith(WORKSPACE_PREFIX)

    fun encodeMcpServerTarget(serverKey: String): String = MCP_SERVER_TARGET_PREFIX + serverKey

    fun decodeMcpServerTarget(toolName: String?): String? {
        if (toolName == null) return null
        if (!toolName.startsWith(MCP_SERVER_TARGET_PREFIX)) return null
        return toolName.removePrefix(MCP_SERVER_TARGET_PREFIX).takeIf { it.isNotBlank() }
    }
}

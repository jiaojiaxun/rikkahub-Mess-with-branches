#!/usr/bin/env python3
# batch271 (Phase 0): approval identity foundation.
#   Tool.approvalKey hook / ToolApprovalIdentity / MCP server-level grants /
#   ChatService auto-approve + grant write / GenerationHandler keyOf / approval card buttons.
# New files (ToolApprovalIdentity.kt) are committed directly; this script edits existing files.
# MARK=rhApprovalIdentity
import sys
from pathlib import Path

MARK = "rhApprovalIdentity"
NL = chr(10)
Q = chr(34)
DIAG = "ci_diag_batch271.txt"
applied = []
failed = []


def diag(msg):
    try:
        with open(DIAG, "a", encoding="utf-8") as f:
            f.write(msg + NL)
    except Exception:
        pass


def fail(msg):
    diag("FAIL " + msg)
    print("::error title=batch271::" + msg)
    raise SystemExit(0)


def read(path):
    p = Path(path)
    if not p.exists():
        fail("missing file: " + path)
    return p.read_text(encoding="utf-8")


def write(path, content):
    Path(path).write_text(content, encoding="utf-8")


def replace_text(content, old, new, label):
    if old not in content:
        fail(label + " text not found")
    n = content.count(old)
    if n != 1:
        fail(label + " text not unique: " + str(n))
    applied.append(label)
    return content.replace(old, new, 1)


def insert_after_line(content, anchor, block, label):
    lines = content.split(NL)
    hits = [i for i, line in enumerate(lines) if line.strip() == anchor]
    if len(hits) != 1:
        fail(label + " anchor count=" + str(len(hits)) + " [" + anchor + "]")
    lines.insert(hits[0] + 1, block)
    applied.append(label)
    return NL.join(lines)


def insert_before_line(content, anchor, block, label):
    lines = content.split(NL)
    hits = [i for i, line in enumerate(lines) if line.strip() == anchor]
    if len(hits) != 1:
        fail(label + " anchor count=" + str(len(hits)) + " [" + anchor + "]")
    lines.insert(hits[0], block)
    applied.append(label)
    return NL.join(lines)


def add_strings(path, pairs, label):
    content = read(path)
    if MARK in content:
        diag(label + " marker present, skip")
        return
    add = []
    for name, text in pairs:
        if ("name=" + Q + name + Q) in content:
            continue
        add.append("    <string name=" + Q + name + Q + ">" + text + "</string>")
    if not add:
        diag(label + " all keys present, skip")
        return
    block = "    <!-- " + MARK + " -->" + NL + NL.join(add)
    content = replace_text(content, "</resources>", block + NL + "</resources>", label)
    write(path, content)


# ---------------- A. ai/core/Tool.kt : approvalKey hook ----------------
def edit_tool_kt():
    path = "ai/src/main/java/me/rerere/ai/core/Tool.kt"
    content = read(path)
    if MARK in content:
        diag("tool.kt already patched")
        return
    anchor = "    val needsApproval: (JsonElement) -> Boolean = { false },"
    block = (
        "    /**" + NL
        + "     * rhApprovalIdentity: 审批身份键。默认 = 工具名；复合工具（如 rikkahub_apply_change）" + NL
        + "     * 覆盖为 " + Q + "工具名@子动作" + Q + "，把「始终允许」细化到动作粒度。同一键既用于授权" + NL
        + "     * 存储，也用于自动放行判定（见 ToolApprovalIdentity）。args 解析失败必须回落工具名。" + NL
        + "     */" + NL
        + "    val approvalKey: (JsonObject) -> String = { name },"
    )
    content = insert_after_line(content, anchor, block, "tool-approvalKey")
    write(path, content)


# ---------------- B. ToolApprovalAllowList : per-chat server grants ----------------
def edit_allow_list():
    path = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/ToolApprovalAllowList.kt"
    content = read(path)
    if MARK in content:
        diag("allow-list already patched")
        return
    anchor = "    private fun key(conversationId: Uuid, toolName: String) = " + Q + "${conversationId}::${toolName}" + Q
    block = (
        "" + NL
        + "    // rhApprovalIdentity: 会话级 MCP 服务器授权（「本会话允许整个 <服务器>」）。" + NL
        + "    // clearChat 按 " + Q + "${conversationId}::" + Q + " 前缀清理，服务器键天然被一并清掉。" + NL
        + "    private val perChatMcpServer: MutableSet<String> =" + NL
        + "        java.util.concurrent.ConcurrentHashMap.newKeySet()" + NL
        + "" + NL
        + "    private fun serverGrantKey(conversationId: Uuid, serverKey: String) =" + NL
        + "        " + Q + "${conversationId}::srv::${serverKey}" + Q + NL
        + "" + NL
        + "    /** True iff 整台 MCP 服务器已在本会话内被放行。 */" + NL
        + "    fun isMcpServerAllowedForChat(conversationId: Uuid, serverKey: String): Boolean =" + NL
        + "        perChatMcpServer.contains(serverGrantKey(conversationId, serverKey))" + NL
        + "" + NL
        + "    fun grantForChatMcpServer(conversationId: Uuid, serverKey: String) {" + NL
        + "        perChatMcpServer.add(serverGrantKey(conversationId, serverKey))" + NL
        + "    }" + NL
        + "" + NL
        + "    fun revokeForChatMcpServer(conversationId: Uuid, serverKey: String) {" + NL
        + "        perChatMcpServer.remove(serverGrantKey(conversationId, serverKey))" + NL
        + "    }" + NL
        + "" + NL
        + "    fun listMcpServersForChat(conversationId: Uuid): List<String> {" + NL
        + "        val prefix = " + Q + "${conversationId}::srv::" + Q + NL
        + "        return perChatMcpServer.asSequence()" + NL
        + "            .filter { it.startsWith(prefix) }" + NL
        + "            .map { it.removePrefix(prefix) }" + NL
        + "            .sorted()" + NL
        + "            .toList()" + NL
        + "    }"
    )
    content = insert_after_line(content, anchor, block, "allowlist-server-grants")
    write(path, content)


# ---------------- C. ToolApprovalPreferences : persistent server grants ----------------
def edit_prefs():
    path = "app/src/main/java/me/rerere/rikkahub/data/preferences/ToolApprovalPreferences.kt"
    content = read(path)
    if MARK in content:
        diag("prefs already patched")
        return
    key_anchor = "    private val K_GLOBAL_YOLO = booleanPreferencesKey(" + Q + "global_auto_approve_yolo" + Q + ")"
    key_block = (
        "    // rhApprovalIdentity: 「始终允许整台 MCP 服务器」集合（元素形如 mcp__<slug>_<服务器名>）" + NL
        + "    private val K_MCP_SERVER_ALWAYS = stringSetPreferencesKey(" + Q + "mcp_server_always" + Q + ")"
    )
    content = insert_after_line(content, key_anchor, key_block, "prefs-key")
    anchor2 = "    suspend fun current(): Set<String> = migrateAwayWorkspaceTools()"
    block2 = (
        "    /** rhApprovalIdentity: 「始终允许整个服务器」的实时集合（设置页开关读取）。 */" + NL
        + "    val mcpServerAlwaysFlow: Flow<Set<String>> = store.data.map {" + NL
        + "        it[K_MCP_SERVER_ALWAYS].orEmpty()" + NL
        + "    }" + NL
        + "" + NL
        + "    suspend fun currentMcpServerAlways(): Set<String> = mcpServerAlwaysFlow.first()" + NL
        + "" + NL
        + "    suspend fun grantMcpServerAlways(serverKey: String) {" + NL
        + "        // 服务器键永不以 workspace_ 开头；这里再加一道守卫，与 grantAlways 同一策略：" + NL
        + "        // 宁可拒绝并记日志，也不静默污染全局集合。" + NL
        + "        if (isWorkspaceToolName(serverKey)) {" + NL
        + "            Log.w(TAG, " + Q + "refusing to grant server-level approval to '" + Q + " + serverKey)" + NL
        + "            return" + NL
        + "        }" + NL
        + "        store.edit { it[K_MCP_SERVER_ALWAYS] = (it[K_MCP_SERVER_ALWAYS].orEmpty()) + serverKey }" + NL
        + "    }" + NL
        + "" + NL
        + "    suspend fun revokeMcpServerAlways(serverKey: String) {" + NL
        + "        store.edit { it[K_MCP_SERVER_ALWAYS] = (it[K_MCP_SERVER_ALWAYS].orEmpty()) - serverKey }" + NL
        + "    }" + NL
        + "" + NL
        + "    suspend fun current(): Set<String> = migrateAwayWorkspaceTools()"
    )
    content = replace_text(content, anchor2, block2, "prefs-server-fns")
    write(path, content)


# ---------------- D. ChatService : auto-approve + grant write key ----------------
def edit_chat_service():
    path = "app/src/main/java/me/rerere/rikkahub/service/ChatService.kt"
    content = read(path)
    if MARK in content:
        diag("chatservice already patched")
        return
    old_lookup = (
        "                            (!isWorkspaceToolName(toolName) &&" + NL
        + "                                toolApprovalPreferences.current().contains(toolName))"
    )
    new_lookup = (
        "                            (!isWorkspaceToolName(toolName) &&" + NL
        + "                                toolApprovalPreferences.current().contains(toolName)) ||" + NL
        + "                            // rhApprovalIdentity: MCP 服务器级授权（本会话或始终）。服务器键" + NL
        + "                            // 永不以 workspace_ 开头，因此不会命中工作区工具。" + NL
        + "                            (me.rerere.rikkahub.data.ai.tools.ToolApprovalIdentity" + NL
        + "                                .mcpServerKeyOf(toolName)" + NL
        + "                                ?.let { srv ->" + NL
        + "                                    me.rerere.rikkahub.data.ai.tools.ToolApprovalAllowList" + NL
        + "                                        .isMcpServerAllowedForChat(conversationId, srv) ||" + NL
        + "                                        toolApprovalPreferences.currentMcpServerAlways().contains(srv)" + NL
        + "                                } == true)"
    )
    content = replace_text(content, old_lookup, new_lookup, "chatservice-auto-approve")

    old_grant = (
        "                        ApprovalScope.ChatScope -> me.rerere.rikkahub.data.ai.tools" + NL
        + "                            .ToolApprovalAllowList.grantForChat(conversationId, toolName)" + NL
        + "                        ApprovalScope.Always -> grantAlwaysScope(conversationId, toolName)"
    )
    new_grant = (
        "                        ApprovalScope.ChatScope -> {" + NL
        + "                            // rhApprovalIdentity: 组级按钮把服务器键编码进伪工具名；解码后" + NL
        + "                            // 写服务器级授权，其余工具写审批键（动作级细化）。" + NL
        + "                            val rhServerKey = me.rerere.rikkahub.data.ai.tools.ToolApprovalIdentity" + NL
        + "                                .decodeMcpServerTarget(toolName)" + NL
        + "                            if (rhServerKey != null) {" + NL
        + "                                me.rerere.rikkahub.data.ai.tools.ToolApprovalAllowList" + NL
        + "                                    .grantForChatMcpServer(conversationId, rhServerKey)" + NL
        + "                            } else {" + NL
        + "                                me.rerere.rikkahub.data.ai.tools.ToolApprovalAllowList.grantForChat(" + NL
        + "                                    conversationId," + NL
        + "                                    resolveApprovalKey(conversationId, toolCallId, toolName)," + NL
        + "                                )" + NL
        + "                            }" + NL
        + "                        }" + NL
        + "                        ApprovalScope.Always -> {" + NL
        + "                            val rhServerKey = me.rerere.rikkahub.data.ai.tools.ToolApprovalIdentity" + NL
        + "                                .decodeMcpServerTarget(toolName)" + NL
        + "                            if (rhServerKey != null) {" + NL
        + "                                toolApprovalPreferences.grantMcpServerAlways(rhServerKey)" + NL
        + "                            } else {" + NL
        + "                                grantAlwaysScope(" + NL
        + "                                    conversationId," + NL
        + "                                    resolveApprovalKey(conversationId, toolCallId, toolName)," + NL
        + "                                )" + NL
        + "                            }" + NL
        + "                        }"
    )
    content = replace_text(content, old_grant, new_grant, "chatservice-grant-key")

    fn_anchor = '    /** Always-scope grant for [toolName]. Workspace tools (the "workspace_" prefix,'
    fn_block = (
        "    /** rhApprovalIdentity: 由 toolCallId 找到待审批工具的入参，复算审批键。" + NL
        + "     *  失败一律回落工具名 —— 绝不能因为找不到消息就丢掉用户刚点的「始终允许」。" + NL
        + "     */" + NL
        + "    private fun resolveApprovalKey(" + NL
        + "        conversationId: Uuid," + NL
        + "        toolCallId: String," + NL
        + "        fallback: String," + NL
        + "    ): String = runCatching {" + NL
        + "        val conversation = getOrCreateSession(conversationId).state.value" + NL
        + "        val part = conversation.messageNodes.asSequence()" + NL
        + "            .flatMap { node -> node.messages.asSequence() }" + NL
        + "            .flatMap { message -> message.parts.asSequence() }" + NL
        + "            .filterIsInstance<UIMessagePart.Tool>()" + NL
        + "            .firstOrNull { it.toolCallId == toolCallId }" + NL
        + "        if (part == null) {" + NL
        + "            fallback" + NL
        + "        } else {" + NL
        + "            me.rerere.rikkahub.data.ai.tools.ToolApprovalIdentity.keyOfName(" + NL
        + "                part.toolName," + NL
        + "                part.inputAsJson() as? kotlinx.serialization.json.JsonObject," + NL
        + "            )" + NL
        + "        }" + NL
        + "    }.getOrDefault(fallback)" + NL
        + "" + NL
        + fn_anchor
    )
    content = replace_text(content, fn_anchor, fn_block, "chatservice-resolve-key")
    write(path, content)


# ---------------- E. GenerationHandler : pass approval key ----------------
def edit_generation_handler():
    path = "app/src/main/java/me/rerere/rikkahub/data/ai/GenerationHandler.kt"
    content = read(path)
    if MARK in content:
        diag("generationhandler already patched")
        return
    old = "                            if (isToolAutoApproved(tool.toolName)) {"
    new = (
        "                            // rhApprovalIdentity: 自动放行按审批键判定（复合工具细化到动作）" + NL
        + "                            val rhApprovalKey = if (toolDef != null) {" + NL
        + "                                me.rerere.rikkahub.data.ai.tools.ToolApprovalIdentity.keyOf(" + NL
        + "                                    toolDef," + NL
        + "                                    tool.inputAsJson() as? kotlinx.serialization.json.JsonObject," + NL
        + "                                )" + NL
        + "                            } else {" + NL
        + "                                tool.toolName" + NL
        + "                            }" + NL
        + "                            if (isToolAutoApproved(rhApprovalKey)) {"
    )
    content = replace_text(content, old, new, "genhandler-key")
    write(path, content)


# ---------------- F. ChatMessageTools : group-level buttons ----------------
def edit_approval_card():
    path = "app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageTools.kt"
    content = read(path)
    if MARK in content:
        diag("approval card already patched")
        return
    old = (
        "                    val allowAlwaysButton = me.rerere.rikkahub.data.ai.tools.ToolApprovalDefaults" + NL
        + "                        .allowsAlwaysAllow(tool.toolName)"
    )
    new = (
        old + NL
        + "                    // rhApprovalIdentity: MCP 服务器级授权（组级按钮）。只在工具本身允许" + NL
        + "                    // 「始终允许」时出现，点一下等于对整台服务器授权。" + NL
        + "                    if (allowAlwaysButton) {" + NL
        + "                        val rhMcpServerKey = me.rerere.rikkahub.data.ai.tools.ToolApprovalIdentity" + NL
        + "                            .mcpServerKeyOf(tool.toolName)" + NL
        + "                        if (rhMcpServerKey != null) {" + NL
        + "                            val rhServerTarget = me.rerere.rikkahub.data.ai.tools.ToolApprovalIdentity" + NL
        + "                                .encodeMcpServerTarget(rhMcpServerKey)" + NL
        + "                            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {" + NL
        + "                                Text(" + NL
        + "                                    text = stringResource(R.string.tool_approval_mcp_server_group_hint)," + NL
        + "                                    style = MaterialTheme.typography.labelSmall," + NL
        + "                                    color = MaterialTheme.colorScheme.onSurfaceVariant," + NL
        + "                                )" + NL
        + "                                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {" + NL
        + "                                    androidx.compose.material3.OutlinedButton(onClick = {" + NL
        + "                                        inFlight = true" + NL
        + "                                        onToolApproval(" + NL
        + "                                            tool.toolCallId, true, " + Q + Q + "," + NL
        + "                                            me.rerere.rikkahub.service.ChatService.ApprovalScope.ChatScope," + NL
        + "                                            rhServerTarget," + NL
        + "                                        )" + NL
        + "                                    }) {" + NL
        + "                                        Text(stringResource(R.string.tool_approval_mcp_server_allow_chat))" + NL
        + "                                    }" + NL
        + "                                    androidx.compose.material3.OutlinedButton(onClick = {" + NL
        + "                                        inFlight = true" + NL
        + "                                        onToolApproval(" + NL
        + "                                            tool.toolCallId, true, " + Q + Q + "," + NL
        + "                                            me.rerere.rikkahub.service.ChatService.ApprovalScope.Always," + NL
        + "                                            rhServerTarget," + NL
        + "                                        )" + NL
        + "                                    }) {" + NL
        + "                                        Text(stringResource(R.string.tool_approval_mcp_server_allow_always))" + NL
        + "                                    }" + NL
        + "                                }" + NL
        + "                            }" + NL
        + "                        }" + NL
        + "                    }"
    )
    content = replace_text(content, old, new, "approval-card-server-buttons")
    write(path, content)


def main():
    for label, fn in (
        ("tool-kt", edit_tool_kt),
        ("allow-list", edit_allow_list),
        ("prefs", edit_prefs),
        ("chat-service", edit_chat_service),
        ("generation-handler", edit_generation_handler),
        ("approval-card", edit_approval_card),
    ):
        try:
            fn()
        except SystemExit:
            failed.append(label)
        except Exception as e:
            diag("EXCEPTION " + label + ": " + repr(e))
            failed.append(label)

    try:
        add_strings(
            "app/src/main/res/values/strings.xml",
            [
                ("tool_approval_mcp_server_group_hint", "Approve the whole MCP server instead of this single tool"),
                ("tool_approval_mcp_server_allow_chat", "Server: this chat"),
                ("tool_approval_mcp_server_allow_always", "Server: always"),
            ],
            "strings-en",
        )
        add_strings(
            "app/src/main/res/values-zh/strings.xml",
            [
                ("tool_approval_mcp_server_group_hint", "按整台 MCP 服务器授权（而不是单个工具）"),
                ("tool_approval_mcp_server_allow_chat", "服务器：本会话"),
                ("tool_approval_mcp_server_allow_always", "服务器：始终"),
            ],
            "strings-zh",
        )
    except SystemExit:
        failed.append("strings")
    except Exception as e:
        diag("EXCEPTION strings: " + repr(e))
        failed.append("strings")

    diag("applied=" + str(len(applied)) + " failed=" + str(len(failed)))
    if applied:
        print("::notice title=batch271-applied::" + ",".join(applied))
    if failed:
        print("::error title=batch271-FAILED::" + ",".join(failed))


main()

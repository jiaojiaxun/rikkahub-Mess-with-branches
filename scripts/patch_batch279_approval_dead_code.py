#!/usr/bin/env python3
# batch279: dead-code cleanup -- drop the two MCP-server helpers that no caller reaches.
#
# revokeForChatMcpServer / listMcpServersForChat were added with the server-level grant
# foundation, but there is no surface for per-chat server grants (the settings page
# manages the persistent set, and clearChat already drops the in-memory ones on /new).
# Keeping uncalled helpers is exactly the "written but unreachable" pattern the project
# audits for, so they go. grantForChatMcpServer / isMcpServerAllowedForChat stay (used by
# ChatService).
# MARK=rhApprovalDeadCodeCleanup
import sys
from pathlib import Path

MARK = "rhApprovalDeadCodeCleanup"
NL = chr(10)
DIAG = "ci_diag_batch279.txt"
PATH = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/ToolApprovalAllowList.kt"
applied = []


def diag(msg):
    try:
        with open(DIAG, "a", encoding="utf-8") as f:
            f.write(msg + NL)
    except Exception:
        pass


def fail(msg):
    diag("FAIL " + msg)
    print("::error title=batch279::" + msg)
    raise SystemExit(0)


def drop_window(content, old_lines, replacement_lines, label):
    lines = content.split(NL)
    n = len(old_lines)
    hits = []
    for i in range(0, len(lines) - n + 1):
        ok = True
        for j in range(n):
            if lines[i + j].strip() != old_lines[j].strip():
                ok = False
                break
        if ok:
            hits.append(i)
    if len(hits) != 1:
        fail(label + " window count=" + str(len(hits)))
    lines[hits[0]:hits[0] + n] = replacement_lines
    applied.append(label)
    return NL.join(lines)


def main():
    p = Path(PATH)
    if not p.exists():
        fail("missing file: " + PATH)
    content = p.read_text(encoding="utf-8")
    if MARK in content:
        diag("already cleaned")
    else:
        revoke_block = [
            "    fun revokeForChatMcpServer(conversationId: Uuid, serverKey: String) {",
            "        perChatMcpServer.remove(serverGrantKey(conversationId, serverKey))",
            "    }",
            "",
        ]
        content = drop_window(content, revoke_block, [], "drop-revoke")

        list_block = [
            "    fun listMcpServersForChat(conversationId: Uuid): List<String> {",
            "        val prefix = \"${conversationId}::srv::\"",
            "        return perChatMcpServer.asSequence()",
            "            .filter { it.startsWith(prefix) }",
            "            .map { it.removePrefix(prefix) }",
            "            .sorted()",
            "            .toList()",
            "    }",
            "",
        ]
        content = drop_window(content, list_block, [], "drop-list")

        content = content.replace(
            "    // rhApprovalIdentity: 会话级 MCP 服务器授权（「本会话允许整个 <服务器>」）。",
            "    // rhApprovalIdentity: 会话级 MCP 服务器授权（「本会话允许整个 <服务器>」）。" + NL
            + "    // " + MARK + ": 只保留有调用方的 grant/isAllowed；撤销与列表无 UI 入口，已删除。",
            1,
        )
        p.write_text(content, encoding="utf-8")

    check = p.read_text(encoding="utf-8")
    missing = []
    for needle in ("fun grantForChatMcpServer(", "fun isMcpServerAllowedForChat("):
        if needle not in check:
            missing.append(needle)
    stale = []
    for needle in ("fun revokeForChatMcpServer(", "fun listMcpServersForChat("):
        if needle in check:
            stale.append(needle)
    if missing or stale:
        fail("verify failed missing=" + ",".join(missing) + " stale=" + ",".join(stale))
    diag("applied=" + ",".join(applied) + " verify=ok")
    print("::notice title=batch279-ok::" + ",".join(applied))


main()

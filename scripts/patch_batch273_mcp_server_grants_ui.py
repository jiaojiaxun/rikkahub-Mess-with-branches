#!/usr/bin/env python3
# batch273 (Phase 2): Settings -> Tool approvals gets an MCP server section.
#   Each server row toggles ToolApprovalPreferences.grantMcpServerAlways / revokeMcpServerAlways.
# MARK=rhApprovalIdentityMcpUi
import sys
from pathlib import Path

MARK = "rhApprovalIdentityMcpUi"
NL = chr(10)
Q = chr(34)
DIAG = "ci_diag_batch273.txt"
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
    print("::error title=batch273::" + msg)
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


def add_strings(path, pairs, label):
    content = read(path)
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


def edit_page():
    path = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingToolApprovalsPage.kt"
    content = read(path)
    if MARK in content:
        diag("page already patched")
        return

    imp_anchor = "import me.rerere.rikkahub.data.preferences.ToolApprovalPreferences"
    content = insert_after_line(
        content, imp_anchor,
        "import me.rerere.rikkahub.data.datastore.SettingsStore // " + MARK,
        "page-import",
    )

    state_anchor = "    val yolo by prefs.globalYoloFlow.collectAsStateWithLifecycle(initialValue = false)"
    state_block = (
        "    // " + MARK + ": MCP 服务器级授权（与单工具授权并列，互不覆盖）" + NL
        + "    val settingsStore: SettingsStore = koinInject()" + NL
        + "    val appSettings by settingsStore.settingsFlow.collectAsStateWithLifecycle(" + NL
        + "        initialValue = me.rerere.rikkahub.data.datastore.Settings.dummy()" + NL
        + "    )" + NL
        + "    val mcpServerAlways by prefs.mcpServerAlwaysFlow.collectAsStateWithLifecycle(" + NL
        + "        initialValue = emptySet()" + NL
        + "    )" + NL
        + "    // 候选服务器键：已配置服务器 + 已授权键反推（服务器被改名/删除后仍可撤销授权）" + NL
        + "    val mcpServerKeys: List<String> = remember(appSettings.mcpServers, granted, mcpServerAlways) {" + NL
        + "        val fromConfig = appSettings.mcpServers.map { server ->" + NL
        + "            " + Q + "mcp__" + Q + " + server.id.toString().take(8).replace(" + Q + "-" + Q + ", " + Q + Q + ") + " + Q + "_" + Q + " + server.commonOptions.name" + NL
        + "        }" + NL
        + "        val fromGrants = (granted + mcpServerAlways)" + NL
        + "            .filter { it.startsWith(" + Q + "mcp__" + Q + ") && it.indexOf(" + Q + "__" + Q + ", 5) > 0 }" + NL
        + "            .map { it.substringBeforeLast(" + Q + "__" + Q + ") }" + NL
        + "        (fromConfig + fromGrants).filter { it.isNotBlank() }.distinct().sorted()" + NL
        + "    }"
    )
    content = insert_after_line(content, state_anchor, state_block, "page-state")

    ui_anchor = "            if (granted.isEmpty()) {"
    ui_block = (
        "            if (mcpServerKeys.isNotEmpty()) {" + NL
        + "                item {" + NL
        + "                    Text(" + NL
        + "                        text = stringResource(R.string.setting_page_tool_approvals_mcp_header)," + NL
        + "                        style = MaterialTheme.typography.bodyMedium," + NL
        + "                        color = MaterialTheme.colorScheme.onSurfaceVariant," + NL
        + "                        modifier = Modifier.padding(horizontal = 16.dp)," + NL
        + "                    )" + NL
        + "                }" + NL
        + "                item {" + NL
        + "                    Column(" + NL
        + "                        modifier = Modifier" + NL
        + "                            .fillMaxWidth()" + NL
        + "                            .padding(horizontal = 8.dp)," + NL
        + "                        verticalArrangement = Arrangement.spacedBy(8.dp)," + NL
        + "                    ) {" + NL
        + "                        mcpServerKeys.forEach { serverKey ->" + NL
        + "                            val serverGranted = serverKey in mcpServerAlways" + NL
        + "                            Row(" + NL
        + "                                modifier = Modifier" + NL
        + "                                    .fillMaxWidth()" + NL
        + "                                    .clip(RoundedCornerShape(12.dp))" + NL
        + "                                    .background(MaterialTheme.colorScheme.surfaceVariant)" + NL
        + "                                    .padding(horizontal = 16.dp, vertical = 12.dp)," + NL
        + "                                horizontalArrangement = Arrangement.SpaceBetween," + NL
        + "                                verticalAlignment = Alignment.CenterVertically," + NL
        + "                            ) {" + NL
        + "                                Column(" + NL
        + "                                    modifier = Modifier.weight(1f)," + NL
        + "                                    verticalArrangement = Arrangement.spacedBy(2.dp)," + NL
        + "                                ) {" + NL
        + "                                    Text(" + NL
        + "                                        text = serverKey.removePrefix(" + Q + "mcp__" + Q + ")," + NL
        + "                                        style = MaterialTheme.typography.titleSmall," + NL
        + "                                        fontWeight = FontWeight.Bold," + NL
        + "                                    )" + NL
        + "                                    Text(" + NL
        + "                                        text = stringResource(" + NL
        + "                                            if (serverGranted) R.string.setting_page_tool_approvals_mcp_on" + NL
        + "                                            else R.string.setting_page_tool_approvals_mcp_off" + NL
        + "                                        )," + NL
        + "                                        style = MaterialTheme.typography.bodySmall," + NL
        + "                                        color = MaterialTheme.colorScheme.onSurfaceVariant," + NL
        + "                                    )" + NL
        + "                                }" + NL
        + "                                Switch(" + NL
        + "                                    checked = serverGranted," + NL
        + "                                    onCheckedChange = { want ->" + NL
        + "                                        scope.launch {" + NL
        + "                                            if (want) prefs.grantMcpServerAlways(serverKey)" + NL
        + "                                            else prefs.revokeMcpServerAlways(serverKey)" + NL
        + "                                        }" + NL
        + "                                    }," + NL
        + "                                )" + NL
        + "                            }" + NL
        + "                        }" + NL
        + "                    }" + NL
        + "                }" + NL
        + "            }" + NL
        + ui_anchor
    )
    content = replace_text(content, ui_anchor, ui_block, "page-ui")
    write(path, content)


def main():
    try:
        edit_page()
    except SystemExit:
        failed.append("page")
    except Exception as e:
        diag("EXCEPTION page: " + repr(e))
        failed.append("page")
    try:
        add_strings(
            "app/src/main/res/values/strings.xml",
            [
                ("setting_page_tool_approvals_mcp_header", "MCP server approvals"),
                ("setting_page_tool_approvals_mcp_on", "Whole server allowed"),
                ("setting_page_tool_approvals_mcp_off", "Ask for every tool"),
            ],
            "strings-en",
        )
        add_strings(
            "app/src/main/res/values-zh/strings.xml",
            [
                ("setting_page_tool_approvals_mcp_header", "MCP 服务器授权"),
                ("setting_page_tool_approvals_mcp_on", "整台服务器已放行"),
                ("setting_page_tool_approvals_mcp_off", "逐个工具询问"),
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
        print("::notice title=batch273-applied::" + ",".join(applied))
    if failed:
        print("::error title=batch273-FAILED::" + ",".join(failed))


main()

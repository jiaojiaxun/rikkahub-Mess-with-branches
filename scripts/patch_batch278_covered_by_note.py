#!/usr/bin/env python3
# batch278: annotate tool rows whose server already has a persistent grant
# ("covered by server-level approval") on the tool-approvals settings page.
# MARK=rhApprovalIdentityCovered
import sys
from pathlib import Path

MARK = "rhApprovalIdentityCovered"
NL = chr(10)
Q = chr(34)
DIAG = "ci_diag_batch278.txt"
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
    print("::error title=batch278::" + msg)
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
    old = (
        "                        granted.sorted().forEach { toolName ->" + NL
        + "                            item(" + NL
        + "                                headlineContent = { Text(toolName) },"
    )
    new = (
        "                        granted.sorted().forEach { toolName ->" + NL
        + "                            // " + MARK + ": 该单工具授权已被整台服务器的授权覆盖时标注" + NL
        + "                            val rhCoveredServerKey = me.rerere.rikkahub.data.ai.tools.ToolApprovalIdentity" + NL
        + "                                .mcpServerKeyOf(toolName)" + NL
        + "                            val rhCoveredNote: (@Composable () -> Unit)? =" + NL
        + "                                if (rhCoveredServerKey != null && rhCoveredServerKey in mcpServerAlways) {" + NL
        + "                                    { Text(stringResource(R.string.setting_page_tool_approvals_mcp_covered)) }" + NL
        + "                                } else {" + NL
        + "                                    null" + NL
        + "                                }" + NL
        + "                            item(" + NL
        + "                                headlineContent = { Text(toolName) }," + NL
        + "                                supportingContent = rhCoveredNote,"
    )
    content = replace_text(content, old, new, "page-covered-note")
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
            [("setting_page_tool_approvals_mcp_covered", "Covered by server-level approval")],
            "strings-en",
        )
        add_strings(
            "app/src/main/res/values-zh/strings.xml",
            [("setting_page_tool_approvals_mcp_covered", "已由服务器级授权覆盖")],
            "strings-zh",
        )
    except SystemExit:
        failed.append("strings")
    except Exception as e:
        diag("EXCEPTION strings: " + repr(e))
        failed.append("strings")
    diag("applied=" + ",".join(applied) + " failed=" + ((",".join(failed)) if failed else "none"))
    if failed:
        print("::error title=batch278-FAILED::" + ",".join(failed))
    else:
        print("::notice title=batch278-ok::" + ",".join(applied))


main()

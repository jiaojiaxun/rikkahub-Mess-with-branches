#!/usr/bin/env python3
# rhLocalTerminal363: 修正 362 的 E 锚点（probe 用错了方向）
#
# 362 的 patch() 幂等判断是 `if probe in text: already`。
#   A/B/C/D/F 的 probe 都是「新增内容」，方向正确（未改时不存在）。
#   E 的 probe 却写成了 `workspace_terminal_not_supported` —— 这是**要删掉的旧内容**，
#   在未改文件里必然存在 -> 直接被判 already 跳过 -> when 分支删不掉，本地工作区仍显示
#   「不支持」。这条由 362 自己的 page-no-unsupported 检查兜住（会 FAIL），但功能仍不可达。
#
# 教训：删除型补丁的幂等特征必须用「删除完成后的形态」，不能用被删内容本身。
#
# 本批把 A/B/C/D/E/F 全部按正确 probe 重放一遍（幂等安全）：
#   A/B/C/D/F 若 362 已改过 -> probe 命中跳过
#   E 若仍未删 -> 用「workspace==null 分支紧跟 else」作为完成特征判断
#
# 另外顺手核对 361 是否落地（runTerminal 前 patcher.patch），只读，不改。

import os
import sys

MARK = "rhLocalTerminal363"
REPO = os.getcwd()
APP = os.path.join(REPO, "app", "src", "main", "java", "me", "rerere", "rikkahub", "ui", "pages", "extensions", "workspace")
MANAGER = os.path.join(APP, "WorkspaceTerminalSessionManager.kt")
PAGE = os.path.join(APP, "WorkspaceTerminalPage.kt")
PROOT = os.path.join(REPO, "workspace", "src", "main", "java", "me", "rerere", "workspace", "ProotShellRunner.kt")
DIAG = os.path.join(REPO, "ci_diag_batch363_page_fix.txt")

A_OLD = (
    'internal data class WorkspaceTerminalTabsState(\n'
    '    val tabs: List<WorkspaceTerminalTab> = emptyList(),\n'
    '    val selectedTabId: Long? = null,\n'
    '    val isCreating: Boolean = false,\n'
    '    val nextTabNumber: Int = 1,\n'
    ')'
)
A_NEW = (
    'internal data class WorkspaceTerminalTabsState(\n'
    '    val tabs: List<WorkspaceTerminalTab> = emptyList(),\n'
    '    val selectedTabId: Long? = null,\n'
    '    val isCreating: Boolean = false,\n'
    '    val nextTabNumber: Int = 1,\n'
    '    /** rhLocalTerminal362: 最近一次建会话失败的原因, 供终端页空态展示 */\n'
    '    val lastError: String? = null,\n'
    ')'
)

B_OLD = (
    '        val session = runCatching {\n'
    '            createWorkspaceTerminalSession(\n'
    '                transport = terminalTransport(workspace),\n'
    '                root = root,\n'
    '                client = client,\n'
    '            )\n'
    '        }.onFailure { error ->\n'
    '            Log.e(TAG, "Failed to create terminal for workspace $root", error)\n'
    '        }.getOrNull()\n'
    '\n'
    '        if (session == null) {\n'
    '            updateState(root) { it.copy(isCreating = false) }\n'
    '            return@withContext\n'
    '        }\n'
)
B_NEW = (
    '        var failure: String? = null\n'
    '        val session = runCatching {\n'
    '            createWorkspaceTerminalSession(\n'
    '                transport = terminalTransport(workspace),\n'
    '                root = root,\n'
    '                client = client,\n'
    '            )\n'
    '        }.onFailure { error ->\n'
    '            Log.e(TAG, "Failed to create terminal for workspace $root", error)\n'
    '            failure = error.message ?: error.toString()\n'
    '        }.getOrNull()\n'
    '\n'
    '        if (session == null) {\n'
    '            updateState(root) { it.copy(isCreating = false, lastError = failure) }\n'
    '            return@withContext\n'
    '        }\n'
)

C_OLD = (
    '            state.copy(\n'
    '                tabs = state.tabs + tab,\n'
    '                selectedTabId = tab.id,\n'
    '                isCreating = false,\n'
    '                nextTabNumber = tabNumber + 1,\n'
    '            )'
)
C_NEW = (
    '            state.copy(\n'
    '                tabs = state.tabs + tab,\n'
    '                selectedTabId = tab.id,\n'
    '                isCreating = false,\n'
    '                nextTabNumber = tabNumber + 1,\n'
    '                lastError = null,\n'
    '            )'
)

D_OLD = '        if (ws != null && ws.isSsh()) {'
D_NEW = '        if (ws != null) {'

E_OLD = (
    '                workspace?.isSsh() != true -> TerminalPlaceholder(\n'
    '                    stringResource(R.string.workspace_terminal_not_supported)\n'
    '                )\n'
    '\n'
    '                else -> Column(modifier = Modifier.fillMaxSize()) {'
)
E_NEW = '                else -> Column(modifier = Modifier.fillMaxSize()) {'
# 删除完成后的形态（workspace==null 分支直接跟 else）
E_DONE = (
    '                workspace == null -> TerminalPlaceholder(stringResource(R.string.workspace_terminal_loading))\n'
    '                else -> Column(modifier = Modifier.fillMaxSize()) {'
)

F_OLD = (
    '                        } else if (tabsState.isCreating) {\n'
    '                            TerminalPlaceholder(stringResource(R.string.workspace_terminal_loading))\n'
    '                        }'
)
F_NEW = (
    '                        } else if (tabsState.isCreating) {\n'
    '                            TerminalPlaceholder(stringResource(R.string.workspace_terminal_loading))\n'
    '                        } else if (tabsState.lastError != null) {\n'
    '                            TerminalPlaceholder(tabsState.lastError ?: "")\n'
    '                        }'
)

OUT = []


def log(line):
    OUT.append(line)
    print(line)


def strip_literals(source):
    out = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch == '"' or ch == "'":
            quote = ch
            i += 1
            while i < n:
                if source[i] == "\\":
                    i += 2
                    continue
                if source[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            while i < n and source[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "*":
            i += 2
            while i + 1 < n and not (source[i] == "*" and source[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def counts(text):
    stripped = strip_literals(text)
    return stripped.count("{") - stripped.count("}"), stripped.count("(") - stripped.count(")")


def patch(path, old, new, label, probe):
    if not os.path.isfile(path):
        log("missing-file:" + label)
        return ["missing-file:" + label]
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    if probe in text:
        log("done:" + label)
        return []
    hits = text.count(old)
    if hits != 1:
        log("anchor-count:" + label + ":" + str(hits))
        return ["anchor:" + label + ":" + str(hits)]
    before = counts(text)
    updated = text.replace(old, new)
    after = counts(updated)
    log("braces:" + label + ":" + str(before) + "->" + str(after))
    if before != after:
        return ["braces:" + label + ":" + str(before) + "->" + str(after)]
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(updated)
    log("wrote:" + label + ":" + str(len(updated)))
    return []


def main():
    failures = []

    failures += patch(MANAGER, A_OLD, A_NEW, "state-lasterror", "lastError: String?")
    failures += patch(MANAGER, B_OLD, B_NEW, "capture-failure", "lastError = failure")
    failures += patch(MANAGER, C_OLD, C_NEW, "clear-failure", "lastError = null,")
    failures += patch(PAGE, D_OLD, D_NEW, "page-effect", "if (ws != null) {")
    # 关键修正：probe 用「删除完成后的形态」
    failures += patch(PAGE, E_OLD, E_NEW, "page-when", E_DONE)
    failures += patch(PAGE, F_OLD, F_NEW, "page-error-slot", "tabsState.lastError != null")

    try:
        with open(MANAGER, "r", encoding="utf-8") as handle:
            mgr = handle.read()
        with open(PAGE, "r", encoding="utf-8") as handle:
            page = handle.read()
        with open(PROOT, "r", encoding="utf-8") as handle:
            proot = handle.read()
        checks = [
            ("state-has-lasterror", "val lastError: String? = null," in mgr),
            ("failure-recorded", "lastError = failure)" in mgr),
            ("failure-cleared", "lastError = null," in mgr),
            ("page-no-ssh-effect", "ws.isSsh()" not in page),
            ("page-no-unsupported", "workspace_terminal_not_supported" not in page),
            ("page-shows-error", "tabsState.lastError != null" in page),
            ("session-create-kept", "manager.ensureSession(ws)" in page),
            ("361-patch-in-launch", "runCatching { patcher.patch(context.linuxDir) }" in proot),
        ]
        for name, ok in checks:
            log("check:" + name + ":" + ("ok" if ok else "FAIL"))
            if not ok:
                failures.append("check:" + name)
    except OSError as error:
        failures.append("cross:" + str(error))

    if failures:
        log("RESULT:FAIL")
        log("failures:" + "|".join(failures))
    else:
        log("RESULT:OK")

    with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(OUT) + "\n")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()

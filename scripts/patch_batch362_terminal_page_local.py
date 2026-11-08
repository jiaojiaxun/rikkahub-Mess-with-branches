#!/usr/bin/env python3
# rhLocalTerminal362: 终端页放开 SSH-only 限制 + 失败原因可见
#
# 实读 snapshot 发现的功能不可达（359/360 之后仍存在）：
#   WorkspaceTerminalPage.kt 有两处写死 SSH：
#     1) LaunchedEffect: `if (ws != null && ws.isSsh()) { manager.ensureSession(ws) ... }`
#        -> 本地工作区进页面根本不会建会话
#     2) when 分支: `workspace?.isSsh() != true -> TerminalPlaceholder(not_supported)`
#        -> 本地工作区直接显示「不支持」
#   也就是说：能力位开了、入口出现了、transport 也支持本地了，但点进去被页面自己拦住。
#
# 本批三件事：
#   A) Manager 的 TabsState 增加 lastError，建会话失败时记录原因
#   B) createTab 的失败路径写 lastError，成功路径清空
#   C) Page 去掉两处 SSH 硬判断，空态增加「失败原因」展示
#      （否则 rootfs 未就绪时页面会一直停在「正在加载」，用户看不出为什么）
#
# 每处改动都用内容特征判断，不共用 MARK。注意 `var tabsState by remember` 是委托属性，
# 编译器无法智能转换，所以 `tabsState.lastError ?: ""` 的 Elvis 是必需的。

import os
import sys

MARK = "rhLocalTerminal362"
REPO = os.getcwd()
APP = os.path.join(REPO, "app", "src", "main", "java", "me", "rerere", "rikkahub", "ui", "pages", "extensions", "workspace")
MANAGER = os.path.join(APP, "WorkspaceTerminalSessionManager.kt")
PAGE = os.path.join(APP, "WorkspaceTerminalPage.kt")
DIAG = os.path.join(REPO, "ci_diag_batch362_terminal_page_local.txt")

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
    '    /** ' + MARK + ': 最近一次建会话失败的原因, 供终端页空态展示 */\n'
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
    """probe: 已经改过的特征串；命中即视为幂等跳过。"""
    if not os.path.isfile(path):
        log("missing-file:" + label)
        return ["missing-file:" + label]
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    if probe in text:
        log("already:" + label)
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
    failures += patch(PAGE, E_OLD, E_NEW, "page-when", "workspace_terminal_not_supported")
    failures += patch(PAGE, F_OLD, F_NEW, "page-error-slot", "tabsState.lastError != null")

    # 复核（以磁盘为准）
    try:
        with open(MANAGER, "r", encoding="utf-8") as handle:
            mgr = handle.read()
        with open(PAGE, "r", encoding="utf-8") as handle:
            page = handle.read()
        checks = [
            ("state-has-lasterror", "val lastError: String? = null," in mgr),
            ("failure-recorded", "lastError = failure)" in mgr),
            ("failure-cleared", "lastError = null," in mgr),
            ("page-no-ssh-effect", "ws.isSsh()" not in page),
            ("page-no-unsupported", "workspace_terminal_not_supported" not in page),
            ("page-shows-error", "tabsState.lastError != null" in page),
            ("session-create-kept", "manager.ensureSession(ws)" in page),
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

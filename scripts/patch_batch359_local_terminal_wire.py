#!/usr/bin/env python3
# rhLocalTerminal359: P2 本地终端 · app 侧接线
#
# 357 给了 libtermux.so + JNI/LocalPtyTransport，358 给了 ProotShellRunner.terminalLaunch，
# 本批把 app 层接上，并放开 local 的 terminal 能力位。
#
# 已核实的既有事实（读 snapshot 源码）：
#   · WorkspaceEntity.supportsTerminal() = capabilities().terminal && shellStatus != DISABLED
#     —— 入口门控本来就走能力位，所以把 LOCAL.terminal 改成 true 即生效，无需改 UI 判断
#   · WorkspaceManager 在 repositoryModule 里已是 single，可直接 get()
#   · WorkspaceTerminalSessionManager 是 internal constructor，AppModule 同模块可访问
#
# 三处改动：
#   1) Workspace.kt            LOCAL.capabilities.terminal false -> true
#   2) WorkspaceTerminalSessionManager.kt  构造注入 WorkspaceManager + terminalTransport 支持本地
#   3) AppModule.kt            注册处补 workspaceManager = get()
#
# 另附只读诊断：统计详情页/列表页里 supportsTerminal() 与 isSsh() 的出现次数，
# 用来确认入口门控是否真的走能力位（不改代码，只观测）。

import os
import sys

MARK = "rhLocalTerminal359"
REPO = os.getcwd()
APP = os.path.join(REPO, "app", "src", "main", "java", "me", "rerere", "rikkahub")

WORKSPACE_KT = os.path.join(REPO, "workspace", "src", "main", "java", "me", "rerere", "workspace", "Workspace.kt")
MANAGER_KT = os.path.join(APP, "ui", "pages", "extensions", "workspace", "WorkspaceTerminalSessionManager.kt")
APP_MODULE = os.path.join(APP, "di", "AppModule.kt")
DETAIL_PAGE = os.path.join(APP, "ui", "pages", "extensions", "workspace", "WorkspaceDetailPage.kt")
SIDEBAR_PAGE = os.path.join(APP, "ui", "pages", "extensions", "workspace", "WorkspacePage.kt")
DIAG = os.path.join(REPO, "ci_diag_batch359_local_terminal_wire.txt")

T1_OLD = '            rootfs = true,\n            terminal = false,'
T1_NEW = '            rootfs = true,\n            terminal = true,'

T2A_OLD = (
    'class WorkspaceTerminalSessionManager internal constructor(\n'
    '    context: Context,\n'
    '    private val appScope: AppScope,\n'
    '    private val workspaceRepository: WorkspaceRepository,\n'
    ') {'
)
T2A_NEW = (
    'class WorkspaceTerminalSessionManager internal constructor(\n'
    '    context: Context,\n'
    '    private val appScope: AppScope,\n'
    '    private val workspaceRepository: WorkspaceRepository,\n'
    '    // ' + MARK + ': 本地工作区的终端启动参数由 ProotShellRunner 提供\n'
    '    private val workspaceManager: me.rerere.workspace.WorkspaceManager,\n'
    ') {'
)

T2B_OLD = (
    '    private fun terminalTransport(workspace: WorkspaceEntity): TerminalTransport {\n'
    '        check(workspace.isSsh()) { "Interactive terminal is only available for SSH workspaces" }\n'
    '        val settings = workspace.sshSettings() ?: error("SSH workspace config is missing: ${workspace.id}")\n'
)
T2B_NEW = (
    '    private fun terminalTransport(workspace: WorkspaceEntity): TerminalTransport {\n'
    '        if (!workspace.isSsh()) {\n'
    '            // ' + MARK + ': 本地工作区走 libtermux.so 的伪终端。\n'
    '            // 参数由 ProotShellRunner 组装(rootfs / bind mount / env 白名单与命令执行完全一致),\n'
    '            // 这里只负责把 argv 交给 TerminalTransport。\n'
    '            val launch = workspaceManager.terminalLaunch(\n'
    '                root = workspace.root,\n'
    '                shellCompatibilityMode = workspace.shellCompatibilityMode,\n'
    '            ) ?: error("本地终端不可用：rootfs 未安装、农场缺失或兼容模式已开启，请先在工作区详情里安装 Rootfs")\n'
    '            return com.termux.terminal.LocalPtyTransport(\n'
    '                launch.executable,\n'
    '                launch.cwd,\n'
    '                launch.args.toTypedArray(),\n'
    '                launch.env.toTypedArray(),\n'
    '            )\n'
    '        }\n'
    '        val settings = workspace.sshSettings() ?: error("SSH workspace config is missing: ${workspace.id}")\n'
)

T3_OLD = (
    '        me.rerere.rikkahub.ui.pages.extensions.workspace.WorkspaceTerminalSessionManager(\n'
    '            context = get(),\n'
    '            appScope = get(),\n'
    '            workspaceRepository = get(),\n'
    '        )'
)
T3_NEW = (
    '        me.rerere.rikkahub.ui.pages.extensions.workspace.WorkspaceTerminalSessionManager(\n'
    '            context = get(),\n'
    '            appScope = get(),\n'
    '            workspaceRepository = get(),\n'
    '            // ' + MARK + '\n'
    '            workspaceManager = get(),\n'
    '        )'
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


def patch(path, old, new, label):
    if not os.path.isfile(path):
        log("missing-file:" + label)
        return ["missing-file:" + label]
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    if MARK in text:
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


def scan(path, label, needles):
    if not os.path.isfile(path):
        log("scan-missing:" + label)
        return
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    parts = []
    for needle in needles:
        parts.append(needle + "=" + str(text.count(needle)))
    log("scan:" + label + ":" + ",".join(parts))


def main():
    failures = []
    failures += patch(WORKSPACE_KT, T1_OLD, T1_NEW, "workspace-kt")
    failures += patch(MANAGER_KT, T2A_OLD, T2A_NEW, "manager-ctor")
    failures += patch(MANAGER_KT, T2B_OLD, T2B_NEW, "manager-transport")
    failures += patch(APP_MODULE, T3_OLD, T3_NEW, "app-module")

    # 只读观测：入口门控到底走能力位还是写死 isSsh()
    scan(DETAIL_PAGE, "detail", ["supportsTerminal(", "isSsh()", "WorkspaceTerminal"])
    scan(SIDEBAR_PAGE, "list", ["supportsTerminal(", "isSsh()", "WorkspaceTerminal"])

    # 交叉检查：LOCAL 能力位与 Manager 的本地分支必须同时存在
    try:
        with open(WORKSPACE_KT, "r", encoding="utf-8") as handle:
            ws_text = handle.read()
        with open(MANAGER_KT, "r", encoding="utf-8") as handle:
            mgr_text = handle.read()
        if "terminal = true," not in ws_text:
            failures.append("cross:local-terminal-not-enabled")
        if "com.termux.terminal.LocalPtyTransport(" not in mgr_text:
            failures.append("cross:no-local-transport")
        if "workspaceManager.terminalLaunch(" not in mgr_text:
            failures.append("cross:no-terminal-launch")
        if "com.termux.terminal.LocalPtyTransport(" in mgr_text and "workspaceManager" not in mgr_text:
            failures.append("cross:transport-without-manager")
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

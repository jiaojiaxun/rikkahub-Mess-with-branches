#!/usr/bin/env python3
# rhLocalTerminal360: 修 359 的半落地
#
# 359 的 script 缺陷（已由 ci_diag_batch359 证实）：
#   braces:manager-ctor 写入成功后文件里就出现了 MARK，随后 manager-transport 那一步用
#   同一个 MARK 做幂等判断 -> 直接 already 跳过 -> terminalTransport 仍是 SSH-only，
#   而构造参数 workspaceManager 已经加上（未使用，只报警告，所以编译不会被挡住）。
#   diag 里的 failures: cross:no-local-transport | cross:no-terminal-launch 就是这个。
#
# 教训：同一个文件的多处改动不能共用一个 MARK 门控，要么各自独立标记，要么用内容特征判断。
# 本批两处改动都用内容判断，不再依赖 MARK（否则会重演同一个 bug）。
#
# 改动：
#   1) terminalTransport 整段替换：本地 -> workspaceManager.terminalLaunch(...)
#      -> com.termux.terminal.LocalPtyTransport(executable, cwd, args, env)；SSH 分支原样保留
#   2) 类注释里「fork 没有本地终端实现」这句已过期，一并更正

import os
import sys

REPO = os.getcwd()
MANAGER = os.path.join(
    REPO, "app", "src", "main", "java", "me", "rerere", "rikkahub",
    "ui", "pages", "extensions", "workspace", "WorkspaceTerminalSessionManager.kt",
)
DIAG = os.path.join(REPO, "ci_diag_batch360_local_transport_fix.txt")
MARK = "rhLocalTerminal360"

OLD_FN = (
    '    private fun terminalTransport(workspace: WorkspaceEntity): TerminalTransport {\n'
    '        check(workspace.isSsh()) { "Interactive terminal is only available for SSH workspaces" }\n'
    '        val settings = workspace.sshSettings() ?: error("SSH workspace config is missing: ${workspace.id}")\n'
    '        return SshTerminalTransport(address = "${settings.username}@${settings.host}:${settings.port}") { columns, rows ->\n'
    '            workspaceRepository.openSshShell(workspace, columns, rows)\n'
    '        }\n'
    '    }\n'
)

NEW_FN = (
    '    private fun terminalTransport(workspace: WorkspaceEntity): TerminalTransport {\n'
    '        if (!workspace.isSsh()) {\n'
    '            // ' + MARK + ': 本地工作区走 libtermux.so 的伪终端。\n'
    '            // PRoot 参数、bind mount 与 env 白名单都由 ProotShellRunner 组装, 与命令执行完全一致。\n'
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
    '        return SshTerminalTransport(address = "${settings.username}@${settings.host}:${settings.port}") { columns, rows ->\n'
    '            workspaceRepository.openSshShell(workspace, columns, rows)\n'
    '        }\n'
    '    }\n'
)

# 旧注释的判定串（不含 MARK 本身，避免误跳）
OLD_DOC_PROBE = 'fork 没有本地终端实现'
OLD_DOC = (
    ' * 与上游的差异: fork 没有本地终端实现(LocalPtyTransport/terminalLaunch 未搬), 这里只保留\n'
    ' * SSH 分支, 也不做 rootfs 准备(SSH 恒就绪)。\n'
)
NEW_DOC = (
    ' * 本地工作区走 libtermux.so 提供的伪终端(' + MARK + '), SSH 工作区走 SshTerminalTransport;\n'
    ' * 两条路径共用同一套标签页状态机, 页面只负责把 TerminalView 挂到选中的会话上。\n'
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


def main():
    failures = []

    if not os.path.isfile(MANAGER):
        log("missing-file:manager")
        with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("missing-file:manager\nRESULT:FAIL\n")
        sys.exit(1)

    with open(MANAGER, "r", encoding="utf-8") as handle:
        text = handle.read()

    if "com.termux.terminal.LocalPtyTransport(" in text:
        log("already:local-transport")
    else:
        hits = text.count(OLD_FN)
        log("anchor-fn:" + str(hits))
        if hits != 1:
            failures.append("anchor-fn:" + str(hits))
        else:
            before = counts(text)
            text = text.replace(OLD_FN, NEW_FN)
            after = counts(text)
            log("braces-fn:" + str(before) + "->" + str(after))
            if before != after:
                failures.append("braces-fn")
            else:
                log("wrote:fn")

    if OLD_DOC_PROBE not in text:
        log("doc:already")
    else:
        hits = text.count(OLD_DOC)
        log("anchor-doc:" + str(hits))
        if hits == 1:
            before = counts(text)
            text = text.replace(OLD_DOC, NEW_DOC)
            after = counts(text)
            if before != after:
                failures.append("braces-doc")
            else:
                log("wrote:doc")
        else:
            # 注释不是功能，缺失只记录不阻断，但要可见
            log("warn:doc-anchor:" + str(hits))

    with open(MANAGER, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    log("file-size:" + str(len(text)))

    # 复核：以磁盘上的文件为准
    with open(MANAGER, "r", encoding="utf-8") as handle:
        final = handle.read()
    checks = [
        ("has-local-transport", "com.termux.terminal.LocalPtyTransport(" in final),
        ("has-terminal-launch", "workspaceManager.terminalLaunch(" in final),
        ("ssh-branch-kept", "SshTerminalTransport(" in final),
        ("ssh-check-removed", "check(workspace.isSsh())" not in final),
        ("ctor-param-used", final.count("workspaceManager") >= 2),
        ("doc-updated", OLD_DOC_PROBE not in final),
    ]
    for name, ok in checks:
        log("check:" + name + ":" + ("ok" if ok else "FAIL"))
        if not ok:
            failures.append("check:" + name)

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

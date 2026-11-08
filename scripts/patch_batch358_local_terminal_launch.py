#!/usr/bin/env python3
# rhLocalTerminal358: P2 本地终端 · workspace 侧启动参数
#
# 上游把交互式终端抽象成 WorkspaceShellRunner.terminalLaunch(WorkspaceTerminalContext),
# 由 ProotShellRunner 组装 proot 参数、返回 WorkspaceTerminalLaunch(可执行文件/argv/env)。
# fork 的 ProotShellRunner 已被 rhWsProot308/312/313、rhShell337 大幅改写（exec 入口是
# /rh-libs 里的静态 busybox，不是 rootfs 内的 bin/sh），所以这里按 fork 现状重写实现，
# 而不是照抄上游。
#
# 三处改动：
#   1) WorkspaceShellRunner.kt  加 terminalLaunch 默认实现 + 两个数据类
#   2) ProotShellRunner.kt      实现 terminalLaunch（与 execute 共用 PRoot 参数与环境白名单）
#   3) WorkspaceManager.kt      加 terminalLaunch(root, shellCompatibilityMode)
#
# 幂等：MARK 出现即跳过。本批不接线、不改变任何现有行为（终端页仍只给 SSH 用，359 才开）。

import os
import sys

MARK = "rhLocalTerminal358"
REPO = os.getcwd()
WS = os.path.join(REPO, "workspace", "src", "main", "java", "me", "rerere", "workspace")
RUNNER = os.path.join(WS, "WorkspaceShellRunner.kt")
PROOT = os.path.join(WS, "ProotShellRunner.kt")
MANAGER = os.path.join(WS, "WorkspaceManager.kt")
DIAG = os.path.join(REPO, "ci_diag_batch358_local_terminal_launch.txt")

RUNNER_ANCHOR = (
    '    fun start(context: WorkspaceShellContext): Process\n'
    '}\n'
    '\n'
    'data class WorkspaceShellContext('
)
RUNNER_NEW = (
    '    fun start(context: WorkspaceShellContext): Process\n'
    '\n'
    '    /**\n'
    '     * rhLocalTerminal358: 交互式终端的启动参数, 不支持交互式终端时返回 null。\n'
    '     * 与 [execute] 的区别只是 exec 目标换成登录/交互 shell, 且由终端模拟器接管 I/O。\n'
    '     */\n'
    '    fun terminalLaunch(context: WorkspaceTerminalContext): WorkspaceTerminalLaunch? = null\n'
    '}\n'
    '\n'
    '/** 交互式终端启动前的输入: 只带路径与开关, 不带命令文本 */\n'
    'data class WorkspaceTerminalContext(\n'
    '    val filesDir: File,\n'
    '    val linuxDir: File,\n'
    '    val tempDir: File,\n'
    '    val bindMounts: List<WorkspaceBindMount> = emptyList(),\n'
    '    val shellCompatibilityMode: Boolean = false,\n'
    ')\n'
    '\n'
    '/** 交给终端模拟器拉起的本地进程; argv 不含 executable 自身 */\n'
    'data class WorkspaceTerminalLaunch(\n'
    '    val executable: String,\n'
    '    val cwd: String,\n'
    '    val args: List<String>,\n'
    '    val env: List<String>,\n'
    ')\n'
    '\n'
    'data class WorkspaceShellContext('
)

PROOT_ANCHOR = '    private fun preflight(context: WorkspaceShellContext): String? {'
PROOT_NEW = (
    '    /**\n'
    '     * rhLocalTerminal358: 交互式终端。PRoot 参数、bind mount 与 env 白名单与 [prootProcess]\n'
    '     * 保持一致, 只把 exec 目标换成农场里的交互 sh, 并且不带 -c 命令。\n'
    '     *\n'
    '     * 返回 null 表示这台设备当下起不了终端(兼容模式 / rootfs 缺失 / proot 缺文件),\n'
    '     * 调用方据此降级, 而不是让用户看到 UnsatisfiedLinkError 或 exec 失败。\n'
    '     */\n'
    '    override fun terminalLaunch(context: WorkspaceTerminalContext): WorkspaceTerminalLaunch? {\n'
    '        if (context.shellCompatibilityMode) return null\n'
    '        if (!context.linuxDir.isDirectory) return null\n'
    '        if (!WorkspaceBusybox.isReady(context.linuxDir, nativeLibraryDir)) return null\n'
    '        val proot = File(nativeLibraryDir, PROOT_EXEC)\n'
    '        if (!proot.isFile) return null\n'
    '        val loader = File(nativeLibraryDir, PROOT_LOADER)\n'
    '        if (!loader.isFile) return null\n'
    '\n'
    '        val args = mutableListOf(\n'
    '            "--root-id",\n'
    '            "--link2symlink",\n'
    '            "-r", context.linuxDir.absolutePath,\n'
    '            "-b", nativeLibraryDir.absolutePath + ":" + WorkspaceBusybox.RH_LIBS,\n'
    '            "-b", context.filesDir.absolutePath + ":" + WorkspaceManager.ROOTFS_WORKSPACE_DIR,\n'
    '        )\n'
    '        for (mount in context.bindMounts) {\n'
    '            if (mount.source.exists()) {\n'
    '                args += "-b"\n'
    '                args += mount.source.absolutePath + ":" + mount.target.trimEnd(\'/\')\n'
    '            }\n'
    '        }\n'
    '        for (path in WorkspaceManager.KERNEL_FS_MOUNTS) {\n'
    '            if (File(path).exists()) {\n'
    '                args += "-b"\n'
    '                args += path\n'
    '            }\n'
    '        }\n'
    '        args += "-w"\n'
    '        args += WorkspaceManager.ROOTFS_WORKSPACE_DIR\n'
    '        // 交互 shell: 农场里的 busybox。basename 不是已知 applet 时 busybox 拿 argv[1]\n'
    '        // 当 applet 名, 所以 "sh" 必须单独一个 argv。-i 保证没有 tty 判定时也是交互态。\n'
    '        args += WorkspaceBusybox.EXEC_PATH\n'
    '        args += "sh"\n'
    '        args += "-i"\n'
    '\n'
    '        // env 直接替换宿主环境(LocalPtyTransport 走 execve), 与 prootProcess 的取值保持一致\n'
    '        val env = mutableListOf(\n'
    '            "PATH=" + GUEST_PATH,\n'
    '            "HOME=/root",\n'
    '            "TERM=xterm-256color",\n'
    '            "LANG=C.UTF-8",\n'
    '            "LC_ALL=C.UTF-8",\n'
    '            "LD_LIBRARY_PATH=" + nativeLibraryDir.absolutePath,\n'
    '            "PROOT_TMP_DIR=" + context.tempDir.absolutePath,\n'
    '            "PROOT_LOADER=" + loader.absolutePath,\n'
    '            "PROOT_NO_SECCOMP=1",\n'
    '        )\n'
    '\n'
    '        return WorkspaceTerminalLaunch(\n'
    '            executable = proot.absolutePath,\n'
    '            cwd = context.filesDir.absolutePath,\n'
    '            args = args,\n'
    '            env = env,\n'
    '        )\n'
    '    }\n'
    '\n'
    '    /** 返回 null 表示可执行；否则是直接展示给用户/模型的错误文案 */\n'
    '    private fun preflight(context: WorkspaceShellContext): String? {'
)

MANAGER_ANCHOR = '    fun cleanupAllTempDirs() {'
MANAGER_NEW = (
    '    /**\n'
    '     * rhLocalTerminal358: 交互式终端的启动参数; shellRunner 不支持时返回 null。\n'
    '     * 与 [executeCommand] 共用同一个 shellRunner, 因此兼容模式/rootfs 判定天然一致。\n'
    '     */\n'
    '    fun terminalLaunch(root: String, shellCompatibilityMode: Boolean = false): WorkspaceTerminalLaunch? =\n'
    '        shellRunner.terminalLaunch(\n'
    '            WorkspaceTerminalContext(\n'
    '                filesDir = filesDir(root),\n'
    '                linuxDir = linuxDir(root),\n'
    '                tempDir = tempDir(root),\n'
    '                bindMounts = bindMounts,\n'
    '                shellCompatibilityMode = shellCompatibilityMode,\n'
    '            )\n'
    '        )\n'
    '\n'
    '    fun cleanupAllTempDirs() {'
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


def braces(text):
    stripped = strip_literals(text)
    diff = stripped.count("{") - stripped.count("}")
    parens = stripped.count("(") - stripped.count(")")
    return diff, parens


def patch_file(path, anchor, replacement, checks, label):
    if not os.path.isfile(path):
        log("missing-file:" + label)
        return ["missing-file:" + label]
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    if MARK in text:
        log("already:" + label)
        return []
    count = text.count(anchor)
    if count != 1:
        log("anchor-count:" + label + ":" + str(count))
        return ["anchor:" + label + ":" + str(count)]
    before = braces(text)
    updated = text.replace(anchor, replacement)
    after = braces(updated)
    log("braces:" + label + ":" + str(before[0]) + "/" + str(before[1]) + " -> " +
        str(after[0]) + "/" + str(after[1]))
    if before != after:
        return ["braces:" + label + ":" + str(before) + "->" + str(after)]
    for needle in checks:
        if needle not in updated:
            return ["check:" + label + ":" + needle]
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(updated)
    log("wrote:" + label + ":" + str(len(updated)))
    return []


def main():
    failures = []

    failures += patch_file(
        RUNNER, RUNNER_ANCHOR, RUNNER_NEW,
        [
            "fun terminalLaunch(context: WorkspaceTerminalContext): WorkspaceTerminalLaunch? = null",
            "data class WorkspaceTerminalContext(",
            "data class WorkspaceTerminalLaunch(",
        ],
        "runner",
    )
    failures += patch_file(
        PROOT, PROOT_ANCHOR, PROOT_NEW,
        [
            "override fun terminalLaunch(context: WorkspaceTerminalContext): WorkspaceTerminalLaunch?",
            'args += "sh"',
            "PROOT_NO_SECCOMP=1",
        ],
        "proot",
    )
    failures += patch_file(
        MANAGER, MANAGER_ANCHOR, MANAGER_NEW,
        [
            "fun terminalLaunch(root: String, shellCompatibilityMode: Boolean = false)",
            "WorkspaceTerminalContext(",
        ],
        "manager",
    )

    # 交叉检查：Manager 用到的两个数据类必须已经存在（防止只落地一半）
    try:
        with open(RUNNER, "r", encoding="utf-8") as handle:
            runner_text = handle.read()
        with open(MANAGER, "r", encoding="utf-8") as handle:
            manager_text = handle.read()
        if "terminalLaunch(root: String" in manager_text and "data class WorkspaceTerminalContext(" not in runner_text:
            failures.append("cross:manager-without-context")
        if "override fun terminalLaunch" in open(PROOT, "r", encoding="utf-8").read():
            if "fun terminalLaunch(context: WorkspaceTerminalContext)" not in runner_text:
                failures.append("cross:override-without-interface")
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

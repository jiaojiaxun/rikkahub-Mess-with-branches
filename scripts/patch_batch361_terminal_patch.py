#!/usr/bin/env python3
# rhLocalTerminal361: 终端首次打开时刷新 rootfs 运行期配置 + 清理 358 留下的重复 KDoc
#
# 两件事：
#   1) ProotShellRunner.terminalLaunch 里补 patcher.patch(linuxDir)。
#      execute 路径在启动 proot 前会 patch（写 resolv.conf / hosts 等），terminalLaunch 之前漏了
#      —— 新装 rootfs 直接开终端时，apk/wget 会解析不到域名，直到 AI 跑过一条 shell 命令才自愈。
#      用 runCatching 包住：patch 失败不该挡住终端启动（preflight 已经保证 rootfs 可用）。
#   2) 358 的插入锚点选在 `private fun preflight(...)` 这一行，导致 preflight 原来的 KDoc 变成了
#      terminalLaunch 前方的孤立注释（现在连着两个 KDoc）。本批删掉那份重复的。
#
# 幂等：以内容特征判断（是否已含 runCatching { patcher.patch / 是否还有连续两个 KDoc）。

import os
import sys

MARK = "rhLocalTerminal361"
REPO = os.getcwd()
PROOT = os.path.join(REPO, "workspace", "src", "main", "java", "me", "rerere", "workspace", "ProotShellRunner.kt")
DIAG = os.path.join(REPO, "ci_diag_batch361_terminal_patch.txt")

DUP_KDOC = (
    '    /** 返回 null 表示可执行；否则是直接展示给用户/模型的错误文案 */\n'
    '    /**\n'
    '     * rhLocalTerminal358: 交互式终端。'
)
FIXED_KDOC = (
    '    /**\n'
    '     * rhLocalTerminal358: 交互式终端。'
)

PATCH_OLD = (
    '        if (!loader.isFile) return null\n'
    '\n'
    '        val args = mutableListOf(\n'
)
PATCH_NEW = (
    '        if (!loader.isFile) return null\n'
    '\n'
    '        // ' + MARK + ': 与 execute 路径保持一致, 首次打开终端也刷新 hosts/resolv 等\n'
    '        // 运行期配置; patch 失败不影响启动(rootfs 可用性已由上面的检查保证)。\n'
    '        runCatching { patcher.patch(context.linuxDir) }\n'
    '\n'
    '        val args = mutableListOf(\n'
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

    if not os.path.isfile(PROOT):
        log("missing-file:proot")
        with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("missing-file:proot\nRESULT:FAIL\n")
        sys.exit(1)

    with open(PROOT, "r", encoding="utf-8") as handle:
        text = handle.read()

    before = counts(text)

    # 1) 重复 KDoc
    if text.count(DUP_KDOC) == 1:
        text = text.replace(DUP_KDOC, FIXED_KDOC)
        log("wrote:dedupe-kdoc")
    elif text.count(FIXED_KDOC) == 1:
        log("already:dedupe-kdoc")
    else:
        log("anchor-kdoc:" + str(text.count(DUP_KDOC)))
        failures.append("anchor-kdoc")

    # 2) patcher.patch
    if MARK in text:
        log("already:patch")
    else:
        hits = text.count(PATCH_OLD)
        log("anchor-patch:" + str(hits))
        if hits == 1:
            text = text.replace(PATCH_OLD, PATCH_NEW)
            log("wrote:patch")
        else:
            failures.append("anchor-patch:" + str(hits))

    after = counts(text)
    log("braces:" + str(before) + "->" + str(after))
    if before != after:
        failures.append("braces")

    with open(PROOT, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    log("file-size:" + str(len(text)))

    # 复核（以磁盘为准）
    with open(PROOT, "r", encoding="utf-8") as handle:
        final = handle.read()
    checks = [
        ("kdoc-deduped", final.count("返回 null 表示可执行；否则是直接展示给用户/模型的错误文案") == 1),
        ("patch-added", "runCatching { patcher.patch(context.linuxDir) }" in final),
        ("launch-present", "override fun terminalLaunch(context: WorkspaceTerminalContext)" in final),
        ("preflight-kept", "private fun preflight(context: WorkspaceShellContext): String?" in final),
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

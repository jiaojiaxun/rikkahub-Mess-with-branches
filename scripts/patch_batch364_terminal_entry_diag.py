#!/usr/bin/env python3
# rhLocalTerminal364 (v2): 只读诊断 —— 终端入口门控 + ChatService 的 workspaceCwd 传参
#
# 两件事一起查，省一次构建：
#
# A) 终端入口真实门控（P2）
#    359 的扫描给出 detail 页 supportsTerminal()=1 / isSsh()=2 / WorkspaceTerminal=1，
#    但「三者都在同一文件」不等于「本地工作区能进终端」——若入口写成
#    `if (workspace.isSsh() && workspace.supportsTerminal())` 或外层再套 isSsh，本地照样进不去。
#    362/363 已删掉终端页自己的 SSH 硬判断，所以入口这层必须确认。
#
# B) ChatService 的会话工作目录（P3，长期挂着的核实项）
#    要确认 conversation.workspaceCwd 有没有真的传给 workspace 工具工厂，
#    还是 AI 的 shell 永远落在工作区默认目录。163KB 的文件不适合整读，用只读扫描定位。
#
# 本批不改任何代码，只把命中行连同前后各 4 行（带行号）写进
#   ci_diag_batch364_terminal_entry.txt
# 判定标准：
#   · supportsTerminal() 在 if 条件里且同一 if 无 isSsh ⇒ 本地可达
#   · 同一 if 里同时有 isSsh ⇒ 本地不可达，需要再补一批
#   · ChatService 里 workspaceCwd 只出现在字段定义/透传、而 createWorkspaceTools 调用点没用到
#     ⇒ 说明没接上，AI 的 shell 默认落在工作区根目录
#
# 只读脚本永不 exit(1)，不会影响构建链。

import os

REPO = os.getcwd()
APP = os.path.join(REPO, "app", "src", "main", "java", "me", "rerere", "rikkahub")
TARGETS = [
    ("detail", os.path.join(APP, "ui", "pages", "extensions", "workspace", "WorkspaceDetailPage.kt"),
     ["supportsTerminal", "isSsh()", "WorkspaceTerminal"], 12),
    ("list", os.path.join(APP, "ui", "pages", "extensions", "workspace", "WorkspacePage.kt"),
     ["supportsTerminal", "isSsh()", "WorkspaceTerminal"], 8),
    ("route", os.path.join(APP, "RouteActivity.kt"),
     ["WorkspaceTerminal"], 6),
    ("chatservice", os.path.join(APP, "service", "ChatService.kt"),
     ["workspaceCwd", "createWorkspaceTools", "workspaceTools"], 8),
]
DIAG = os.path.join(REPO, "ci_diag_batch364_terminal_entry.txt")
CONTEXT = 4

OUT = []


def log(line):
    OUT.append(line)
    print(line)


def scan(label, path, needles, max_blocks):
    if not os.path.isfile(path):
        log("S" + label + " MISSING")
        return
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        lines = handle.read().split("\n")
    log("S" + label + " lines=" + str(len(lines)))
    hits = []
    for index, line in enumerate(lines):
        if any(needle in line for needle in needles):
            hits.append(index)
    log("S" + label + " hits=" + str(len(hits)))
    emitted = 0
    for index in hits:
        if emitted >= max_blocks:
            log("S" + label + " truncated after " + str(max_blocks) + " blocks")
            break
        start = max(0, index - CONTEXT)
        end = min(len(lines) - 1, index + CONTEXT)
        log("-- " + label + " @line" + str(index + 1))
        for cursor in range(start, end + 1):
            marker = ">>" if cursor == index else "  "
            log(marker + str(cursor + 1) + ": " + lines[cursor])
        emitted += 1


def main():
    for label, path, needles, max_blocks in TARGETS:
        scan(label, path, needles, max_blocks)
    log("RESULT:OK")
    with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()

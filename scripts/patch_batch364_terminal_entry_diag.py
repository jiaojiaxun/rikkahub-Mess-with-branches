#!/usr/bin/env python3
# rhLocalTerminal364: 只读诊断 —— 详情页/列表页/路由里终端入口的真实门控
#
# 为什么需要它：359 的只读扫描给出 detail 页 supportsTerminal()=1 / isSsh()=2 / WorkspaceTerminal=1，
# 但「三者在同一处」不等于「本地工作区能进终端」——如果入口被写成
# `if (workspace.isSsh() && workspace.supportsTerminal())` 或外层再套一个 isSsh 判断，
# 本地的能力位照样进不去。362/363 又会把 Page 里的 SSH 硬判断删掉，
# 所以必须确认入口这一层到底怎么写的。
#
# 本批**不改任何代码**，只把命中行的上下文（前后各 4 行、带行号）写进诊断文件：
#   ci_diag_batch364_terminal_entry.txt
# 判定标准（人工看 diag）：
#   · supportsTerminal() 出现在 if 条件里，且同一 if 里没有 isSsh ⇒ 本地可达
#   · 同一 if 里同时有 isSsh ⇒ 本地不可达，需要再补一批
#
# 只读脚本永远 exit(0)：warn-only 之前也不该拦住构建链。

import os

REPO = os.getcwd()
APP = os.path.join(REPO, "app", "src", "main", "java", "me", "rerere", "rikkahub")
TARGETS = [
    ("detail", os.path.join(APP, "ui", "pages", "extensions", "workspace", "WorkspaceDetailPage.kt")),
    ("list", os.path.join(APP, "ui", "pages", "extensions", "workspace", "WorkspacePage.kt")),
    ("route", os.path.join(APP, "RouteActivity.kt")),
]
NEEDLES = ["supportsTerminal", "isSsh()", "WorkspaceTerminal"]
DIAG = os.path.join(REPO, "ci_diag_batch364_terminal_entry.txt")

MAX_BLOCKS = 12
CONTEXT = 4

OUT = []


def log(line):
    OUT.append(line)
    print(line)


def scan(label, path):
    if not os.path.isfile(path):
        log("§" + label + " MISSING")
        return
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        lines = handle.read().split("\n")
    log("§" + label + " lines=" + str(len(lines)))
    hits = []
    for index, line in enumerate(lines):
        if any(needle in line for needle in NEEDLES):
            hits.append(index)
    log("§" + label + " hits=" + str(len(hits)))
    emitted = 0
    for index in hits:
        if emitted >= MAX_BLOCKS:
            log("§" + label + " truncated after " + str(MAX_BLOCKS) + " blocks")
            break
        start = max(0, index - CONTEXT)
        end = min(len(lines) - 1, index + CONTEXT)
        log("-- " + label + " @" + str(index + 1))
        for cursor in range(start, end + 1):
            marker = ">>" if cursor == index else "  "
            log(marker + str(cursor + 1) + ": " + lines[cursor])
        emitted += 1


def main():
    for label, path in TARGETS:
        scan(label, path)
    log("RESULT:OK")
    with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()

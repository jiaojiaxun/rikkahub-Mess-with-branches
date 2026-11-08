#!/usr/bin/env python3
# rhDiFix367: 路由参数被写死 —— WorkspaceFileEditor 的 area 丢失
#
# 排查「还有没有同类问题」时，在 RouteActivity 的 entry 区发现：
#
#   entry<Screen.WorkspaceFileEditor> { key ->
#       WorkspaceFileEditorPage(
#           id = key.id,
#           area = WorkspaceStorageArea.FILES,   // ← 写死，key.area 完全没用
#           path = key.path,
#       )
#   }
#
# 而 Screen 定义带 area：`data class WorkspaceFileEditor(val id: String, val area: String, val path: String)`，
# Page 签名是 `WorkspaceFileEditorPage(id: String, area: WorkspaceStorageArea, path: String)`。
# 也就是：从 LINUX 区打开文件时，导航参数里的 "LINUX" 被丢掉，页面一律按 FILES 区解析路径
# —— 读不到文件（或读到文件区同名文件）。这和「参数加了没用」是同一族问题。
#
# 修法（安全、行为向后兼容）：
#   area = runCatching { WorkspaceStorageArea.valueOf(key.area) }
#       .getOrDefault(WorkspaceStorageArea.FILES)
#   · 调用方传 "FILES" → 与今天完全一致
#   · 调用方传 "LINUX" → 修好
#   · 传了别的脏值 → 回退 FILES，不会抛异常
#
# 另附只读 dump：把 `Screen.WorkspaceFileEditor(` 的所有调用点（前后 3 行）写进诊断，
# 用于人工确认调用方实参到底传的什么。

import os
import re
import sys

MARK = "rhDiFix367"
REPO = os.getcwd()
ROUTE = os.path.join(REPO, "app", "src", "main", "java", "me", "rerere", "rikkahub", "RouteActivity.kt")
APP = os.path.join(REPO, "app", "src", "main", "java")
DIAG = os.path.join(REPO, "ci_diag_batch367_file_editor_area.txt")

OLD = (
    '                            entry<Screen.WorkspaceFileEditor> { key ->\n'
    '                                WorkspaceFileEditorPage(\n'
    '                                    id = key.id,\n'
    '                                    area = WorkspaceStorageArea.FILES,\n'
    '                                    path = key.path,\n'
    '                                )\n'
    '                            }\n'
)
NEW = (
    '                            entry<Screen.WorkspaceFileEditor> { key ->\n'
    '                                WorkspaceFileEditorPage(\n'
    '                                    id = key.id,\n'
    '                                    // ' + MARK + ': 用导航参数里的 area, 不要写死。\n'
    '                                    // 脏值回退 FILES, 与旧行为一致, 不会抛异常。\n'
    '                                    area = runCatching { WorkspaceStorageArea.valueOf(key.area) }\n'
    '                                        .getOrDefault(WorkspaceStorageArea.FILES),\n'
    '                                    path = key.path,\n'
    '                                )\n'
    '                            }\n'
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


def walk_kotlin(root):
    for folder, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith(".kt"):
                yield os.path.join(folder, name)


def main():
    failures = []

    if not os.path.isfile(ROUTE):
        log("missing-file:route")
        with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("missing-file:route\nRESULT:FAIL\n")
        sys.exit(1)

    with open(ROUTE, "r", encoding="utf-8") as handle:
        text = handle.read()
    before = counts(text)

    if MARK in text:
        log("already:fix")
    else:
        hits = text.count(OLD)
        log("anchor:" + str(hits))
        if hits != 1:
            failures.append("anchor:" + str(hits))
        else:
            text = text.replace(OLD, NEW)
            log("wrote:fix")

    after = counts(text)
    log("braces:" + str(before) + "->" + str(after))
    if before != after:
        failures.append("braces")

    with open(ROUTE, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    log("file-size:" + str(len(text)))

    # 复核
    with open(ROUTE, "r", encoding="utf-8") as handle:
        final = handle.read()
    checks = [
        ("uses-key-area", "WorkspaceStorageArea.valueOf(key.area)" in final),
        ("no-hardcoded-area-line", "area = WorkspaceStorageArea.FILES,\n" not in final),
        ("fallback-present", "getOrDefault(WorkspaceStorageArea.FILES)" in final),
        ("entry-kept", "entry<Screen.WorkspaceFileEditor> { key ->" in final),
    ]
    for name, ok in checks:
        log("check:" + name + ":" + ("ok" if ok else "FAIL"))
        if not ok:
            failures.append("check:" + name)

    # 只读 dump：所有导航到该 Screen 的调用点
    needle = "Screen.WorkspaceFileEditor("
    dumped = 0
    for path in walk_kotlin(APP):
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.read().split("\n")
        for index, line in enumerate(lines):
            if needle not in line:
                continue
            if "entry<Screen.WorkspaceFileEditor>" in line:
                continue
            if dumped >= 10:
                break
            dumped += 1
            log("-- call " + os.path.relpath(path, REPO) + " @line" + str(index + 1))
            for cursor in range(max(0, index - 3), min(len(lines), index + 4)):
                marker = ">>" if cursor == index else "  "
                log(marker + str(cursor + 1) + ": " + lines[cursor])
    log("call-sites:" + str(dumped))

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

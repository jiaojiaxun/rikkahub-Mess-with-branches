#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhPhone348e -- 修挡路的全局编译错误：WorkspaceFileEditorPage 缺两个 import。

348d 的编译错误（check-run 128618085584）：
    Unresolved reference 'stringResource'
    Unresolved reference 'R'
    Location: ui/pages/extensions/workspace/WorkspaceFileEditorPage.kt line 85

line 85 是：
    fileName + " (" + stringResource(R.string.workspace_file_read_only) + ")"
但该文件的 import 区里（实读 snapshot 0-4200 字节）既没有
    androidx.compose.ui.res.stringResource
也没有
    me.rerere.rikkahub.R

这不是手机操控的文件，是工作区文件编辑器（可能是并行会话刚移植的版本）。
但全局编译红会挡住所有批次，所以必须补。

本批只加两行 import，幂等：已存在就跳过。
"""
import os
import sys

MARK = "rhPhone348e"
DIAG = "ci_diag_batch348e_ws_import.txt"
ROOT = os.path.abspath(os.getcwd())
REL = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceFileEditorPage.kt"
rows = []


def note(msg):
    line = "[batch348e] " + str(msg)
    print(line)
    rows.append(line)


def flush():
    try:
        with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
    except Exception:
        pass


def main():
    path = os.path.join(ROOT, REL)
    if not os.path.exists(path):
        note("MISSING " + REL)
        return
    with open(path, encoding="utf-8") as f:
        text = f.read()

    need_sr = "import androidx.compose.ui.res.stringResource"
    need_r = "import me.rerere.rikkahub.R"

    added = 0
    if need_sr not in text:
        anchor = "import androidx.compose.ui.unit.sp"
        if text.count(anchor) != 1:
            note("stringResource anchor count=" + str(text.count(anchor)))
        else:
            text = text.replace(anchor, anchor + "\n" + need_sr + " // " + MARK, 1)
            added += 1

    if need_r not in text:
        anchor2 = "import me.rerere.rikkahub.data.repository.WorkspaceRepository"
        if text.count(anchor2) != 1:
            note("R anchor count=" + str(text.count(anchor2)))
        else:
            text = text.replace(anchor2, need_r + " // " + MARK + "\n" + anchor2, 1)
            added += 1

    if need_sr not in text or need_r not in text:
        note("one import still missing")
        return
    if added == 0:
        note("both imports already present")
        return

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    note("added " + str(added) + " import(s)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        note("EXCEPTION " + type(exc).__name__ + " " + str(exc)[:240])
    flush()
    print("::error::batch348e END lines=" + str(len(rows)))
    sys.exit(0)
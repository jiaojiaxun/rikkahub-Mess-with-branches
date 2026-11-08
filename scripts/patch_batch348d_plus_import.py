#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhPhone348d -- 补 SettingPhoneControlPage 缺的 PaddingValues.plus import。

348c 的编译错误（check-run 128613652486）：
    Unresolved reference 'plus' for operator '+' on receiver of type 'PaddingValues'.
    Location: ui/pages/setting/SettingPhoneControlPage.kt line 102

line 102 是 `contentPadding = innerPadding + PaddingValues(8.dp)`。
RikkaHub 的 PaddingValues 相加走 `me.rerere.rikkahub.utils.plus` 扩展，
SettingPage 里 import 了，新页面漏了。

本批只加一行 import，不改任何逻辑。
"""
import os
import sys

MARK = "rhPhone348d"
DIAG = "ci_diag_batch348d_import.txt"
ROOT = os.path.abspath(os.getcwd())
REL = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPhoneControlPage.kt"
rows = []


def note(msg):
    line = "[batch348d] " + str(msg)
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
    if "import me.rerere.rikkahub.utils.plus" in text:
        note("import already present")
        return
    anchor = "import me.rerere.rikkahub.ui.theme.CustomColors"
    if text.count(anchor) != 1:
        note("anchor count=" + str(text.count(anchor)))
        return
    text = text.replace(
        anchor,
        anchor + "\nimport me.rerere.rikkahub.utils.plus // " + MARK,
        1,
    )
    if "import me.rerere.rikkahub.utils.plus" not in text:
        note("insert lost")
        return
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    note("added import me.rerere.rikkahub.utils.plus")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        note("EXCEPTION " + type(exc).__name__ + " " + str(exc)[:240])
    flush()
    print("::error::batch348d END lines=" + str(len(rows)))
    sys.exit(0)
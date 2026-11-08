#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhPhone348c -- 补 348b 漏掉的 Screen 类型定义。

348b 的实测（snapshot ci_diag_batch348b_phone_page.txt）：
    wrote SettingPhoneControlPage.kt
    Screen.SettingToolApprovals definition not found   ← 只差这一处
    entryProvider: SettingPhoneControl registered
    SettingPage: long block -> one entry row

后果：entryProvider 引用了 Screen.SettingPhoneControl，但 sealed interface 里
没有这个类型 → 编译 Unresolved reference。

根因：我已知道 Screen 定义在 RouteActivity 文件末尾（不是开头），且
SettingToolApprovals 的实际声明可能是 data object 也可能是 data class，
348b 硬编码了 `data class` 所以没命中。

本批改用「行内含 SettingToolApprovals + : Screen」的宽松定位，
插入 `data object SettingPhoneControl : Screen`（entry 不取 key，object 即可）。
"""
import os
import sys

MARK = "rhPhone348c"
DIAG = "ci_diag_batch348c_screen.txt"
ROOT = os.path.abspath(os.getcwd())
REL = "app/src/main/java/me/rerere/rikkahub/RouteActivity.kt"
rows = []


def note(msg):
    line = "[batch348c] " + str(msg)
    print(line)
    rows.append(line)


def flush():
    try:
        with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
    except Exception:
        pass


def parens(t):
    return (t.count("(") - t.count(")"), t.count("{") - t.count("}"), t.count("[") - t.count("]"))


def main():
    path = os.path.join(ROOT, REL)
    if not os.path.exists(path):
        note("MISSING " + REL)
        return
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if "data object SettingPhoneControl : Screen" in text or "data class SettingPhoneControl" in text:
        note("already defined")
        return

    lines = text.split("\n")
    idx = -1
    for i, line in enumerate(lines):
        if "SettingToolApprovals" in line and ": Screen" in line:
            idx = i
            break
    if idx < 0:
        note("SettingToolApprovals declaration not found")
        return

    before = parens(text)
    indent = lines[idx][:len(lines[idx]) - len(lines[idx].lstrip())]
    lines[idx + 1:idx + 1] = [
        "",
        indent + "@Serializable",
        indent + "data object SettingPhoneControl : Screen // " + MARK,
    ]
    out = "\n".join(lines)
    after = parens(out)
    if after != before:
        note("balance " + str(before) + " -> " + str(after))
        return
    if "data object SettingPhoneControl : Screen" not in out:
        note("insert lost")
        return
    if "entry<Screen.SettingPhoneControl>" not in out:
        note("WARN entry not present, will still compile-fail")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    note("inserted data object SettingPhoneControl after line " + str(idx + 1))
    note("parens before=" + str(before) + " after=" + str(after))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        note("EXCEPTION " + type(exc).__name__ + " " + str(exc)[:240])
    flush()
    print("::error::batch348c END lines=" + str(len(rows)))
    sys.exit(0)
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhScan339 -- 全仓扫描 token 显示点，不再靠猜。

338 的实证（snapshot ci_diag_batch338_token_unit.txt）：
    wrote TokenUnitStore.kt
    patched RikkaHubApp.kt (init)
    patched SettingPreferencesUIPage.kt (state + item)
    FAIL FilesPicker token line not found
    FAIL provider page preset line not found
    patched ChatPage.kt (untitled title)
    steps ok=4/6

说明 fork 的 FilesPicker / SettingProviderDetailPage 里根本没有上游那两行
（fork 基线 2.4.14，上游片段来自 2.5.x）。继续按上游文本猜锚点只会再挂一次。

本批不改任何源码，只做一件事：扫描 app/src/main/java 下所有 .kt，
把含 formatNumber( / formatTokens( / contextTokens / TokenUsage 的行
（文件:行号: 内容）写进 ci_diag_batch339_token_scan.txt，供下一批精确落点。

扫描本身是只读的，不会影响 580 的产物。
"""
import os
import sys

MARK = "rhScan339"
DIAG = "ci_diag_batch339_token_scan.txt"
ROOT = os.path.abspath(os.getcwd())
BASE = os.path.join(ROOT, "app/src/main/java")
KEYS = ("formatNumber(", "formatTokens(", "contextTokens", "TokenUsage", "tokenUsage")

rows = []


def note(msg):
    rows.append(str(msg)[:400])


def main():
    if not os.path.isdir(BASE):
        note("MISSING " + BASE)
        return
    files = 0
    for dirpath, _dirs, names in os.walk(BASE):
        for name in names:
            if not name.endswith(".kt"):
                continue
            files += 1
            path = os.path.join(dirpath, name)
            rel = path.replace(ROOT + os.sep, "").replace(os.sep, "/")
            try:
                with open(path, encoding="utf-8") as f:
                    lines = f.read().split("\n")
            except Exception as exc:  # noqa: BLE001
                note("READ FAIL " + rel + " " + str(exc)[:120])
                continue
            for index, line in enumerate(lines, 1):
                if any(key in line for key in KEYS):
                    rows.append(rel + ":" + str(index) + ": " + line.strip()[:200])
    note("scan done files=" + str(files) + " hits=" + str(len(rows)))
    try:
        with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
    except Exception as exc:  # noqa: BLE001
        print("::error title=scan339::diag write failed " + str(exc)[:200])
    print("::error::batch339 scan hits=" + str(len(rows)))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        note("EXCEPTION " + type(exc).__name__ + " " + str(exc)[:200])
        try:
            with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
                f.write("\n".join(rows) + "\n")
        except Exception:
            pass
        sys.exit(0)
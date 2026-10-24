#!/usr/bin/env python3
# batch281: 修复 batch280 写入的两处错误字符串。
#
# batch280 的 STORE_CODE 里两处 toast 文案误写成 "已删除备份包：「 + nameStr （多了一个「），
# 会让 Kotlin 字符串字面量提前闭合 → 编译失败。本批把该文件中所有 ：「 换成 ："。
# 如果 batch280 已经写对（无 ：「）则本批为空操作。
# MARK=rhBackupDel281
import sys
from pathlib import Path

MARK = "rhBackupDel281"
NL = chr(10)
Q = chr(34)
DIAG = "ci_diag_batch281.txt"
STORE = "app/src/main/java/me/rerere/rikkahub/data/sync/PendingBackupDeleteStore.kt"
applied = []
failed = []


def diag(msg):
    try:
        with open(DIAG, "a", encoding="utf-8") as f:
            f.write(msg + NL)
    except Exception:
        pass


def fail(msg):
    diag("FAIL " + msg)
    print("::error title=batch281::" + msg)
    raise SystemExit(0)


def main():
    p = Path(STORE)
    if not p.exists():
        fail("missing file: " + STORE)
    content = p.read_text(encoding="utf-8")
    if "rhBackupDel280" not in content:
        diag("batch280 not applied, nothing to repair")
        print("::notice title=batch281-skip::batch280 not applied")
        return
    broken = "：" + "「"
    if broken not in content:
        diag("no stray quote, nothing to repair")
        print("::notice title=batch281-ok::nothing to repair")
        return
    n = content.count(broken)
    content = content.replace(broken, "：" + Q)
    p.write_text(content, encoding="utf-8")
    check = p.read_text(encoding="utf-8")
    if broken in check:
        fail("repair incomplete, still " + str(check.count(broken)))
    applied.append("store-stray-quote=" + str(n))
    diag("applied=" + ",".join(applied))
    print("::notice title=batch281-ok::" + ",".join(applied))


main()

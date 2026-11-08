#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhPhone348a -- 补 347 漏改的 needsApproval。

347 的实测（snapshot ci_diag_batch347_phone_policies.txt）：
    FAIL PhoneTools needsApproval count=5 (expected 6)
    steps ok=5/6

我数错了：写工具只有 5 个（tap / type / tap_xy / open / intent），
handoff 是读类、needsApproval=false，不算在内。

本批不再硬编码数量：取实际出现次数（必须 ≥1），全部替换，
替换后断言旧串为 0。这样以后加减工具都不会再因为计数错而整批失败。
"""
import os
import sys

MARK = "rhPhone348a"
DIAG = "ci_diag_batch348a_approval.txt"
ROOT = os.path.abspath(os.getcwd())
REL = "app/src/main/java/me/rerere/rikkahub/phone/PhoneTools.kt"
rows = []


def note(msg):
    line = "[batch348a] " + str(msg)
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
    if MARK in text:
        note("already applied")
        return
    needle = "    needsApproval = { true },"
    count = text.count(needle)
    if count < 1:
        note("no needsApproval = { true } left (already converted?)")
        return
    repl = (
        "    needsApproval = { me.rerere.rikkahub.phone.PhonePoliciesStore.current.confirmMode != "
        "me.rerere.rikkahub.phone.ConfirmMode.ALWAYS }, // " + MARK
    )
    text = text.replace(needle, repl)
    if needle in text:
        note("still has old line after replace")
        return
    if "PhonePoliciesStore.current.confirmMode" not in text:
        note("replacement missing")
        return
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    note("converted " + str(count) + " needsApproval sites to mode != ALWAYS")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        note("EXCEPTION " + type(exc).__name__ + " " + str(exc)[:240])
    flush()
    print("::error::batch348a END lines=" + str(len(rows)))
    sys.exit(0)
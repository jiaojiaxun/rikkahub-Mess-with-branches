#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhPhone332 -- 自查修补：PhoneCapture 用了不存在的 API。

逐行核对 AccessibilityNodeInfo 的可用方法时发现：
  node.roleDescription  -> 不存在（Android 没有 getRoleDescription）
  真实可用的角色信息在 getExtras()（Compose / Chromium 会放
  "AccessibilityNodeInfo.role" / "role"）与 getClassName()。

改成从 extras 读，读不到就 null；外层 runCatching 保证任何厂商实现
抛异常都不影响读屏。这是自查第二处编译级真问题。
"""
import os
import sys

MARK = "rhPhone332"
DIAG_NAME = "ci_diag_batch332_phone_role.txt"
DIAG = []


def log(msg):
    line = "[batch332] " + str(msg)
    print(line)
    DIAG.append(line)


def fail(msg):
    line = "FAIL " + str(msg)
    print("::error title=phone332::" + line)
    DIAG.append(line)
    write_diag()
    sys.exit(1)


def write_diag():
    try:
        with open(DIAG_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(DIAG) + "\n")
    except Exception as exc:  # noqa: BLE001
        print("::warning title=phone332::diag write failed: " + str(exc))


def repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    guess = os.path.abspath(os.path.join(here, ".."))
    if os.path.isdir(os.path.join(guess, "app")):
        return guess
    return os.getcwd()


ROOT = repo_root()
CAPTURE = "app/src/main/java/me/rerere/rikkahub/phone/PhoneCapture.kt"


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def write_text(rel, content):
    with open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


OLD = '''            roleHint = runCatching { node.roleDescription?.toString()?.lowercase() }.getOrNull(),'''

NEW = '''            // 没有 getRoleDescription()：Compose / Chromium 把角色放在 extras 里，读不到就 null。
            roleHint = runCatching {
                val extras = node.extras
                val role = extras?.getCharSequence("AccessibilityNodeInfo.role")
                    ?: extras?.getCharSequence("role")
                role?.toString()?.lowercase()
            }.getOrNull(),'''


def main():
    log("root=" + ROOT)
    text = read(CAPTURE)
    if MARK in text:
        log("skip PhoneCapture.kt (already applied)")
        write_diag()
        return
    count = text.count(OLD)
    if count != 1:
        fail("roleDescription anchor count=" + str(count))
    text = text.replace(OLD, NEW, 1)
    write_text(CAPTURE, text)
    back = read(CAPTURE)
    if "roleDescription" in back:
        fail("PhoneCapture still references roleDescription")
    if "AccessibilityNodeInfo.role" not in back:
        fail("PhoneCapture write-back lost extras role read")
    for op, cl in [("{", "}"), ("(", ")")]:
        if back.count(op) != back.count(cl):
            fail("PhoneCapture unbalanced " + op + cl + ": " + str(back.count(op)) + "/" + str(back.count(cl)))
    log("patched PhoneCapture.kt (extras role)")
    write_diag()


if __name__ == "__main__":
    main()
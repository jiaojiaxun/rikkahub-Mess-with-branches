#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhPhone333 -- run#574 编译错误的真因修复：class 与 object 同名重名。

CI 注解（check-run 124783989379）原文：
  PhoneCapture.kt:16:7  Redeclaration:
  PhoneCapture.kt:47:8  Redeclaration:
  PhoneCapture.kt:95:36 Unresolved reference 'MAX_WINDOWS'.
  PhoneCapture.kt:101:70 Unresolved reference 'activeRoot'.
  PhoneCapture.kt:117:28 Unresolved reference 'convert'.
  PhoneCapture.kt:160:70 Unresolved reference 'activeRoot'.
  PhoneCapture.kt:164:21 Unresolved reference 'release'.
  PhoneCapture.kt:181:9  Unresolved reference 'release'.
  PhoneCapture.kt:192:13 Unresolved reference 'release'.
  PhoneCapture.kt:195:25 Unresolved reference 'MAX_NODES'.

根因：dsh-go 原本是 `internal class Capture` + `internal object TreeCapture`（两个名字），
我在 327 里把两者都改成了 PhoneCapture，Kotlin 不允许同包同名 class 与 object。
结果 object 的所有成员（常量、convert、activeRoot、release）全部不可见。

修法（最小、可验证）：object 改名 PhoneCapturer，数据类 PhoneCapture 保持不变；
PhoneCore 里的调用点同步改名。

本批只动两个已存在文件，锚点来自 snapshot 实读。
"""
import os
import sys

MARK = "rhPhone333"
DIAG_NAME = "ci_diag_batch333_phone_redecl.txt"
DIAG = []


def log(msg):
    line = "[batch333] " + str(msg)
    print(line)
    DIAG.append(line)


def fail(msg):
    line = "FAIL " + str(msg)
    print("::error title=phone333::" + line)
    DIAG.append(line)
    write_diag()
    sys.exit(0)


def write_diag():
    try:
        with open(DIAG_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(DIAG) + "\n")
    except Exception as exc:  # noqa: BLE001
        print("::warning title=phone333::diag write failed: " + str(exc))


def repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    guess = os.path.abspath(os.path.join(here, ".."))
    if os.path.isdir(os.path.join(guess, "app")):
        return guess
    return os.getcwd()


ROOT = repo_root()
CAPTURE = "app/src/main/java/me/rerere/rikkahub/phone/PhoneCapture.kt"
CORE = "app/src/main/java/me/rerere/rikkahub/phone/PhoneCore.kt"


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def write_text(rel, content):
    with open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def replace_once(text, needle, replacement, label):
    count = text.count(needle)
    if count != 1:
        fail("anchor count=" + str(count) + " for " + label)
    return text.replace(needle, replacement, 1)


def main():
    log("root=" + ROOT)

    cap = read(CAPTURE)
    if MARK in cap:
        log("skip PhoneCapture.kt (already applied)")
    else:
        if "class PhoneCapture(" not in cap:
            fail("PhoneCapture data class missing")
        cap = replace_once(cap, "object PhoneCapture {", "object PhoneCapturer {", "object rename")
        # 数据类里的 PhoneCapture(...) 构造调用不受影响；只有 object 声明改名。
        if cap.count("object PhoneCapturer {") != 1:
            fail("PhoneCapturer object count != 1")
        if "object PhoneCapture {" in cap:
            fail("PhoneCapture object still present")
        write_text(CAPTURE, cap)
        log("renamed object PhoneCapture -> PhoneCapturer")

    core = read(CORE)
    if MARK in core:
        log("skip PhoneCore.kt (already applied)")
    else:
        core = replace_once(
            core,
            "PhoneCapture.capture(service, screen, context.packageName, 800)",
            "PhoneCapturer.capture(service, screen, context.packageName, 800)",
            "PhoneCore capture call",
        )
        if "PhoneCapture.capture(" in core:
            fail("PhoneCore still calls PhoneCapture.capture")
        write_text(CORE, core)
        log("PhoneCore call updated to PhoneCapturer")

    # 复验：两个文件各自括号平衡，且数据类仍叫 PhoneCapture。
    for rel in (CAPTURE, CORE):
        back = read(rel)
        for op, cl in [("{", "}"), ("(", ")")]:
            if back.count(op) != back.count(cl):
                fail(rel + " unbalanced " + op + cl + ": " + str(back.count(op)) + "/" + str(back.count(cl)))
    if "class PhoneCapture(" not in read(CAPTURE):
        fail("data class PhoneCapture lost")
    log("DONE")
    write_diag()


if __name__ == "__main__":
    main()
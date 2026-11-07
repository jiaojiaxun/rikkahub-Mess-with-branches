#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhPhone334 -- 自查第四处：PhoneCore.type() 的返回拼接有运算符优先级 bug。

原行（329 写入）：
    return Result(note + if (submit) "，并已提交" else "" + "\n" + next.formatted.text)

Kotlin 会把 else 分支整体当成 "" + "\n" + text，于是：
  * submit=true  → 只回"已写入，并已提交"，**新屏幕整段丢失**
  * submit=false → 正常
这不是日志措辞问题，是模型拿不到动作后的屏幕，下一步必然乱点。

修：先算 suffix，再拼。顺带把 note 里"已写入"与"并已提交"的间隔补好。
"""
import os
import sys

MARK = "rhPhone334"
DIAG_NAME = "ci_diag_batch334_phone_concat.txt"
DIAG = []


def log(msg):
    line = "[batch334] " + str(msg)
    print(line)
    DIAG.append(line)


def fail(msg):
    line = "FAIL " + str(msg)
    print("::error title=phone334::" + line)
    DIAG.append(line)
    write_diag()
    sys.exit(0)


def write_diag():
    try:
        with open(DIAG_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(DIAG) + "\n")
    except Exception as exc:  # noqa: BLE001
        print("::warning title=phone334::diag write failed: " + str(exc))


def repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    guess = os.path.abspath(os.path.join(here, ".."))
    if os.path.isdir(os.path.join(guess, "app")):
        return guess
    return os.getcwd()


ROOT = repo_root()
CORE = "app/src/main/java/me/rerere/rikkahub/phone/PhoneCore.kt"

OLD = '''        return Result(note + if (submit) "，并已提交" else "" + "\\n" + next.formatted.text)'''

NEW = '''        val suffix = if (submit) "，并已提交" else ""
        return Result(note + suffix + "\\n" + next.formatted.text)'''


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def write_text(rel, content):
    with open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def main():
    log("root=" + ROOT)
    text = read(CORE)
    if MARK in text:
        log("skip PhoneCore.kt (already applied)")
        write_diag()
        return
    count = text.count(OLD)
    if count != 1:
        fail("type concat anchor count=" + str(count))
    text = text.replace(OLD, NEW, 1)
    write_text(CORE, text)
    back = read(CORE)
    if "val suffix = if (submit)" not in back:
        fail("write-back lost suffix")
    if 'note + if (submit)' in back:
        fail("old concat still present")
    for op, cl in [("{", "}"), ("(", ")")]:
        if back.count(op) != back.count(cl):
            fail("PhoneCore unbalanced " + op + cl + ": " + str(back.count(op)) + "/" + str(back.count(cl)))
    log("patched PhoneCore.type() concat")
    write_diag()


if __name__ == "__main__":
    main()
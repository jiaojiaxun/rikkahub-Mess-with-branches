#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhPhone336 -- 修 335 的枚举锚点：TimeInfo 是三行注解，不是两行。

335 的实证（snapshot ci_diag_batch335_phone_wire.txt）：
    FAIL LocalTools enum anchor count=0
    [batch335] patched AssistantLocalToolPage.kt (+1 row, refs=2)

助手页开关行已经写进去了，但 LocalTools.kt 一步没动 —— 我把锚点记成了
    @Serializable @SerialName("time_info")
而仓库里实际是三行：
    @Serializable
    @SerialName("time_info")
    data object TimeInfo : LocalToolOption()

本批改用「按行 strip 全等」定位，不再赌注解怎么排版：
  * 找到 strip == "data object TimeInfo : LocalToolOption()" 的行，在它后面插 PhoneControl
  * 找到 strip == "if (options.contains(LocalToolOption.ImageGeneration)) {" 的行，在它前面插注册分支
  * 两步各自独立执行，互不阻断
  * 复验：枚举 1 处、注册 1 处、开关行仍为 2 处
"""
import os
import sys

MARK = "rhPhone336"
DIAG_NAME = "ci_diag_batch336_phone_enum.txt"
DIAG = []


def log(msg):
    line = "[batch336] " + str(msg)
    print(line)
    DIAG.append(line)


def fail(msg):
    line = "FAIL " + str(msg)
    print("::error title=phone336::" + line)
    DIAG.append(line)
    write_diag()
    sys.exit(0)


def write_diag():
    try:
        with open(DIAG_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(DIAG) + "\n")
    except Exception as exc:  # noqa: BLE001
        print("::warning title=phone336::diag write failed: " + str(exc))


def repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    guess = os.path.abspath(os.path.join(here, ".."))
    if os.path.isdir(os.path.join(guess, "app")):
        return guess
    return os.getcwd()


ROOT = repo_root()
LOCAL_TOOLS = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt"
TOOL_PAGE = "app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/detail/AssistantLocalToolPage.kt"

ENUM_INSERT = [
    "",
    "    /** rhPhone336: 手机操控（无障碍读屏 + 点击 / 输入 / 滑动）。 */",
    '    @Serializable @SerialName("phone_control")',
    "    data object PhoneControl : LocalToolOption()",
]

REG_INSERT = [
    "        if (options.contains(LocalToolOption.PhoneControl)) { // rhPhone336",
    "            tools.addAll(me.rerere.rikkahub.phone.buildPhoneTools(context))",
    "        }",
]


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def write_text(rel, content):
    with open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def find_line(lines, exact):
    for i, line in enumerate(lines):
        if line.strip() == exact:
            return i
    return -1


def patch_enum():
    text = read(LOCAL_TOOLS)
    if "data object PhoneControl" in text:
        log("skip LocalTools enum (already present)")
        return
    lines = text.split("\n")
    idx = find_line(lines, "data object TimeInfo : LocalToolOption()")
    if idx < 0:
        fail("TimeInfo line not found")
    lines[idx + 1:idx + 1] = ENUM_INSERT
    text = "\n".join(lines)
    write_text(LOCAL_TOOLS, text)
    back = read(LOCAL_TOOLS)
    if back.count("data object PhoneControl : LocalToolOption()") != 1:
        fail("PhoneControl enum count=" + str(back.count("data object PhoneControl")))
    log("inserted PhoneControl enum after TimeInfo (line " + str(idx + 1) + ")")


def patch_register():
    text = read(LOCAL_TOOLS)
    if "buildPhoneTools(context)" in text:
        log("skip LocalTools register (already present)")
        return
    lines = text.split("\n")
    idx = find_line(lines, "if (options.contains(LocalToolOption.ImageGeneration)) {")
    if idx < 0:
        fail("ImageGeneration register line not found")
    lines[idx:idx] = REG_INSERT
    text = "\n".join(lines)
    write_text(LOCAL_TOOLS, text)
    back = read(LOCAL_TOOLS)
    if back.count("buildPhoneTools(context)") != 1:
        fail("buildPhoneTools count=" + str(back.count("buildPhoneTools(context)")))
    log("inserted register branch before ImageGeneration (line " + str(idx + 1) + ")")


def verify_tool_page():
    text = read(TOOL_PAGE)
    refs = text.count("LocalToolOption.PhoneControl")
    if refs != 2:
        fail("tool page PhoneControl refs=" + str(refs) + " (expected 2)")
    log("tool page still ok (refs=2)")


def main():
    log("root=" + ROOT)
    ok = 0
    try:
        patch_enum()
        ok += 1
    except SystemExit:
        pass
    try:
        patch_register()
        ok += 1
    except SystemExit:
        pass
    try:
        verify_tool_page()
    except SystemExit:
        pass
    if ok != 2:
        fail("LocalTools steps ok=" + str(ok) + "/2")
    log("DONE LocalTools enum + register")
    write_diag()


if __name__ == "__main__":
    main()
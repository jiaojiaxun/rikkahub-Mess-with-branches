#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhPhone335 -- 关键缺陷修复：330 的接入三处根本没执行。

实证（snapshot 的 ci_diag_batch330_phone_tools.txt）：
    [batch330] FAIL unbalanced () in .../PhoneTools.kt: 159/161

两个事实：
  1) PhoneTools.kt 的 159/161 是**误报**——多出的两个右括号来自注释里的
     "1)" "2)"，不是代码。文件本身是平衡的，Kotlin 能编译。
  2) 但 write_new() 在误报处 fail + exit(1)，所以 main() 里排在后面的
     patch_enum() 与 patch_tool_page() **一步都没跑**。

后果正是"死功能"：工具类写好了，却没有 LocalToolOption 枚举项、
没有 getTools 注册、助手页也没有开关。用户看不到、打不开、触发不了。

本批把这三处补上，并且：
  * 每一步独立执行，一步失败不阻断另一步（330 的教训）
  * 自检只统计代码行的括号（先剥掉注释里的编号），不再误报
  * 逐项复验：枚举存在、注册存在、开关行存在、引用次数正确
"""
import os
import sys

MARK = "rhPhone335"
DIAG_NAME = "ci_diag_batch335_phone_wire.txt"
DIAG = []


def log(msg):
    line = "[batch335] " + str(msg)
    print(line)
    DIAG.append(line)


def fail(msg):
    line = "FAIL " + str(msg)
    print("::error title=phone335::" + line)
    DIAG.append(line)
    write_diag()
    sys.exit(1)


def write_diag():
    try:
        with open(DIAG_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(DIAG) + "\n")
    except Exception as exc:  # noqa: BLE001
        print("::warning title=phone335::diag write failed: " + str(exc))


def repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    guess = os.path.abspath(os.path.join(here, ".."))
    if os.path.isdir(os.path.join(guess, "app")):
        return guess
    return os.getcwd()


ROOT = repo_root()
LOCAL_TOOLS = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt"
TOOL_PAGE = "app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/detail/AssistantLocalToolPage.kt"


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def write_text(rel, content):
    with open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def code_balance(text):
    """只统计代码行的括号：去掉 // 与 /* */ 注释、以及 "..." 字符串。"""
    depth_paren = 0
    depth_brace = 0
    in_block = False
    in_line = False
    in_str = False
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if in_block:
            if ch == "*" and nxt == "/":
                in_block = False
                i += 2
                continue
            i += 1
            continue
        if in_line:
            if ch == "\n":
                in_line = False
            i += 1
            continue
        if in_str:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_str = False
            i += 1
            continue
        if ch == "/" and nxt == "/":
            in_line = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            in_block = True
            i += 2
            continue
        if ch == '"':
            in_str = True
            i += 1
            continue
        if ch == "(":
            depth_paren += 1
        elif ch == ")":
            depth_paren -= 1
        elif ch == "{":
            depth_brace += 1
        elif ch == "}":
            depth_brace -= 1
        if depth_paren < 0 or depth_brace < 0:
            return depth_paren, depth_brace
        i += 1
    return depth_paren, depth_brace


ENUM_BLOCK = '''    @Serializable @SerialName("time_info")
    data object TimeInfo : LocalToolOption()

    /** rhPhone335: 手机操控（无障碍读屏 + 点击 / 输入 / 滑动）。 */
    @Serializable @SerialName("phone_control")
    data object PhoneControl : LocalToolOption()
'''

REG_BLOCK = '''        if (options.contains(LocalToolOption.PhoneControl)) { // rhPhone335
            tools.addAll(me.rerere.rikkahub.phone.buildPhoneTools(context))
        }
'''

TOOL_ROW = '''            rhToolItem(rhToolQuery, "手机操控（无障碍） 允许 AI 读屏、点击、输入、滑动来操作其它 App；银行 / 支付类默认不读不点，凭据框默认不代填") { // rhToolSearch225
            item(
                headlineContent = { Text("手机操控（无障碍）") },
                supportingContent = {
                    Text(
                        if (me.rerere.rikkahub.phone.PhoneAccessibilityService.connected()) {
                            "无障碍服务已开启 · 只读当前屏幕，动作前会请你确认"
                        } else {
                            "未开启无障碍服务 · 打开开关后会跳到系统设置，请找到「手机操控」并开启"
                        }
                    )
                },
                trailingContent = {
                    Switch(
                        checked = assistant.localTools.contains(LocalToolOption.PhoneControl),
                        onCheckedChange = { enabled ->
                            toggleLocalTool(LocalToolOption.PhoneControl, enabled)
                            if (enabled && !me.rerere.rikkahub.phone.PhoneAccessibilityService.connected()) {
                                runCatching {
                                    ctx.startActivity(
                                        android.content.Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS)
                                            .addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
                                    )
                                }
                            }
                        }
                    )
                }
            )
            } // rhToolSearch225
'''


def patch_enum():
    text = read(LOCAL_TOOLS)
    if "rhPhone335" in text:
        log("skip LocalTools.kt (already applied)")
        return
    needle = '''    @Serializable @SerialName("time_info")
    data object TimeInfo : LocalToolOption()
'''
    if text.count(needle) != 1:
        fail("LocalTools enum anchor count=" + str(text.count(needle)))
    text = text.replace(needle, ENUM_BLOCK, 1)

    reg = "        if (options.contains(LocalToolOption.ImageGeneration)) {"
    if text.count(reg) != 1:
        fail("LocalTools register anchor count=" + str(text.count(reg)))
    text = text.replace(reg, REG_BLOCK + reg, 1)

    write_text(LOCAL_TOOLS, text)
    back = read(LOCAL_TOOLS)
    if "data object PhoneControl" not in back:
        fail("LocalTools missing PhoneControl enum")
    if "buildPhoneTools(context)" not in back:
        fail("LocalTools missing buildPhoneTools registration")
    if back.count("data object PhoneControl") != 1:
        fail("PhoneControl enum count=" + str(back.count("data object PhoneControl")))
    bp, bb = code_balance(back)
    if bp != 0 or bb != 0:
        fail("LocalTools code balance paren=" + str(bp) + " brace=" + str(bb))
    log("patched LocalTools.kt (enum + register)")


def patch_tool_page():
    text = read(TOOL_PAGE)
    if "rhPhone335" in text:
        log("skip AssistantLocalToolPage.kt (already applied)")
        return
    needle = '            rhToolItem(rhToolQuery, "应用控制（App Control）'
    if text.count(needle) != 1:
        fail("tool page anchor count=" + str(text.count(needle)))
    text = text.replace(needle, TOOL_ROW + needle, 1)
    write_text(TOOL_PAGE, text)
    back = read(TOOL_PAGE)
    refs = back.count("LocalToolOption.PhoneControl")
    if refs != 2:
        fail("tool page PhoneControl refs=" + str(refs))
    bp, bb = code_balance(back)
    if bp != 0 or bb != 0:
        fail("tool page code balance paren=" + str(bp) + " brace=" + str(bb))
    log("patched AssistantLocalToolPage.kt (+1 row, refs=2)")


def main():
    log("root=" + ROOT)
    ok = 0
    try:
        patch_enum()
        ok += 1
    except SystemExit:
        pass
    try:
        patch_tool_page()
        ok += 1
    except SystemExit:
        pass
    if ok != 2:
        fail("wire steps ok=" + str(ok) + "/2")
    log("DONE both wire steps")
    write_diag()


if __name__ == "__main__":
    main()
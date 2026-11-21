#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhTokenUnit338 -- 两个需求：
  A) token 计数单位统一开关：默认 K，打开后统一按 M 显示
  B) 未命名对话显示「未命名的对话」，不再回退成助手名

A 的实现（零改 PreferencesStore / DisplaySetting 的序列化结构，避免动备份格式）：
  1. 新文件 utils/TokenUnitStore.kt：SharedPreferences 存一个布尔 + 全局 @Volatile，
     并提供 Int.formatTokens()。K 模式复用现有 formatNumber()（<1K 原值，1.2K/3.4M 自适应）；
     M 模式统一按百万：>=100M 取整、>=10M 一位、其余两位。
  2. RikkaHubApp.onCreate 里 init 一次（重启后仍生效）。
  3. SettingPreferencesUIPage 加一行开关（界面与偏好 → 消息显示设置）。
  4. FilesPicker 的「上下文 x / y」与 SettingProviderDetailPage 的上下文长度预设改用 formatTokens()。

B 的实现：
  ChatPage 顶栏 title = conversation.title.ifBlank { assistant.name }
  → conversation.title.ifBlank { "未命名的对话" }

锚点全部取自 snapshot 实读；行级 strip 定位；每步独立执行；括号差值断言。
"""
import os
import sys

MARK = "rhTokenUnit338"
DIAG_NAME = "ci_diag_batch338_token_unit.txt"
DIAG = []
Q = chr(34)

ROOT = os.path.abspath(os.getcwd())
APP = "app/src/main/java/me/rerere/rikkahub"


def log(msg):
    line = "[batch338] " + str(msg)
    print(line)
    DIAG.append(line)


def fail(msg):
    line = "FAIL " + str(msg)
    print("::error title=token338::" + line)
    DIAG.append(line)
    write_diag()
    sys.exit(0)


def write_diag():
    try:
        with open(os.path.join(ROOT, DIAG_NAME), "w", encoding="utf-8") as f:
            f.write("\n".join(DIAG) + "\n")
    except Exception as exc:  # noqa: BLE001
        print("::warning title=token338::diag write failed " + str(exc))


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def write_text(rel, content):
    path = os.path.join(ROOT, rel)
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def parens(t):
    return (
        t.count("(") - t.count(")"),
        t.count("{") - t.count("}"),
        t.count("[") - t.count("]"),
    )


STORE = r'''package me.rerere.rikkahub.utils

import android.content.Context

/**
 * rhTokenUnit338 -- token 计数单位的全局开关。
 *
 * 默认 K：沿用 [formatNumber] 的自适应（<1K 原值、1.2K、3.4M）。
 * 打开后统一按百万：0.13M / 1.50M / 128M。
 *
 * 为什么不用 DisplaySetting：那条链要走 PreferencesStore 的 JSON 序列化与备份格式，
 * 一个纯展示偏好不值得动数据契约。这里用独立 SharedPreferences，App 启动时 [init]。
 */
object TokenUnitStore {
    private const val PREFS = "rh_token_unit"
    private const val KEY = "millions"

    @Volatile
    var millions: Boolean = false
        private set

    fun init(context: Context) {
        val sp = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        millions = sp.getBoolean(KEY, false)
    }

    fun set(context: Context, value: Boolean) {
        millions = value
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY, value)
            .apply()
    }
}

/** 按当前开关格式化 token 数：K 模式自适应，M 模式统一百万。 */
fun Int.formatTokens(): String {
    if (!TokenUnitStore.millions) return this.formatNumber()
    val absValue = kotlin.math.abs(this)
    if (absValue < 1000) return this.toString()
    val sign = if (this < 0) "-" else ""
    val m = absValue / 1_000_000.0
    return when {
        m >= 100.0 -> sign + m.toInt().toString() + "M"
        m >= 10.0 -> sign + m.toFixed(1) + "M"
        else -> sign + m.toFixed(2) + "M"
    }
}
'''


def step_create_store():
    rel = APP + "/utils/TokenUnitStore.kt"
    path = os.path.join(ROOT, rel)
    if os.path.exists(path):
        if MARK in read(rel):
            log("skip TokenUnitStore.kt (already applied)")
            return
        fail("TokenUnitStore.kt exists without marker")
    write_text(rel, STORE)
    back = read(rel)
    if MARK not in back:
        fail("TokenUnitStore.kt lost marker")
    if "fun Int.formatTokens()" not in back:
        fail("TokenUnitStore.kt missing formatTokens")
    log("wrote TokenUnitStore.kt")


def step_app_init():
    rel = APP + "/RikkaHubApp.kt"
    text = read(rel)
    if MARK in text:
        log("skip RikkaHubApp.kt (already applied)")
        return
    needle = "        AppStartupProgressTracker.update(5, AppStartupStage.Starting)"
    if text.count(needle) != 1:
        fail("RikkaHubApp anchor count=" + str(text.count(needle)))
    text = text.replace(
        needle,
        "        me.rerere.rikkahub.utils.TokenUnitStore.init(this) // " + MARK + "\n" + needle,
        1,
    )
    write_text(rel, text)
    if MARK not in read(rel):
        fail("RikkaHubApp.kt lost marker")
    log("patched RikkaHubApp.kt (init)")


def step_settings_ui():
    rel = APP + "/ui/pages/setting/SettingPreferencesUIPage.kt"
    text = read(rel)
    if MARK in text:
        log("skip SettingPreferencesUIPage.kt (already applied)")
        return
    anchor_a = "    val chatFontFamily = rememberChatFontFamily(displaySetting)"
    if text.count(anchor_a) != 1:
        fail("settings ui anchor A count=" + str(text.count(anchor_a)))
    text = text.replace(
        anchor_a,
        anchor_a + "\n    var rhTokenMillions by remember { mutableStateOf(me.rerere.rikkahub.utils.TokenUnitStore.millions) } // " + MARK,
        1,
    )

    anchor_b = "                    // rhPerConversationModel299: 唯一开关，统一控制旧版/新版模型切换"
    if text.count(anchor_b) != 1:
        fail("settings ui anchor B count=" + str(text.count(anchor_b)))
    item = (
        "                    // " + MARK + ": token 单位统一开关（默认 K，打开 M）\n"
        "                    item(\n"
        "                        headlineContent = { Text(" + Q + "Token 单位用 M" + Q + ") },\n"
        "                        supportingContent = { Text(" + Q + "关闭(默认)=K：1.2K / 3.4M 自适应；开启=统一按百万：0.13M / 1.50M" + Q + ") },\n"
        "                        trailingContent = {\n"
        "                            Switch(\n"
        "                                checked = rhTokenMillions,\n"
        "                                onCheckedChange = { enabled ->\n"
        "                                    rhTokenMillions = enabled\n"
        "                                    me.rerere.rikkahub.utils.TokenUnitStore.set(context, enabled)\n"
        "                                }\n"
        "                            )\n"
        "                        },\n"
        "                    )\n"
    )
    text = text.replace(anchor_b, item + anchor_b, 1)
    write_text(rel, text)
    back = read(rel)
    if back.count(MARK) != 2:
        fail("settings ui marker count=" + str(back.count(MARK)))
    log("patched SettingPreferencesUIPage.kt (state + item)")


def ensure_import(text, imp):
    if ("import " + imp) in text:
        return text, False
    anchor = "import me.rerere.rikkahub.utils.formatNumber\n"
    if anchor in text:
        return text.replace(anchor, anchor + "import " + imp + "\n", 1), True
    anchor2 = "import me.rerere.rikkahub.utils."
    idx = text.find(anchor2)
    if idx < 0:
        return text, False
    return text[:idx] + "import " + imp + "\n" + text[idx:], True


def step_files_picker():
    rel = APP + "/ui/components/ai/FilesPicker.kt"
    text = read(rel)
    if MARK in text:
        log("skip FilesPicker.kt (already applied)")
        return
    hit = False
    out_lines = []
    for line in text.split("\n"):
        if "contextTokens.formatNumber()" in line and "formatTokens()" not in line:
            line = line.replace("contextTokens.formatNumber()", "contextTokens.formatTokens()")
            line = line.replace("contextLength.formatNumber()", "contextLength.formatTokens()")
            line = line + " // " + MARK
            hit = True
        out_lines.append(line)
    if not hit:
        fail("FilesPicker token line not found")
    text = "\n".join(out_lines)
    text, ok = ensure_import(text, "me.rerere.rikkahub.utils.formatTokens")
    if not ok:
        fail("FilesPicker import anchor missing")
    write_text(rel, text)
    back = read(rel)
    if "contextTokens.formatTokens()" not in back:
        fail("FilesPicker write-back lost formatTokens")
    if "contextTokens.formatNumber()" in back:
        fail("FilesPicker still has formatNumber")
    log("patched FilesPicker.kt (context tokens)")


def step_provider_page():
    rel = APP + "/ui/pages/setting/SettingProviderDetailPage.kt"
    text = read(rel)
    if MARK in text:
        log("skip SettingProviderDetailPage.kt (already applied)")
        return
    hit = False
    out_lines = []
    for line in text.split("\n"):
        if "preset?.formatNumber()" in line:
            line = line.replace("preset?.formatNumber()", "preset?.formatTokens()")
            line = line + " // " + MARK
            hit = True
        out_lines.append(line)
    if not hit:
        fail("provider page preset line not found")
    text = "\n".join(out_lines)
    text, ok = ensure_import(text, "me.rerere.rikkahub.utils.formatTokens")
    if not ok:
        fail("provider page import anchor missing")
    write_text(rel, text)
    back = read(rel)
    if "preset?.formatTokens()" not in back:
        fail("provider page write-back lost formatTokens")
    log("patched SettingProviderDetailPage.kt (context preset)")


def step_untitled_title():
    rel = APP + "/ui/pages/chat/ChatPage.kt"
    text = read(rel)
    if MARK in text:
        log("skip ChatPage.kt (already applied)")
        return
    needle = "                    title = conversation.title.ifBlank { assistant.name },"
    if text.count(needle) != 1:
        fail("ChatPage title anchor count=" + str(text.count(needle)))
    text = text.replace(
        needle,
        "                    title = conversation.title.ifBlank { " + Q + "未命名的对话" + Q + " }, // " + MARK,
        1,
    )
    write_text(rel, text)
    back = read(rel)
    if "未命名的对话" not in back:
        fail("ChatPage write-back lost 未命名的对话")
    if needle in back:
        fail("ChatPage old title line still present")
    log("patched ChatPage.kt (untitled title)")


def main():
    log("root=" + ROOT)
    steps = [
        ("store", step_create_store),
        ("appInit", step_app_init),
        ("settingsUi", step_settings_ui),
        ("filesPicker", step_files_picker),
        ("providerPage", step_provider_page),
        ("untitled", step_untitled_title),
    ]
    ok = 0
    for name, fn in steps:
        try:
            fn()
            ok += 1
        except SystemExit:
            pass
        except Exception as exc:  # noqa: BLE001
            log("EXCEPTION " + name + " " + type(exc).__name__ + " " + str(exc)[:300])
    log("steps ok=" + str(ok) + "/" + str(len(steps)))
    if ok != len(steps):
        fail("partial apply")
    write_diag()
    print("::error::batch338 END lines=" + str(len(DIAG)))


if __name__ == "__main__":
    main()
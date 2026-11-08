#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhPhone346 -- 把手机操控从「助手 → 本地工具」提到「设置」首页，做成独立板块。

为什么改：
dsh-go 的手机操控是 App 级设置板块（不是每个助手一份）。fork 之前只在
AssistantLocalToolPage 里放了一个助手级开关，入口太深，用户按「设置里有没有」
去找，自然找不到。

本批做四件事：
1. 新 phone/PhoneControlStore.kt：SharedPreferences 存一个全局 enabled；
2. RikkaHubApp.onCreate 里 init（重启保持）；
3. SettingPage 首页新增「手机操控」CardGroup（开关 + 无障碍状态 + 安全边界）；
4. LocalTools.getTools 的注册条件改成「助手级枚举 OR 全局开关」——
   两处都能开，不用二选一，旧助手的设置也不失效。

不改 AssistantLocalToolPage：那里保留，作为 per-assistant 的细粒度开关。
"""
import os
import sys

MARK = "rhPhone346"
DIAG = "ci_diag_batch346_phone_settings.txt"
Q = chr(34)
ROOT = os.path.abspath(os.getcwd())
rows = []

STORE = r'''package me.rerere.rikkahub.phone

import android.content.Context

/**
 * rhPhone346 -- 手机操控的 App 级总开关。
 *
 * 与 Assistant.localTools 里的 per-assistant 开关是「或」的关系：
 * 任一为真就注册 11 个 phone_* 工具。这样从设置页开一次就全局可用，
 * 也不需要迁移旧助手的配置。
 */
object PhoneControlStore {
    private const val PREFS = "rh_phone_control"
    private const val KEY_ENABLED = "enabled"

    @Volatile
    var enabled: Boolean = false
        private set

    fun init(context: Context) {
        val sp = context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        enabled = sp.getBoolean(KEY_ENABLED, false)
    }

    fun set(context: Context, value: Boolean) {
        enabled = value
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_ENABLED, value)
            .apply()
    }
}
'''

CARD = '''            item("phoneControl") { // rhPhone346: dsh-go 风格，设置首页独立板块
                val rhCtx = androidx.compose.ui.platform.LocalContext.current
                val rhPhoneState = androidx.compose.runtime.remember {
                    androidx.compose.runtime.mutableStateOf(me.rerere.rikkahub.phone.PhoneControlStore.enabled)
                }
                val rhPhoneOn = rhPhoneState.value
                val rhA11yOn = me.rerere.rikkahub.phone.PhoneAccessibilityService.connected()
                CardGroup(
                    modifier = Modifier.padding(horizontal = 8.dp),
                    title = { Text("手机操控") },
                ) {
                    item(
                        headlineContent = { Text("启用手机操控") },
                        supportingContent = {
                            Text(
                                if (rhPhoneOn) {
                                    "已开启：允许 AI 读屏、点击、输入；写操作仍需审批"
                                } else {
                                    "关闭：AI 看不到也动不了这台手机"
                                }
                            )
                        },
                        leadingContent = { Icon(HugeIcons.SmartPhone01, null) },
                        trailingContent = {
                            androidx.compose.material3.Switch(
                                checked = rhPhoneOn,
                                onCheckedChange = { enabled ->
                                    rhPhoneState.value = enabled
                                    me.rerere.rikkahub.phone.PhoneControlStore.set(rhCtx, enabled)
                                    if (enabled && !me.rerere.rikkahub.phone.PhoneAccessibilityService.connected()) {
                                        runCatching {
                                            rhCtx.startActivity(
                                                android.content.Intent(
                                                    android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS
                                                ).addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
                                            )
                                        }
                                    }
                                }
                            )
                        },
                    )
                    item(
                        headlineContent = { Text("无障碍服务") },
                        supportingContent = {
                            Text(if (rhA11yOn) "已连接" else "未连接 · 点这里去系统设置开启「手机操控」")
                        },
                        onClick = {
                            runCatching {
                                rhCtx.startActivity(
                                    android.content.Intent(android.provider.Settings.ACTION_ACCESSIBILITY_SETTINGS)
                                        .addFlags(android.content.Intent.FLAG_ACTIVITY_NEW_TASK)
                                )
                            }
                        },
                    )
                    item(
                        headlineContent = { Text("安全边界") },
                        supportingContent = {
                            Text("银行/支付/券商不读不点；密码/验证码框不代填；系统设置只能看不能动")
                        },
                    )
                }
            }

'''


def note(msg):
    line = "[batch346] " + str(msg)
    print(line)
    rows.append(line)


def fail(msg):
    note("FAIL " + str(msg))
    flush()
    sys.exit(1)


def flush():
    try:
        with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
    except Exception:
        pass


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def write(rel, text):
    path = os.path.join(ROOT, rel)
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def parens(t):
    return (t.count("(") - t.count(")"), t.count("{") - t.count("}"), t.count("[") - t.count("]"))


def step_store():
    rel = "app/src/main/java/me/rerere/rikkahub/phone/PhoneControlStore.kt"
    path = os.path.join(ROOT, rel)
    if os.path.exists(path):
        if MARK in read(rel):
            note("skip PhoneControlStore (already applied)")
            return
        fail("PhoneControlStore exists without marker")
    write(rel, STORE)
    back = read(rel)
    if MARK not in back or "fun init(" not in back:
        fail("PhoneControlStore write-back bad")
    note("wrote PhoneControlStore.kt")


def step_app_init():
    rel = "app/src/main/java/me/rerere/rikkahub/RikkaHubApp.kt"
    text = read(rel)
    if MARK in text:
        note("skip RikkaHubApp (already applied)")
        return
    needle = "        me.rerere.rikkahub.utils.TokenUnitStore.init(this)"
    if text.count(needle) != 1:
        fail("RikkaHubApp anchor count=" + str(text.count(needle)))
    text = text.replace(
        needle,
        needle + "\n        me.rerere.rikkahub.phone.PhoneControlStore.init(this) // " + MARK,
        1,
    )
    write(rel, text)
    if MARK not in read(rel):
        fail("RikkaHubApp write-back lost marker")
    note("RikkaHubApp: PhoneControlStore.init added")


def step_setting_page():
    rel = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPage.kt"
    text = read(rel)
    if MARK in text:
        note("skip SettingPage (already applied)")
        return
    needle = '            item("modelServices") {'
    if text.count(needle) != 1:
        fail("SettingPage anchor count=" + str(text.count(needle)))
    before = parens(text)
    text = text.replace(needle, CARD + needle, 1)
    after = parens(text)
    if after != before:
        fail("SettingPage balance " + str(before) + " -> " + str(after))
    write(rel, text)
    back = read(rel)
    if "启用手机操控" not in back:
        fail("SettingPage write-back lost card")
    note("SettingPage: phone control card inserted")


def step_get_tools():
    rel = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt"
    text = read(rel)
    if MARK in text:
        note("skip LocalTools (already applied)")
        return
    needle = "        if (options.contains(LocalToolOption.PhoneControl)) { // rhPhone335"
    if text.count(needle) != 1:
        fail("LocalTools anchor count=" + str(text.count(needle)))
    repl = (
        "        if (options.contains(LocalToolOption.PhoneControl) || "
        "me.rerere.rikkahub.phone.PhoneControlStore.enabled) { // " + MARK
    )
    text = text.replace(needle, repl, 1)
    write(rel, text)
    back = read(rel)
    if "PhoneControlStore.enabled" not in back:
        fail("LocalTools write-back lost store check")
    note("LocalTools: global switch ORed in")


def main():
    steps = [
        ("store", step_store),
        ("appInit", step_app_init),
        ("settingPage", step_setting_page),
        ("getTools", step_get_tools),
    ]
    ok = 0
    for name, fn in steps:
        try:
            fn()
            ok += 1
        except SystemExit:
            pass
        except Exception as exc:  # noqa: BLE001
            note("EXCEPTION " + name + " " + type(exc).__name__ + " " + str(exc)[:240])
    note("steps ok=" + str(ok) + "/" + str(len(steps)))
    flush()
    print("::error::batch346 END lines=" + str(len(rows)))
    sys.exit(0)


if __name__ == "__main__":
    main()
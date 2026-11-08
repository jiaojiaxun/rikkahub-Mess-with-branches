#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhPhone347 -- 修 346 的致命遗漏，并把 dsh-go 的确认策略补上。

━━ 346 的实测（snapshot ci_diag_batch346_phone_settings.txt） ━━
    wrote PhoneControlStore.kt
    RikkaHubApp: PhoneControlStore.init added
    SettingPage: phone control card inserted
    FAIL LocalTools anchor count=0
    steps ok=3/4

真因：336 插入注册行时用的 marker 是 `// rhPhone336`，346 却按 `// rhPhone335` 找。
后果：设置页有开关、拿到的是 true，但 getTools 只看 assistant.localTools，
      开关等于摆设——这是必须立刻修的假完成。

━━ 本批四件事 ━━
1. LocalTools 用**行级 strip**定位 `if (options.contains(LocalToolOption.PhoneControl)) {`
   （不带注释，不再赌 marker），改成「助手级 OR 全局」。
2. 新 PhonePoliciesStore：确认模式 + 三项解除限制，SharedPreferences 存。
3. PhoneCore.policies 改为只读 getter，统一从 store 取。
4. PhoneTools 的 6 处 needsApproval = { true } 改成「模式 != ALWAYS」；
   设置页加「确认模式」Select 与三项解锁 Switch（插在 346 的「安全边界」之前）。

不做：悬浮确认条 / 通知兜底（348）；截图标号 / A11yKeeper（349）；日志与 handoff 等待（350）。
"""
import os
import sys

MARK = "rhPhone347"
DIAG = "ci_diag_batch347_phone_policies.txt"
Q = chr(34)
ROOT = os.path.abspath(os.getcwd())
rows = []

STORE = r'''package me.rerere.rikkahub.phone

import android.content.Context
import android.content.SharedPreferences

/**
 * rhPhone347 -- 手机操控的策略存储（对齐 dsh-go 的 PhonePolicies）。
 *
 * 确认模式：ASK 每次都问 / TASK 本任务免确认 / ALWAYS 始终免确认。
 * 解除限制：systemPages（系统页可操作）、secretFields（可填密码框）、ownApp（可操作自己）。
 *
 * 用独立 SharedPreferences，不动 Settings/DisplaySetting 的序列化与备份格式。
 */
object PhonePoliciesStore {
    private const val PREFS = "rh_phone_policies"
    private const val KEY_MODE = "confirm_mode"
    private const val KEY_UNLOCK_SYSTEM = "unlock_system_pages"
    private const val KEY_UNLOCK_SECRET = "unlock_secret_fields"
    private const val KEY_UNLOCK_OWN = "unlock_own_app"

    @Volatile
    var current: PhonePolicies = PhonePolicies()
        private set

    fun init(context: Context) {
        val sp = prefs(context)
        current = PhonePolicies(
            confirmMode = ConfirmMode.fromWire(sp.getString(KEY_MODE, null)) ?: ConfirmMode.ASK,
            unlocks = PhoneUnlocks(
                systemPages = sp.getBoolean(KEY_UNLOCK_SYSTEM, false),
                secretFields = sp.getBoolean(KEY_UNLOCK_SECRET, false),
                ownApp = sp.getBoolean(KEY_UNLOCK_OWN, false),
            ),
        )
    }

    fun setConfirmMode(context: Context, mode: ConfirmMode) {
        prefs(context).edit().putString(KEY_MODE, mode.wire).apply()
        current = current.copy(confirmMode = mode)
    }

    /** key: system / secret / own */
    fun setUnlock(context: Context, key: String, value: Boolean) {
        val editor = prefs(context).edit()
        when (key) {
            "system" -> {
                editor.putBoolean(KEY_UNLOCK_SYSTEM, value)
                current = current.copy(unlocks = current.unlocks.copy(systemPages = value))
            }
            "secret" -> {
                editor.putBoolean(KEY_UNLOCK_SECRET, value)
                current = current.copy(unlocks = current.unlocks.copy(secretFields = value))
            }
            "own" -> {
                editor.putBoolean(KEY_UNLOCK_OWN, value)
                current = current.copy(unlocks = current.unlocks.copy(ownApp = value))
            }
        }
        editor.apply()
    }

    private fun prefs(context: Context): SharedPreferences =
        context.applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
}
'''

POLICY_UI = '''                    item(
                        headlineContent = { Text("确认模式") },
                        supportingContent = { Text("每次都问 / 本任务免确认 / 始终免确认（ALWAYS 下写操作不再弹审批卡）") },
                        trailingContent = {
                            Select(
                                options = me.rerere.rikkahub.phone.ConfirmMode.entries,
                                selectedOption = rhModeState.value,
                                onOptionSelected = { mode ->
                                    rhModeState.value = mode
                                    me.rerere.rikkahub.phone.PhonePoliciesStore.setConfirmMode(rhCtx, mode)
                                },
                                optionToString = { mode ->
                                    when (mode) {
                                        me.rerere.rikkahub.phone.ConfirmMode.ASK -> "每次都问"
                                        me.rerere.rikkahub.phone.ConfirmMode.TASK -> "本任务免确认"
                                        me.rerere.rikkahub.phone.ConfirmMode.ALWAYS -> "始终免确认"
                                    }
                                },
                                modifier = Modifier.width(150.dp)
                            )
                        },
                    )
                    item(
                        headlineContent = { Text("允许操作系统设置") },
                        supportingContent = { Text("默认关闭。打开后可点设置/权限/安装器页面，风险自负") },
                        trailingContent = {
                            Switch(
                                checked = rhUnlockState.value.systemPages,
                                onCheckedChange = { enabled ->
                                    rhUnlockState.value = rhUnlockState.value.copy(systemPages = enabled)
                                    me.rerere.rikkahub.phone.PhonePoliciesStore.setUnlock(rhCtx, "system", enabled)
                                }
                            )
                        },
                    )
                    item(
                        headlineContent = { Text("允许填写密码/验证码") },
                        supportingContent = { Text("默认关闭。打开后仍会遮罩日志，但键盘输入会进上下文") },
                        trailingContent = {
                            Switch(
                                checked = rhUnlockState.value.secretFields,
                                onCheckedChange = { enabled ->
                                    rhUnlockState.value = rhUnlockState.value.copy(secretFields = enabled)
                                    me.rerere.rikkahub.phone.PhonePoliciesStore.setUnlock(rhCtx, "secret", enabled)
                                }
                            )
                        },
                    )
                    item(
                        headlineContent = { Text("允许操作 RikkaHub 自己") },
                        supportingContent = { Text("默认关闭。防止 AI 点自己的确认按钮绕过审批") },
                        trailingContent = {
                            Switch(
                                checked = rhUnlockState.value.ownApp,
                                onCheckedChange = { enabled ->
                                    rhUnlockState.value = rhUnlockState.value.copy(ownApp = enabled)
                                    me.rerere.rikkahub.phone.PhonePoliciesStore.setUnlock(rhCtx, "own", enabled)
                                }
                            )
                        },
                    )
'''


def note(msg):
    line = "[batch347] " + str(msg)
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
    rel = "app/src/main/java/me/rerere/rikkahub/phone/PhonePoliciesStore.kt"
    path = os.path.join(ROOT, rel)
    if os.path.exists(path):
        if MARK in read(rel):
            note("skip PhonePoliciesStore (already applied)")
            return
        fail("PhonePoliciesStore exists without marker")
    write(rel, STORE)
    back = read(rel)
    if MARK not in back or "fun setConfirmMode(" not in back:
        fail("PhonePoliciesStore write-back bad")
    note("wrote PhonePoliciesStore.kt")


def step_app_init():
    rel = "app/src/main/java/me/rerere/rikkahub/RikkaHubApp.kt"
    text = read(rel)
    if MARK in text:
        note("skip RikkaHubApp (already applied)")
        return
    needle = "        me.rerere.rikkahub.phone.PhoneControlStore.init(this)"
    if text.count(needle) != 1:
        fail("RikkaHubApp anchor count=" + str(text.count(needle)))
    text = text.replace(
        needle,
        needle + "\n        me.rerere.rikkahub.phone.PhonePoliciesStore.init(this) // " + MARK,
        1,
    )
    write(rel, text)
    note("RikkaHubApp: PhonePoliciesStore.init added")


def step_local_tools():
    rel = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt"
    text = read(rel)
    if "PhoneControlStore.enabled" in text:
        note("skip LocalTools (already wired)")
        return
    lines = text.split("\n")
    target = "if (options.contains(LocalToolOption.PhoneControl)) {"
    idx = -1
    for i, line in enumerate(lines):
        if line.strip().startswith(target):
            idx = i
            break
    if idx < 0:
        fail("LocalTools phone control line not found")
    indent = lines[idx][:len(lines[idx]) - len(lines[idx].lstrip())]
    before = parens(text)
    lines[idx] = (
        indent + "if (options.contains(LocalToolOption.PhoneControl) || "
        "me.rerere.rikkahub.phone.PhoneControlStore.enabled) { // " + MARK
    )
    out = "\n".join(lines)
    after = parens(out)
    if after != before:
        fail("LocalTools balance " + str(before) + " -> " + str(after))
    write(rel, out)
    note("LocalTools: global switch ORed in (line " + str(idx + 1) + ")")


def step_core_getter():
    rel = "app/src/main/java/me/rerere/rikkahub/phone/PhoneCore.kt"
    text = read(rel)
    if "PhonePoliciesStore.current" in text:
        note("skip PhoneCore (already getter)")
        return
    needle = """    @Volatile
    var policies: PhonePolicies = PhonePolicies()"""
    if text.count(needle) != 1:
        fail("PhoneCore policies anchor count=" + str(text.count(needle)))
    repl = """    // """ + MARK + """: 策略统一由 PhonePoliciesStore 持有，设置页改完立即生效
    val policies: PhonePolicies
        get() = me.rerere.rikkahub.phone.PhonePoliciesStore.current"""
    text = text.replace(needle, repl, 1)
    write(rel, text)
    note("PhoneCore: policies -> store getter")


def step_needs_approval():
    rel = "app/src/main/java/me/rerere/rikkahub/phone/PhoneTools.kt"
    text = read(rel)
    if MARK in text:
        note("skip PhoneTools (already applied)")
        return
    needle = "    needsApproval = { true },"
    count = text.count(needle)
    if count != 6:
        fail("PhoneTools needsApproval count=" + str(count) + " (expected 6)")
    repl = (
        "    needsApproval = { me.rerere.rikkahub.phone.PhonePoliciesStore.current.confirmMode != "
        "me.rerere.rikkahub.phone.ConfirmMode.ALWAYS }, // " + MARK
    )
    text = text.replace(needle, repl, 1)
    text = text.replace(needle, repl, 1)
    text = text.replace(needle, repl, 1)
    text = text.replace(needle, repl, 1)
    text = text.replace(needle, repl, 1)
    text = text.replace(needle, repl, 1)
    if needle in text:
        fail("PhoneTools still has needsApproval = { true }")
    write(rel, text)
    note("PhoneTools: 6 needsApproval -> mode != ALWAYS")


def step_setting_ui():
    rel = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPage.kt"
    text = read(rel)
    if MARK in text:
        note("skip SettingPage (already applied)")
        return
    needle = """                    item(
                        headlineContent = { Text("安全边界") },"""
    if text.count(needle) != 1:
        fail("SettingPage safety row count=" + str(text.count(needle)))
    head = """                val rhModeState = androidx.compose.runtime.remember {
                    androidx.compose.runtime.mutableStateOf(
                        me.rerere.rikkahub.phone.PhonePoliciesStore.current.confirmMode
                    )
                }
                val rhUnlockState = androidx.compose.runtime.remember {
                    androidx.compose.runtime.mutableStateOf(
                        me.rerere.rikkahub.phone.PhonePoliciesStore.current.unlocks
                    )
                }
"""
    anchor_state = "                val rhPhoneOn = rhPhoneState.value\n"
    if text.count(anchor_state) != 1:
        fail("SettingPage state anchor count=" + str(text.count(anchor_state)))
    text = text.replace(anchor_state, anchor_state + head, 1)
    before = parens(text)
    text = text.replace(needle, POLICY_UI + needle, 1)
    after = parens(text)
    if after != before:
        fail("SettingPage balance " + str(before) + " -> " + str(after))
    write(rel, text)
    back = read(rel)
    for need in ("确认模式", "允许操作系统设置", "允许填写密码/验证码", "允许操作 RikkaHub 自己"):
        if need not in back:
            fail("SettingPage missing " + need)
    note("SettingPage: confirm mode + 3 unlocks inserted")


def main():
    steps = [
        ("store", step_store),
        ("appInit", step_app_init),
        ("localTools", step_local_tools),
        ("coreGetter", step_core_getter),
        ("needsApproval", step_needs_approval),
        ("settingUi", step_setting_ui),
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
    print("::error::batch347 END lines=" + str(len(rows)))
    sys.exit(0)


if __name__ == "__main__":
    main()
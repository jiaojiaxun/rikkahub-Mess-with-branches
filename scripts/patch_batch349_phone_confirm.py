#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhPhone349 -- 动作级确认通道（对齐 dsh-go 的 SafetyGate.Confirm + ControlOverlay）。

现状问题：写操作只有 RikkaHub 的工具审批卡（粗粒度，一次工具调用问一次），
dsh-go 问的是「在微信点『发送』」这种具体一步，且首次进 App / 敏感词 / 提交各有规则。

本批做四件事：
1. 新 phone/PhoneConfirmBus.kt：挂起等待用户选择，30 秒超时按拒绝；
2. 新 phone/PhoneConfirmHost.kt：Compose AlertDialog，观察 bus；
3. ChatPage 挂载 Host（锚点 AssistantBackground）；
4. PhoneCore：
   - Verdict 加 Confirm；
   - gate 末尾按规则（tap_xy / submit / 敏感词 / 逐写 App / 首次进 App）返回 Confirm；
   - checkWrite 改 suspend，遇到 Confirm 走 bus；
   - 6 个动作函数改 suspend（tap/type/scroll/key/tapXY/open）；
   - open 里的 gate 调用改成 when 三分支。
5. PhoneTools 的 needsApproval 全改 { false }——粗粒度审批卡让位给细粒度 bus。

不做（下一批）：通知兜底、悬浮条。应用内 Dialog 在没有前台聊天页时不会显示，
bus 会在 30 秒后按拒绝处理，这是安全的默认。
"""
import os
import sys

MARK = "rhPhone349"
DIAG = "ci_diag_batch349_confirm.txt"
Q = chr(34)
ROOT = os.path.abspath(os.getcwd())
rows = []

BUS = r'''package me.rerere.rikkahub.phone

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withTimeoutOrNull

/**
 * rhPhone349 -- 动作级确认通道。
 *
 * PhoneCore 在需要用户点头的那一步挂起在这里，UI 侧的 PhoneConfirmHost 弹窗，
 * 用户点允许/拒绝后 resume。30 秒没人理按拒绝处理（安全默认）。
 *
 * 不用 RikkaHub 的工具审批卡：那张卡是「一次工具调用」粒度，问的是
 * 「是否允许 phone_tap 执行」，而不是「是否在微信点发送」。
 */
object PhoneConfirmBus {
    class Request(
        val sentence: String,
        val appLabel: String?,
        val packageName: String?,
        val reason: String,
        val completer: CompletableDeferred<Boolean>,
    )

    private val _current = MutableStateFlow<Request?>(null)
    val current: StateFlow<Request?> = _current.asStateFlow()

    suspend fun ask(sentence: String, appLabel: String?, pkg: String?, reason: String): Boolean {
        val deferred = CompletableDeferred<Boolean>()
        _current.value = Request(sentence, appLabel, pkg, reason, deferred)
        return try {
            withTimeoutOrNull(30_000L) { deferred.await() } ?: false
        } finally {
            _current.value = null
        }
    }

    fun answer(allow: Boolean) {
        _current.value?.completer?.complete(allow)
    }
}
'''

HOST = r'''package me.rerere.rikkahub.phone

import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle

/**
 * rhPhone349 -- 动作级确认弹窗。挂在聊天页，观察 PhoneConfirmBus。
 *
 * 后台（聊天页不在前台）时不会显示，bus 30 秒后按拒绝处理。
 */
@Composable
fun PhoneConfirmHost() {
    val request by PhoneConfirmBus.current.collectAsStateWithLifecycle()
    val r = request ?: return
    AlertDialog(
        onDismissRequest = { PhoneConfirmBus.answer(false) },
        title = { Text("允许这一步吗？") },
        text = { Text(r.sentence) },
        confirmButton = {
            TextButton(onClick = { PhoneConfirmBus.answer(true) }) { Text("允许") }
        },
        dismissButton = {
            TextButton(onClick = { PhoneConfirmBus.answer(false) }) { Text("拒绝") }
        },
    )
}
'''

DESCRIBE = '''    /** rhPhone349: 把一步动作写成一句人话，给确认弹窗用 */
    private fun describeAction(
        kind: WriteKind,
        el: ScreenElement?,
        app: String,
        typed: String?,
        submit: Boolean,
    ): String {
        val label = el?.label?.takeIf { it.isNotBlank() } ?: el?.role?.takeIf { it.isNotBlank() } ?: "元素"
        return when (kind) {
            WriteKind.TAP -> "在「" + app + "」点「" + label + "」"
            WriteKind.LONG_TAP -> "在「" + app + "」长按「" + label + "」"
            WriteKind.TYPE -> "在「" + app + "」的「" + label + "」输入：\\"" +
                PhoneRules.quoteText(typed ?: "", 30) + "\\"" + if (submit) "，然后提交" else ""
            WriteKind.TAP_XY -> "在「" + app + "」点一个坐标"
            else -> "在「" + app + "」执行一步操作"
        }
    }

'''


def note(msg):
    line = "[batch349] " + str(msg)
    print(line)
    rows.append(line)


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


def step_new_files():
    for rel, body, must in [
        ("app/src/main/java/me/rerere/rikkahub/phone/PhoneConfirmBus.kt", BUS, "fun answer("),
        ("app/src/main/java/me/rerere/rikkahub/phone/PhoneConfirmHost.kt", HOST, "fun PhoneConfirmHost()"),
    ]:
        path = os.path.join(ROOT, rel)
        if os.path.exists(path):
            if MARK in read(rel):
                note("skip " + rel)
                continue
            note("exists without marker: " + rel)
            continue
        write(rel, body)
        if must not in read(rel):
            note("write-back bad: " + rel)
            continue
        note("wrote " + rel.split("/")[-1])


def step_chat_page():
    rel = "app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt"
    text = read(rel)
    if MARK in text:
        note("skip ChatPage (already applied)")
        return
    needle = "        AssistantBackground(setting = setting, modifier = Modifier)"
    if text.count(needle) != 1:
        note("ChatPage anchor count=" + str(text.count(needle)))
        return
    text = text.replace(
        needle,
        "        me.rerere.rikkahub.phone.PhoneConfirmHost() // " + MARK + "\n" + needle,
        1,
    )
    write(rel, text)
    note("ChatPage: PhoneConfirmHost mounted")


def step_verdict():
    rel = "app/src/main/java/me/rerere/rikkahub/phone/PhoneCore.kt"
    text = read(rel)
    if "class Confirm(" in text:
        note("skip Verdict (already applied)")
        return
    needle = """    private sealed class Verdict {
        class Allow(val reason: String) : Verdict()
        class Refuse(val message: String) : Verdict()
    }"""
    if text.count(needle) != 1:
        note("Verdict anchor count=" + str(text.count(needle)))
        return
    repl = """    private sealed class Verdict {
        class Allow(val reason: String) : Verdict()
        class Refuse(val message: String) : Verdict()
        class Confirm(
            val sentence: String,
            val reason: String,
            val pkg: String?,
            val app: String?,
        ) : Verdict()
    }"""
    text = text.replace(needle, repl, 1)
    write(rel, text)
    note("PhoneCore: Verdict.Confirm added")


def step_gate():
    rel = "app/src/main/java/me/rerere/rikkahub/phone/PhoneCore.kt"
    text = read(rel)
    if "describeAction(" in text:
        note("skip gate (already applied)")
        return
    needle = """        if (pkg != null && pkg !in p.confirmEveryWritePackages) approvedApps.add(pkg)
        return Verdict.Allow("ok")"""
    if text.count(needle) != 1:
        note("gate tail anchor count=" + str(text.count(needle)))
        return
    repl = """        // rhPhone349: 硬规则之后，按规则决定是否要用户点头（细粒度）
        if (p.confirmMode == ConfirmMode.ALWAYS) {
            if (pkg != null) approvedApps.add(pkg)
            return Verdict.Allow("always")
        }
        val everyWrite = pkg != null && pkg in p.confirmEveryWritePackages
        val firstInApp = !everyWrite && (pkg == null || pkg !in approvedApps)
        val word = if (kind == WriteKind.TAP || kind == WriteKind.LONG_TAP) {
            SensitiveWords.confirmHit(el?.label, el?.viewId)
        } else {
            null
        }
        val appLabel = appName(context, pkg)
        val action = describeAction(kind, el, appLabel, typed, submit)
        val reason = when {
            kind == WriteKind.TAP_XY -> "tap_xy"
            kind == WriteKind.TYPE && submit -> "submit"
            word != null -> "sensitive:" + word
            everyWrite -> "every-write"
            firstInApp -> "first-in-app"
            else -> null
        }
        if (reason == null) {
            if (pkg != null) approvedApps.add(pkg)
            return Verdict.Allow("ok")
        }
        val sentence = if (reason == "first-in-app") {
            "允许在本任务中操作「" + appLabel + "」？第一步：" + action
        } else {
            action
        }
        return Verdict.Confirm(sentence, reason, pkg, appLabel)"""
    before = parens(text)
    text = text.replace(needle, repl, 1)
    after = parens(text)
    if after != before:
        note("gate balance " + str(before) + " -> " + str(after))
        return
    write(rel, text)
    note("PhoneCore: gate returns Confirm by rule")


def step_describe():
    rel = "app/src/main/java/me/rerere/rikkahub/phone/PhoneCore.kt"
    text = read(rel)
    if "private fun describeAction(" in text:
        note("skip describeAction")
        return
    needle = "    private fun checkWrite("
    if text.count(needle) != 1:
        note("checkWrite anchor count=" + str(text.count(needle)))
        return
    text = text.replace(needle, DESCRIBE + needle, 1)
    write(rel, text)
    note("PhoneCore: describeAction inserted")


def step_check_write():
    rel = "app/src/main/java/me/rerere/rikkahub/phone/PhoneCore.kt"
    text = read(rel)
    if "PhoneConfirmBus.ask(" in text:
        note("skip checkWrite (already applied)")
        return
    needle = """    private fun checkWrite(
        context: Context,
        snap: Snapshot,
        kind: WriteKind,
        el: ScreenElement?,
        typed: String?,
        submit: Boolean,
        target: TargetInfo?,
    ) {
        val pkg = el?.packageName ?: snap.capture.packageName
        when (val verdict = gate(context, pkg, kind, el, typed, submit, target)) {
            is Verdict.Refuse -> throw Refused(verdict.message)
            is Verdict.Allow -> Unit
        }
    }"""
    if text.count(needle) != 1:
        note("checkWrite body anchor count=" + str(text.count(needle)))
        return
    repl = """    private suspend fun checkWrite(
        context: Context,
        snap: Snapshot,
        kind: WriteKind,
        el: ScreenElement?,
        typed: String?,
        submit: Boolean,
        target: TargetInfo?,
    ) {
        val pkg = el?.packageName ?: snap.capture.packageName
        when (val verdict = gate(context, pkg, kind, el, typed, submit, target)) {
            is Verdict.Refuse -> throw Refused(verdict.message)
            is Verdict.Allow -> Unit
            is Verdict.Confirm -> {
                val ok = PhoneConfirmBus.ask(verdict.sentence, verdict.app, verdict.pkg, verdict.reason)
                if (!ok) {
                    throw Refused("用户拒绝了这一步（或 30 秒内没有选择）。不要重试同一个动作；换个做法，或问用户想怎么做。")
                }
                if (verdict.pkg != null) approvedApps.add(verdict.pkg)
            }
        }
    }"""
    text = text.replace(needle, repl, 1)
    write(rel, text)
    note("PhoneCore: checkWrite suspend + Confirm branch")


def step_suspend_fns():
    rel = "app/src/main/java/me/rerere/rikkahub/phone/PhoneCore.kt"
    text = read(rel)
    targets = ["tap", "type", "scroll", "key", "tapXY", "open"]
    changed = 0
    for name in targets:
        old = "    private fun " + name + "("
        new = "    private suspend fun " + name + "("
        if old in text:
            text = text.replace(old, new, 1)
            changed += 1
    if changed != 6:
        note("suspend conversion changed=" + str(changed) + "/6")
        return
    write(rel, text)
    note("PhoneCore: 6 action fns -> suspend")


def step_open_gate():
    rel = "app/src/main/java/me/rerere/rikkahub/phone/PhoneCore.kt"
    text = read(rel)
    if "is Verdict.Confirm ->" in text and "open" in text and "PhoneConfirmBus.ask" in text:
        note("skip open gate")
        return
    needle = """            val verdict = gate(context, pkg, kind, null, null, false, null)
            if (verdict is Verdict.Refuse) throw Refused(verdict.message)"""
    if text.count(needle) != 1:
        note("open gate anchor count=" + str(text.count(needle)))
        return
    repl = """            when (val verdict = gate(context, pkg, kind, null, null, false, null)) {
                is Verdict.Refuse -> throw Refused(verdict.message)
                is Verdict.Allow -> Unit
                is Verdict.Confirm -> {
                    val ok = PhoneConfirmBus.ask(verdict.sentence, verdict.app, verdict.pkg, verdict.reason)
                    if (!ok) throw Refused("用户拒绝了这一步。")
                }
            }"""
    text = text.replace(needle, repl, 1)
    write(rel, text)
    note("PhoneCore: open gate -> when(3 branches)")


def step_tools_approval():
    rel = "app/src/main/java/me/rerere/rikkahub/phone/PhoneTools.kt"
    text = read(rel)
    if "needsApproval = { false }, // rhPhone349" in text:
        note("skip PhoneTools (already applied)")
        return
    needle = "    needsApproval = { me.rerere.rikkahub.phone.PhonePoliciesStore.current.confirmMode != me.rerere.rikkahub.phone.ConfirmMode.ALWAYS }, // rhPhone348a"
    count = text.count(needle)
    if count < 1:
        note("PhoneTools approval anchor count=" + str(count))
        return
    text = text.replace(
        needle,
        "    needsApproval = { false }, // " + MARK + ": 细粒度确认交给 PhoneConfirmBus",
    )
    write(rel, text)
    note("PhoneTools: " + str(count) + " needsApproval -> false")


def main():
    step_new_files()
    step_chat_page()
    step_verdict()
    step_gate()
    step_describe()
    step_check_write()
    step_suspend_fns()
    step_open_gate()
    step_tools_approval()
    note("DONE")
    flush()
    print("::error::batch349 END lines=" + str(len(rows)))
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        note("EXCEPTION " + type(exc).__name__ + " " + str(exc)[:240])
        flush()
        sys.exit(0)
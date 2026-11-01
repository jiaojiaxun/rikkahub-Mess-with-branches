#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhPhone331 -- 自查修补：PhoneTools 引用了 PhoneCore.PHONE_INTENT，但 329 没实现它。

这是我推完 330 后立刻做的一致性自查发现的编译级断链：
  PhoneTools.kt  intentTool()  ->  PhoneCore.PHONE_INTENT   （常量不存在）
  且 PhoneCore.call 的 when 没有 intent 分支                （工具会掉进 else）
同时修一个真实隐患：
  PhoneTools 的 run() 用 kotlinx.coroutines.runBlocking 调 suspend 的 PhoneCore.call，
  在 suspend lambda 里会阻塞当前线程；改成 suspend 直调。

本批只改两个已存在的文件，锚点均来自 snapshot 实读。
"""
import os
import sys

MARK = "rhPhone331"
DIAG_NAME = "ci_diag_batch331_phone_intent.txt"
DIAG = []


def log(msg):
    line = "[batch331] " + str(msg)
    print(line)
    DIAG.append(line)


def fail(msg):
    line = "FAIL " + str(msg)
    print("::error title=phone331::" + line)
    DIAG.append(line)
    write_diag()
    sys.exit(1)


def write_diag():
    try:
        with open(DIAG_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(DIAG) + "\n")
    except Exception as exc:  # noqa: BLE001
        print("::warning title=phone331::diag write failed: " + str(exc))


def repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    guess = os.path.abspath(os.path.join(here, ".."))
    if os.path.isdir(os.path.join(guess, "app")):
        return guess
    return os.getcwd()


ROOT = repo_root()
PKG_DIR = "app/src/main/java/me/rerere/rikkahub/phone"
CORE = PKG_DIR + "/PhoneCore.kt"
TOOLS = PKG_DIR + "/PhoneTools.kt"


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def write_text(rel, content):
    path = os.path.join(ROOT, rel)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def replace_once(text, needle, replacement, label):
    count = text.count(needle)
    if count != 1:
        fail("anchor count=" + str(count) + " for " + label)
    return text.replace(needle, replacement, 1)


INTENT_IMPL = r'''    private fun intent(context: Context, args: JsonObject): Result {
        val kind = args.str("kind") ?: return Result("intent 需要 kind", true)
        val intent = when (kind) {
            "settings" -> {
                val page = args.str("page") ?: "home"
                val action = when (page) {
                    "wifi" -> Settings.ACTION_WIFI_SETTINGS
                    "bluetooth" -> Settings.ACTION_BLUETOOTH_SETTINGS
                    "mobile_network" -> Settings.ACTION_DATA_ROAMING_SETTINGS
                    "airplane" -> Settings.ACTION_AIRPLANE_MODE_SETTINGS
                    "display" -> Settings.ACTION_DISPLAY_SETTINGS
                    "sound" -> Settings.ACTION_SOUND_SETTINGS
                    "battery" -> Settings.ACTION_BATTERY_SAVER_SETTINGS
                    "location" -> Settings.ACTION_LOCATION_SOURCE_SETTINGS
                    "date" -> Settings.ACTION_DATE_SETTINGS
                    "language" -> Settings.ACTION_LOCALE_SETTINGS
                    "storage" -> Settings.ACTION_INTERNAL_STORAGE_SETTINGS
                    "nfc" -> Settings.ACTION_NFC_SETTINGS
                    else -> Settings.ACTION_SETTINGS
                }
                Intent(action)
            }
            "dial" -> Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + (args.str("number") ?: "")))
            "sms_draft" -> Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:" + (args.str("number") ?: ""))).apply {
                putExtra("sms_body", args.str("text") ?: "")
            }
            "share" -> Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_TEXT, args.str("text") ?: "")
            }
            "navigate" -> {
                val destination = args.str("destination")
                    ?: return Result("navigate 需要 destination", true)
                Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0?q=" + Uri.encode(destination)))
            }
            "calendar" -> {
                val begin = args.str("begin") ?: return Result("calendar 需要 begin", true)
                Intent(Intent.ACTION_INSERT).apply {
                    data = android.provider.CalendarContract.Events.CONTENT_URI
                    putExtra(android.provider.CalendarContract.EXTRA_EVENT_BEGIN_TIME, parseMillis(begin))
                    args.str("end")?.let {
                        putExtra(android.provider.CalendarContract.EXTRA_EVENT_END_TIME, parseMillis(it))
                    }
                    putExtra(android.provider.CalendarContract.Events.TITLE, args.str("title") ?: "")
                }
            }
            else -> return Result(
                "intent 的 kind 只能是 settings / dial / sms_draft / share / navigate / calendar",
                true,
            )
        }
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            context.startActivity(intent)
            sleepForUi(500)
            val next = publish(context, capture(requireService(), context), false, null, emptyList())
            Result("已打开 " + kind + "\n" + next.formatted.text)
        } catch (e: Throwable) {
            Result("打不开这个界面：" + (e.message ?: e.toString()) + "。可以让用户自己打开，或改用 phone_handoff。", true)
        }
    }

    /** 接受 2026-10-24T19:00 或 2026-10-24；解析失败给"一小时后"，不让日程直接丢掉。 */
    private fun parseMillis(value: String): Long = runCatching {
        java.time.LocalDateTime.parse(value).atZone(java.time.ZoneId.systemDefault()).toInstant().toEpochMilli()
    }.recoverCatching {
        java.time.LocalDate.parse(value).atStartOfDay(java.time.ZoneId.systemDefault()).toInstant().toEpochMilli()
    }.getOrElse { System.currentTimeMillis() + 3_600_000L }

'''


def patch_core():
    text = read(CORE)
    if MARK in text:
        log("skip PhoneCore.kt (already applied)")
        return
    text = replace_once(
        text,
        '''                    PHONE_HANDOFF -> handoff(context, args)
                    else -> Result("未知的手机操控工具：$tool", true)''',
        '''                    PHONE_HANDOFF -> handoff(context, args)
                    PHONE_INTENT -> intent(context, args)
                    else -> Result("未知的手机操控工具：$tool", true)''',
        "call when",
    )
    text = replace_once(
        text,
        '''    const val PHONE_HANDOFF = "phone_handoff"
}''',
        '''    const val PHONE_HANDOFF = "phone_handoff"
    const val PHONE_INTENT = "phone_intent"
}''',
        "PHONE_INTENT const",
    )
    text = replace_once(
        text,
        '''    private fun handoff(context: Context, args: JsonObject): Result {''',
        INTENT_IMPL + '''    private fun handoff(context: Context, args: JsonObject): Result {''',
        "intent impl",
    )
    write_text(CORE, text)
    back = read(CORE)
    if "PHONE_INTENT" not in back:
        fail("PhoneCore write-back lost PHONE_INTENT")
    if "private fun intent(" not in back:
        fail("PhoneCore write-back lost intent impl")
    for op, cl in [("{", "}"), ("(", ")")]:
        if back.count(op) != back.count(cl):
            fail("PhoneCore unbalanced " + op + cl + ": " + str(back.count(op)) + "/" + str(back.count(cl)))
    log("patched PhoneCore.kt (intent branch + const + impl)")


def patch_tools():
    text = read(TOOLS)
    if MARK in text:
        log("skip PhoneTools.kt (already applied)")
        return
    text = replace_once(
        text,
        '''private fun run(context: Context, name: String, args: JsonObject): List<UIMessagePart> {
    val result = kotlinx.coroutines.runBlocking { PhoneCore.call(context, name, args) }
    return listOf(UIMessagePart.Text(result.text))
}''',
        '''private suspend fun run(context: Context, name: String, args: JsonObject): List<UIMessagePart> {
    val result = PhoneCore.call(context, name, args)
    return listOf(UIMessagePart.Text(result.text))
}''',
        "run() blocking",
    )
    write_text(TOOLS, text)
    back = read(TOOLS)
    if "runBlocking" in back:
        fail("PhoneTools still contains runBlocking")
    if "private suspend fun run(" not in back:
        fail("PhoneTools write-back lost suspend run()")
    log("patched PhoneTools.kt (suspend run)")


def main():
    log("root=" + ROOT)
    patch_core()
    patch_tools()
    log("DONE")
    write_diag()


if __name__ == "__main__":
    main()
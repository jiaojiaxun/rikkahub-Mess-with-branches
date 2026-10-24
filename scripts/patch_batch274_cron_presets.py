#!/usr/bin/env python3
# batch274 (Phase 3): CronPresets as the single source of truth for preset schedules.
#   * CronTools.schedule_job gains an optional `preset` id
#   * AppControlService.scheduleCronJob gains the same `preset` id
# New file data/cron/CronPresets.kt + CronPresetsTest.kt are committed directly.
# MARK=rhCronPresets
import sys
from pathlib import Path

MARK = "rhCronPresets"
NL = chr(10)
Q = chr(34)
DIAG = "ci_diag_batch274.txt"
applied = []
failed = []


def diag(msg):
    try:
        with open(DIAG, "a", encoding="utf-8") as f:
            f.write(msg + NL)
    except Exception:
        pass


def fail(msg):
    diag("FAIL " + msg)
    print("::error title=batch274::" + msg)
    raise SystemExit(0)


def read(path):
    p = Path(path)
    if not p.exists():
        fail("missing file: " + path)
    return p.read_text(encoding="utf-8")


def write(path, content):
    Path(path).write_text(content, encoding="utf-8")


def replace_text(content, old, new, label):
    if old not in content:
        fail(label + " text not found")
    n = content.count(old)
    if n != 1:
        fail(label + " text not unique: " + str(n))
    applied.append(label)
    return content.replace(old, new, 1)


def edit_cron_tools():
    path = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/CronTools.kt"
    content = read(path)
    if MARK in content:
        diag("cron tools already patched")
        return
    old_head = (
        "            val params = args.jsonObject" + NL
        + "            val name = params[" + Q + "name" + Q + "]?.jsonPrimitive?.contentOrNull" + NL
        + "                ?: return@Tool errEnv(" + Q + "invalid_name" + Q + ", " + Q + "name is required" + Q + ")" + NL
        + "            val cron = params[" + Q + "cron" + Q + "]?.jsonPrimitive?.contentOrNull" + NL
        + "                ?: return@Tool errEnv(" + Q + "invalid_cron" + Q + ", " + Q + "cron is required" + Q + ")" + NL
        + "            val prompt = params[" + Q + "prompt" + Q + "]?.jsonPrimitive?.contentOrNull" + NL
        + "                ?: return@Tool errEnv(" + Q + "invalid_prompt" + Q + ", " + Q + "prompt is required" + Q + ")"
    )
    new_head = (
        "            val params = args.jsonObject" + NL
        + "            // " + MARK + ": preset 与 cron 同源（CronPresets），预设值可被显式参数覆盖" + NL
        + "            val presetId = params[" + Q + "preset" + Q + "]?.jsonPrimitive?.contentOrNull" + NL
        + "            val preset = if (presetId != null) {" + NL
        + "                CronPresets.resolve(presetId)" + NL
        + "                    ?: return@Tool errEnv(" + NL
        + "                        " + Q + "unknown_preset" + Q + "," + NL
        + "                        " + Q + "unknown preset id: " + Q + " + presetId + " + Q + " (available: " + Q + " + CronPresets.ids() + " + Q + ")" + Q + "," + NL
        + "                    )" + NL
        + "            } else null" + NL
        + "            val name = params[" + Q + "name" + Q + "]?.jsonPrimitive?.contentOrNull" + NL
        + "                ?: preset?.title" + NL
        + "                ?: return@Tool errEnv(" + Q + "invalid_name" + Q + ", " + Q + "name is required" + Q + ")" + NL
        + "            val cron = params[" + Q + "cron" + Q + "]?.jsonPrimitive?.contentOrNull" + NL
        + "                ?: preset?.cronExpression" + NL
        + "                ?: return@Tool errEnv(" + Q + "invalid_cron" + Q + ", " + Q + "cron is required" + Q + ")" + NL
        + "            val prompt = params[" + Q + "prompt" + Q + "]?.jsonPrimitive?.contentOrNull" + NL
        + "                ?: preset?.suggestedPrompt?.takeIf { it.isNotBlank() }" + NL
        + "                ?: return@Tool errEnv(" + Q + "invalid_prompt" + Q + ", " + Q + "prompt is required" + Q + ")"
    )
    content = replace_text(content, old_head, new_head, "cron-execute-head")

    req_old = "                required = listOf(" + Q + "name" + Q + ", " + Q + "cron" + Q + ", " + Q + "prompt" + Q + "),"
    req_new = (
        "                // " + MARK + ": name/cron/prompt 可由 preset 供值，因此不再强制必填（缺失仍会报错）" + NL
        + "                required = emptyList(),"
    )
    content = replace_text(content, req_old, req_new, "cron-required")

    prop_anchor = (
        "                    put(" + Q + "assistant_id" + Q + ", buildJsonObject {" + NL
        + "                        put(" + Q + "type" + Q + ", " + Q + "string" + Q + ")" + NL
        + "                        put(" + Q + "description" + Q + ", " + Q + "Assistant UUID for new conversations (omit for current)" + Q + ")" + NL
        + "                    })"
    )
    prop_add = (
        prop_anchor + NL
        + "                    put(" + Q + "preset" + Q + ", buildJsonObject {" + NL
        + "                        put(" + Q + "type" + Q + ", " + Q + "string" + Q + ")" + NL
        + "                        put(" + Q + "description" + Q + ", " + Q + "Preset id; supplies name/cron/prompt: " + Q + " + CronPresets.ids())" + NL
        + "                    })"
    )
    content = replace_text(content, prop_anchor, prop_add, "cron-param")

    desc_anchor = "            conversation_id=\"new\" to create a fresh conversation on every fire. Every schedule needs approval."
    desc_add = (
        "            conversation_id=\"new\" to create a fresh conversation on every fire. Every schedule needs approval." + NL
        + "            Pass preset=<id> to use a built-in schedule instead of a raw cron expression; " + NL
        + "            explicit name/cron/prompt still win over the preset values. Presets: " + Q + Q + " + CronPresets.ids()."
    )
    content = replace_text(content, desc_anchor, desc_add, "cron-description")

    imp_anchor = "import me.rerere.rikkahub.data.cron.CronJobStore"
    content = replace_text(content, imp_anchor,
                           "import me.rerere.rikkahub.data.cron.CronJobStore" + NL + "import me.rerere.rikkahub.data.cron.CronPresets // " + MARK,
                           "cron-import")
    write(path, content)


def edit_appcontrol_cron():
    path = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/appcontrol/AppControlService.kt"
    content = read(path)
    if MARK in content:
        diag("appcontrol cron already patched")
        return
    old = (
        "        val name = strArg(args, " + Q + "name" + Q + ") ?: return errorJson(" + Q + "name required" + Q + ")" + NL
        + "        val cron = strArg(args, " + Q + "cron" + Q + ") ?: return errorJson(" + Q + "cron required" + Q + ")" + NL
        + "        val prompt = strArg(args, " + Q + "prompt" + Q + ") ?: return errorJson(" + Q + "prompt required" + Q + ")"
    )
    new = (
        "        // " + MARK + ": 与 CronTools 共用 CronPresets（单一数据源），显式参数优先" + NL
        + "        val presetId = strArg(args, " + Q + "preset" + Q + ")" + NL
        + "        val preset = if (presetId != null) {" + NL
        + "            me.rerere.rikkahub.data.cron.CronPresets.resolve(presetId)" + NL
        + "                ?: return errorJson(" + NL
        + "                    " + Q + "unknown preset id: " + Q + " + presetId + " + Q + " (available: " + Q + " + me.rerere.rikkahub.data.cron.CronPresets.ids() + " + Q + ")" + Q + "," + NL
        + "                )" + NL
        + "        } else null" + NL
        + "        val name = strArg(args, " + Q + "name" + Q + ") ?: preset?.title ?: return errorJson(" + Q + "name required" + Q + ")" + NL
        + "        val cron = strArg(args, " + Q + "cron" + Q + ") ?: preset?.cronExpression ?: return errorJson(" + Q + "cron required" + Q + ")" + NL
        + "        val prompt = strArg(args, " + Q + "prompt" + Q + ") ?: preset?.suggestedPrompt?.takeIf { it.isNotBlank() }" + NL
        + "            ?: return errorJson(" + Q + "prompt required" + Q + ")"
    )
    content = replace_text(content, old, new, "appcontrol-cron-preset")
    write(path, content)


def main():
    for label, fn in (("cron-tools", edit_cron_tools), ("appcontrol-cron", edit_appcontrol_cron)):
        try:
            fn()
        except SystemExit:
            failed.append(label)
        except Exception as e:
            diag("EXCEPTION " + label + ": " + repr(e))
            failed.append(label)
    diag("applied=" + str(len(applied)) + " failed=" + str(len(failed)))
    if applied:
        print("::notice title=batch274-applied::" + ",".join(applied))
    if failed:
        print("::error title=batch274-FAILED::" + ",".join(failed))


main()

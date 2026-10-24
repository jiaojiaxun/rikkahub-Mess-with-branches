#!/usr/bin/env python3
# batch277: redo the AppControlService half of Phase 1 with a clean, line-based patch.
#
# batch272's edit_service built one of its replacement blocks as a Python tuple, so
# content.replace() raised TypeError before write() ran: the whitelist, the three action
# implementations, the error-detail list and the query snapshot were never persisted.
# This script only touches AppControlService.kt, matches lines by strip() equality, and
# reads the file back at the end to prove all four edits are present.
# MARK=rhAppControlTheme
import sys
from pathlib import Path

MARK = "rhAppControlTheme"
NL = chr(10)
DIAG = "ci_diag_batch277.txt"
PATH = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/appcontrol/AppControlService.kt"
applied = []


def diag(msg):
    try:
        with open(DIAG, "a", encoding="utf-8") as f:
            f.write(msg + NL)
    except Exception:
        pass


def fail(msg):
    diag("FAIL " + msg)
    print("::error title=batch277::" + msg)
    raise SystemExit(0)


def insert_after_line(content, anchor, block, label):
    lines = content.split(NL)
    hits = [i for i, line in enumerate(lines) if line.strip() == anchor.strip()]
    if len(hits) != 1:
        fail(label + " line count=" + str(len(hits)) + " [" + anchor + "]")
    lines.insert(hits[0] + 1, block)
    applied.append(label)
    return NL.join(lines)


def insert_before_line(content, anchor, block, label):
    lines = content.split(NL)
    hits = [i for i, line in enumerate(lines) if line.strip() == anchor.strip()]
    if len(hits) != 1:
        fail(label + " line count=" + str(len(hits)) + " [" + anchor + "]")
    lines.insert(hits[0], block)
    applied.append(label)
    return NL.join(lines)


def replace_line(content, anchor, block, label):
    lines = content.split(NL)
    hits = [i for i, line in enumerate(lines) if line.strip() == anchor.strip()]
    if len(hits) != 1:
        fail(label + " line count=" + str(len(hits)) + " [" + anchor + "]")
    lines[hits[0]:hits[0] + 1] = block.split(NL)
    applied.append(label)
    return NL.join(lines)


WHITELIST_BLOCK = '''        // rhAppControlTheme: 主题 / 动态色 / 显示设置
        "set_theme" -> setTheme(args)
        "set_dynamic_color" -> setDynamicColor(args)
        "set_display_setting" -> setDisplaySetting(args)'''

DETAIL_BLOCK = '''                    "delete_cron_job, pause_cron_job, resume_cron_job, trigger_cron_job, " +
                    "set_theme, set_dynamic_color, set_display_setting",'''

SNAPSHOT_BLOCK = '''        put("enable_web_fetch_tools", settings.enableWebFetchTools)
        // rhAppControlTheme: 主题快照（只读，供模型判断当前外观）
        put("theme_id", settings.themeId)
        put("dynamic_color", settings.dynamicColor)'''

IMPL_BLOCK = '''    // ==== rhAppControlTheme: 主题 / 动态色 / 显示设置实现 ====

    private suspend fun setTheme(args: JsonObject): JsonObject {
        val themeId = strArg(args, "theme_id")
        val mode = strArg(args, "mode")
        if (themeId.isNullOrBlank() && mode.isNullOrBlank()) {
            return errorJson("theme_id or mode required")
        }
        if (!themeId.isNullOrBlank()) {
            val presets = me.rerere.rikkahub.ui.theme.PresetThemes
            val available = presets.map { it.id } + settings.customThemes.map { it.id }
            if (available.none { it == themeId }) {
                return errorJson(
                    "unknown theme_id: " + themeId + " (available: " + available.joinToString(", ") + ")"
                )
            }
            settingsStore.update { old -> old.copy(themeId = themeId) }
        }
        val appliedTheme = settingsStore.settingsFlow.value.themeId
        val kind = if (me.rerere.rikkahub.ui.theme.PresetThemes.any { p -> p.id == appliedTheme }) "preset" else "custom"
        return buildJsonObject {
            put("success", true)
            put("theme_id", appliedTheme)
            put("theme_kind", kind)
            if (!mode.isNullOrBlank()) {
                put("mode", mode)
                put("mode_note", "dark/light follows the app color mode; each theme carries both schemes")
            }
        }
    }

    private suspend fun setDynamicColor(args: JsonObject): JsonObject {
        val enabled = args["enabled"]?.toString()?.toBooleanStrictOrNull()
            ?: return errorJson("enabled (boolean) required")
        settingsStore.update { old -> old.copy(dynamicColor = enabled) }
        return successJson("dynamic color enabled=" + enabled)
    }

    private suspend fun setDisplaySetting(args: JsonObject): JsonObject {
        val key = strArg(args, "key") ?: return errorJson("key required")
        val raw = args["value"]?.toString()?.trim('"') ?: return errorJson("value required")
        var changed = false
        settingsStore.update { old ->
            val display = old.displaySetting
            val updated = when (key) {
                "bubble_opacity" -> raw.toFloatOrNull()?.let { v -> display.copy(bubbleOpacity = v.coerceIn(0.1f, 1f)) }
                "show_user_avatar" -> raw.toBooleanStrictOrNull()?.let { v -> display.copy(showUserAvatar = v) }
                "show_assistant_bubble" -> raw.toBooleanStrictOrNull()?.let { v -> display.copy(showAssistantBubble = v) }
                "show_model_icon" -> raw.toBooleanStrictOrNull()?.let { v -> display.copy(showModelIcon = v) }
                "show_model_name" -> raw.toBooleanStrictOrNull()?.let { v -> display.copy(showModelName = v) }
                "show_token_usage" -> raw.toBooleanStrictOrNull()?.let { v -> display.copy(showTokenUsage = v) }
                "show_thinking_content" -> raw.toBooleanStrictOrNull()?.let { v -> display.copy(showThinkingContent = v) }
                "show_date_time_in_message" -> raw.toBooleanStrictOrNull()?.let { v -> display.copy(showDateTimeInMessage = v) }
                else -> null
            }
            if (updated == null) {
                old
            } else {
                changed = true
                old.copy(displaySetting = updated)
            }
        }
        if (!changed) {
            return errorJson(
                "unsupported key: " + key + " (supported: bubble_opacity, show_user_avatar, " +
                    "show_assistant_bubble, show_model_icon, show_model_name, show_token_usage, " +
                    "show_thinking_content, show_date_time_in_message)"
            )
        }
        return successJson("display setting " + key + " updated")
    }
'''


def main():
    p = Path(PATH)
    if not p.exists():
        fail("missing file: " + PATH)
    content = p.read_text(encoding="utf-8")
    if MARK in content:
        diag("already patched (marker present), verify only")
    else:
        content = insert_after_line(content, '"trigger_cron_job" -> triggerCronJob(args)', WHITELIST_BLOCK, "whitelist")
        content = replace_line(
            content,
            '"delete_cron_job, pause_cron_job, resume_cron_job, trigger_cron_job",',
            DETAIL_BLOCK,
            "error-detail",
        )
        content = replace_line(
            content,
            'put("enable_web_fetch_tools", settings.enableWebFetchTools)',
            SNAPSHOT_BLOCK,
            "snapshot",
        )
        content = insert_before_line(content, "@OptIn(ExperimentalUuidApi::class)", IMPL_BLOCK, "impls")
        p.write_text(content, encoding="utf-8")

    check = p.read_text(encoding="utf-8")
    missing = []
    for needle in (MARK, "private suspend fun setTheme(", "private suspend fun setDynamicColor(",
                   "private suspend fun setDisplaySetting(", 'put("theme_id", settings.themeId)'):
        if needle not in check:
            missing.append(needle)
    if missing:
        fail("verify failed, missing: " + " | ".join(missing))
    diag("applied=" + ",".join(applied) + " verify=ok")
    print("::notice title=batch277-ok::" + ",".join(applied))


main()

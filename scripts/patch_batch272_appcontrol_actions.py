#!/usr/bin/env python3
# batch272 (Phase 1): App Control action-level approval + theme/display actions.
#   * rikkahub_apply_change gets an action-scoped approvalKey
#   * whitelist: set_theme / set_dynamic_color / set_display_setting
#   * query snapshot: theme_id / dynamic_color
# MARK=rhAppControlTheme
import sys
from pathlib import Path

MARK = "rhAppControlTheme"
NL = chr(10)
Q = chr(34)
DIAG = "ci_diag_batch272.txt"
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
    print("::error title=batch272::" + msg)
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


def insert_after_line(content, anchor, block, label):
    lines = content.split(NL)
    hits = [i for i, line in enumerate(lines) if line.strip() == anchor.strip()]
    if len(hits) != 1:
        fail(label + " anchor count=" + str(len(hits)) + " [" + anchor + "]")
    lines.insert(hits[0] + 1, block)
    applied.append(label)
    return NL.join(lines)


def edit_tools():
    path = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/appcontrol/AppControlTools.kt"
    content = read(path)
    if MARK in content:
        diag("appcontrol tools already patched")
        return
    anchor = "        needsApproval = { true },"
    block = (
        "        // rhAppControlTheme: 动作级审批键 —— 批一次 set_theme 不会放行 toggle_provider_enabled" + NL
        + "        approvalKey = { args ->" + NL
        + "            me.rerere.rikkahub.data.ai.tools.ToolApprovalIdentity" + NL
        + "                .actionScopedKey(" + Q + "rikkahub_apply_change" + Q + ", args)" + NL
        + "        },"
    )
    content = insert_after_line(content, anchor, block, "tools-approvalKey")

    content = replace_text(content, "                        put(" + Q + "version" + Q + ", 4)",
                            "                        put(" + Q + "version" + Q + ", 5)", "tools-version")
    cron_add = "                            add(JsonPrimitive(" + Q + "trigger_cron_job" + Q + "))"
    theme_add = (
        cron_add + NL
        + "                            add(JsonPrimitive(" + Q + "set_theme" + Q + "))" + NL
        + "                            add(JsonPrimitive(" + Q + "set_dynamic_color" + Q + "))" + NL
        + "                            add(JsonPrimitive(" + Q + "set_display_setting" + Q + "))"
    )
    content = replace_text(content, cron_add, theme_add, "tools-capabilities")

    desc_anchor = "            - trigger_cron_job {job_id}"
    desc_add = (
        desc_anchor + NL
        + "            - set_theme {theme_id} (theme_id must already exist; optional mode=light|dark is" + NL
        + "              echoed back as a note, dark/light follows the app color mode)" + NL
        + "            - set_dynamic_color {enabled}" + NL
        + "            - set_display_setting {key, value}: bubble_opacity (0.1-1.0) or boolean keys" + NL
        + "              show_user_avatar / show_assistant_bubble / show_model_icon / show_model_name /" + NL
        + "              show_token_usage / show_thinking_content / show_date_time_in_message"
    )
    content = replace_text(content, desc_anchor, desc_add, "tools-description")
    write(path, content)


def edit_service():
    path = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/appcontrol/AppControlService.kt"
    content = read(path)
    if MARK in content:
        diag("appcontrol service already patched")
        return
    anchor = "        " + Q + "trigger_cron_job" + Q + " -> triggerCronJob(args)"
    block = (
        "        // rhAppControlTheme: 主题 / 动态色 / 显示设置" + NL
        + "        " + Q + "set_theme" + Q + " -> setTheme(args)" + NL
        + "        " + Q + "set_dynamic_color" + Q + " -> setDynamicColor(args)" + NL
        + "        " + Q + "set_display_setting" + Q + " -> setDisplaySetting(args)"
    )
    content = insert_after_line(content, anchor, block, "service-whitelist")

    old_detail = "                    " + Q + "delete_cron_job, pause_cron_job, resume_cron_job, trigger_cron_job" + Q + ","
    new_detail = (
        "                    " + Q + "delete_cron_job, pause_cron_job, resume_cron_job, trigger_cron_job, " + Q + " +" + NL
        + "                    " + Q + "set_theme, set_dynamic_color, set_display_setting" + Q + ","
    )
    content = replace_text(content, old_detail, new_detail, "service-error-detail")

    snap_anchor = "        put(" + Q + "enable_web_fetch_tools" + Q + ", settings.enableWebFetchTools)"
    snap_add = (
        snap_anchor + NL
        + "        // rhAppControlTheme: 主题快照（只读，供模型判断当前外观）" + NL
        + "        put(" + Q + "theme_id" + Q + ", settings.themeId)" + NL
        + "        put(" + Q + "dynamic_color" + Q + ", settings.dynamicColor)"
    )
    content = replace_text(content, snap_anchor, snap_add, "service-snapshot")

    fn_anchor = "    @OptIn(ExperimentalUuidApi::class)"
    fn_block = (
        "    // ==== rhAppControlTheme: 主题 / 动态色 / 显示设置实现 ====" + NL
        + "" + NL
        + "    private suspend fun setTheme(args: JsonObject): JsonObject {" + NL
        + "        val themeId = strArg(args, " + Q + "theme_id" + Q + ")" + NL
        + "        val mode = strArg(args, " + Q + "mode" + Q + ")" + NL
        + "        if (themeId.isNullOrBlank() && mode.isNullOrBlank()) {" + NL
        + "            return errorJson(" + Q + "theme_id or mode required" + Q + ")" + NL
        + "        }" + NL
        + "        if (!themeId.isNullOrBlank()) {" + NL
        + "            val presets = me.rerere.rikkahub.ui.theme.PresetThemes" + NL
        + "            val available = presets.map { it.id } + settings.customThemes.map { it.id }" + NL
        + "            if (available.none { it == themeId }) {" + NL
        + "                return errorJson(" + Q + "unknown theme_id: " + Q + " + themeId + " + NL
        + "                    " + Q + " (available: " + Q + " + available.joinToString(", ") + " + Q + ")" + Q + ")" + NL
        + "            }" + NL
        + "            settingsStore.update { old -> old.copy(themeId = themeId) }" + NL
        + "        }" + NL
        + "        val applied = settingsStore.settingsFlow.value.themeId" + NL
        + "        val kind = if (me.rerere.rikkahub.ui.theme.PresetThemes.any { it.id == applied }) " + Q + "preset" + Q + " else " + Q + "custom" + Q + NL
        + "        return buildJsonObject {" + NL
        + "            put(" + Q + "success" + Q + ", true)" + NL
        + "            put(" + Q + "theme_id" + Q + ", applied)" + NL
        + "            put(" + Q + "theme_kind" + Q + ", kind)" + NL
        + "            if (!mode.isNullOrBlank()) {" + NL
        + "                put(" + Q + "mode" + Q + ", mode)" + NL
        + "                put(" + Q + "mode_note" + Q + ", " + Q + "dark/light follows the app color mode; each theme carries both schemes" + Q + ")" + NL
        + "            }" + NL
        + "        }" + NL
        + "    }" + NL
        + "" + NL
        + "    private suspend fun setDynamicColor(args: JsonObject): JsonObject {" + NL
        + "        val enabled = args[" + Q + "enabled" + Q + "]?.toString()?.toBooleanStrictOrNull()" + NL
        + "            ?: return errorJson(" + Q + "enabled (boolean) required" + Q + ")" + NL
        + "        settingsStore.update { old -> old.copy(dynamicColor = enabled) }" + NL
        + "        return successJson(" + Q + "dynamic color enabled=" + Q + " + enabled)" + NL
        + "    }" + NL
        + "" + NL
        + "    private suspend fun setDisplaySetting(args: JsonObject): JsonObject {" + NL
        + "        val key = strArg(args, " + Q + "key" + Q + ") ?: return errorJson(" + Q + "key required" + Q + ")" + NL
        + "        val raw = args[" + Q + "value" + Q + "]?.toString()?.trim('" + Q + "') ?: return errorJson(" + Q + "value required" + Q + ")" + NL
        + "        var applied = false" + NL
        + "        settingsStore.update { old ->" + NL
        + "            val display = old.displaySetting" + NL
        + "            val updated = when (key) {" + NL
        + "                " + Q + "bubble_opacity" + Q + " -> raw.toFloatOrNull()?.let { display.copy(bubbleOpacity = it.coerceIn(0.1f, 1f)) }" + NL
        + "                " + Q + "show_user_avatar" + Q + " -> raw.toBooleanStrictOrNull()?.let { display.copy(showUserAvatar = it) }" + NL
        + "                " + Q + "show_assistant_bubble" + Q + " -> raw.toBooleanStrictOrNull()?.let { display.copy(showAssistantBubble = it) }" + NL
        + "                " + Q + "show_model_icon" + Q + " -> raw.toBooleanStrictOrNull()?.let { display.copy(showModelIcon = it) }" + NL
        + "                " + Q + "show_model_name" + Q + " -> raw.toBooleanStrictOrNull()?.let { display.copy(showModelName = it) }" + NL
        + "                " + Q + "show_token_usage" + Q + " -> raw.toBooleanStrictOrNull()?.let { display.copy(showTokenUsage = it) }" + NL
        + "                " + Q + "show_thinking_content" + Q + " -> raw.toBooleanStrictOrNull()?.let { display.copy(showThinkingContent = it) }" + NL
        + "                " + Q + "show_date_time_in_message" + Q + " -> raw.toBooleanStrictOrNull()?.let { display.copy(showDateTimeInMessage = it) }" + NL
        + "                else -> null" + NL
        + "            }" + NL
        + "            if (updated == null) {" + NL
        + "                old" + NL
        + "            } else {" + NL
        + "                applied = true" + NL
        + "                old.copy(displaySetting = updated)" + NL
        + "            }" + NL
        + "        }" + NL
        + "        if (!applied) {" + NL
        + "            return errorJson(" + NL
        + "                " + Q + "unsupported key: " + Q + " + key + " + NL
        + "                    " + Q + " (supported: bubble_opacity, show_user_avatar, show_assistant_bubble, " + Q + " +" + NL
        + "                    " + Q + "show_model_icon, show_model_name, show_token_usage, show_thinking_content, " + Q + " +" + NL
        + "                    " + Q + "show_date_time_in_message)" + Q + "," + NL
        + "            )" + NL
        + "        }" + NL
        + "        return successJson(" + Q + "display setting " + Q + " + key + " + Q + " updated" + Q + ")" + NL
        + "    }" + NL
        + "" + NL
        + fn_anchor
    )
    content = replace_text(content, fn_anchor, fn_block, "service-impls")
    write(path, content)


def main():
    for label, fn in (("tools", edit_tools), ("service", edit_service)):
        try:
            fn()
        except SystemExit:
            failed.append(label)
        except Exception as e:
            diag("EXCEPTION " + label + ": " + repr(e))
            failed.append(label)
    diag("applied=" + str(len(applied)) + " failed=" + str(len(failed)))
    if applied:
        print("::notice title=batch272-applied::" + ",".join(applied))
    if failed:
        print("::error title=batch272-FAILED::" + ",".join(failed))


main()

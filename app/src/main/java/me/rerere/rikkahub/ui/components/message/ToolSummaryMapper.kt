package me.rerere.rikkahub.ui.components.message

/**
 * 工具调用语义化摘要映射器。
 *
 * 将 ThinkingBlock 里的 ToolStep / ServerToolStep 按 toolName 分类,
 * 生成类似「操作了 3 个文件 · 调用了 MCP · 生成了图片」的摘要。
 *
 * 分类规则覆盖 fork 里所有已注册工具(LocalTools + CronTools + SubAgent + AppControl + Browser + ImageGeneration)。
 * 未匹配的工具走默认「使用了工具」分支,不会遗漏。
 */
object ToolSummaryMapper {

    fun summarize(steps: List<ThinkingStep>): String? {
        val toolNames = steps.mapNotNull { step ->
            when (step) {
                is ThinkingStep.ToolStep -> step.tool.toolName
                is ThinkingStep.ServerToolStep -> step.tool.toolName
                else -> null
            }
        }
        if (toolNames.isEmpty()) return null

        val categories = mutableMapOf<String, Int>()
        for (name in toolNames) {
            val cat = categorize(name)
            categories[cat] = (categories[cat] ?: 0) + 1
        }

        return categories.entries.joinToString(" \u00b7 ") { (cat, count) ->
            if (count > 1) {
                cat + " " + count + " \u6b21"
            } else {
                cat
            }
        }
    }

    @Suppress("kotlin:S1192")
    private fun categorize(name: String): String = when {
        name.startsWith("mcp__") -> "\u8c03\u7528\u4e86 MCP"
        name.startsWith("browser_") -> "\u6d4f\u89c8\u4e86\u7f51\u9875"
        name.startsWith("cron_") -> "\u7ba1\u7406\u4e86\u5b9a\u65f6\u4efb\u52a1"
        name.startsWith("subagent_") -> "\u8c03\u5ea6\u4e86\u5b50\u4ee3\u7406"
        name.startsWith("rikkahub_") -> "\u63a7\u5236\u4e86\u5e94\u7528"
        name.startsWith("keystore_") -> "\u5bc6\u94a5\u64cd\u4f5c"
        name.startsWith("nfc_") -> "NFC \u64cd\u4f5c"
        name.startsWith("read_") ||
        name.startsWith("list_") ||
        name.startsWith("file_") ||
        name.startsWith("find_") ||
        name.startsWith("write_") ||
        name.startsWith("edit_") ||
        name.startsWith("delete_") ||
        name.startsWith("move_") ||
        name.startsWith("copy_") ||
        name.startsWith("batch_") ||
        name.startsWith("zip") ||
        name.startsWith("unzip") ||
        name == "create_directory" ||
        name == "grant_directory_access" ||
        name == "list_storage_volumes" ||
        name == "list_granted_directories" ||
        name == "show_image" ||
        name == "open_file" -> "\u64cd\u4f5c\u4e86\u6587\u4ef6"
        name == "web_fetch" || name == "web_extract" -> "\u641c\u7d22\u4e86\u7f51\u9875"
        name == "generate_image" -> "\u751f\u6210\u4e86\u56fe\u7247"
        name == "camera_photo" -> "\u62cd\u4e86\u7167\u7247"
        name == "send_notification" || name == "toast" -> "\u53d1\u9001\u4e86\u901a\u77e5"
        name == "mic_recorder" -> "\u5f55\u4e86\u97f3"
        name == "speech_to_text" -> "\u8bed\u97f3\u8f6c\u6587\u5b57"
        name == "media_scanner" -> "\u626b\u63cf\u4e86\u5a92\u4f53"
        name == "memory_tool" -> "\u7ba1\u7406\u4e86\u8bb0\u5fc6"
        name == "skill_install_from_url" || name == "skill_install_from_text" -> "\u5b89\u88c5\u4e86\u6280\u80fd"
        name == "create_calendar_event" -> "\u521b\u5efa\u4e86\u65e5\u5386\u4e8b\u4ef6"
        name == "create_contact" -> "\u521b\u5efa\u4e86\u8054\u7cfb\u4eba"
        name == "open_wifi_settings" -> "\u6253\u5f00\u4e86 WiFi \u8bbe\u7f6e"
        name == "show_location_on_map" -> "\u663e\u793a\u4e86\u5730\u56fe"
        name == "set_wallpaper" -> "\u8bbe\u7f6e\u4e86\u58c1\u7eb8"
        name == "time_info" -> "\u67e5\u8be2\u4e86\u65f6\u95f4"
        name == "location" -> "\u67e5\u8be2\u4e86\u4f4d\u7f6e"
        name == "download_file" -> "\u4e0b\u8f7d\u4e86\u6587\u4ef6"
        name == "check_token_usage" -> "\u68c0\u67e5\u4e86\u7528\u91cf"
        name == "run_js" -> "\u8fd0\u884c\u4e86\u811a\u672c"
        name == "fingerprint" -> "\u9a8c\u8bc1\u4e86\u6307\u7eb9"
        name == "send_sms" || name == "send_sms_intent" -> "\u53d1\u9001\u4e86\u77ed\u4fe1"
        name == "send_email_intent" -> "\u53d1\u9001\u4e86\u90ae\u4ef6"
        name == "search_contacts" || name == "list_contacts" -> "\u67e5\u770b\u4e86\u8054\u7cfb\u4eba"
        name == "call_log" -> "\u67e5\u770b\u4e86\u901a\u8bdd\u8bb0\u5f55"
        name == "list_sms_inbox" || name == "search_sms" -> "\u67e5\u770b\u4e86\u77ed\u4fe1"
        else -> "\u4f7f\u7528\u4e86\u5de5\u5177"
    }
}

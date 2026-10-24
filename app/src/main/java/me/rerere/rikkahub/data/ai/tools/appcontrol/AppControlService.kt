package me.rerere.rikkahub.data.ai.tools.appcontrol

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import me.rerere.ai.provider.ProviderSetting
import me.rerere.rikkahub.data.ai.mcp.McpServerConfig
import me.rerere.rikkahub.data.datastore.Settings
import me.rerere.rikkahub.data.datastore.SettingsStore
import me.rerere.rikkahub.data.model.Assistant
import kotlin.uuid.ExperimentalUuidApi
import kotlin.uuid.Uuid

/**
 * AppControl gateway (L0-L3 merged into one APK), ported from feat/app-control-v2.
 *
 * Read side returns a redacted snapshot of the app settings: never exposes apiKey,
 * tokens, passwords, or headers. Write side is a whitelist; every write tool is
 * marked needsApproval = true by the tool factory in AppControlTools.kt.
 *
 * Writes go through [SettingsStore.update]; that class exposes both a
 * `update(settings: Settings)` and an `update(fn: (Settings) -> Settings)` overload,
 * so the transform form below is the intended usage.
 */
class AppControlService(
    private val settingsStore: SettingsStore,
) {
    val settings: Settings
        get() = settingsStore.settingsFlow.value

    /** Redacted read-only snapshot, safe to hand to the model. */
    fun queryAppState(): JsonObject = buildJsonObject {
        put("assistant_id", settings.assistantId.toString())
        put("chat_model_id", settings.chatModelId.toString())
        put("fast_model_id", settings.fastModelId.toString())
        put("enable_web_fetch_tools", settings.enableWebFetchTools)
        // rhAppControlTheme: 主题快照（只读，供模型判断当前外观）
        put("theme_id", settings.themeId)
        put("dynamic_color", settings.dynamicColor)
        put("web_server", buildJsonObject {
            put("enabled", settings.webServerEnabled)
            put("port", settings.webServerPort)
            put("jwt_enabled", settings.webServerJwtEnabled)
            put("localhost_only", settings.webServerLocalhostOnly)
        })
        put("search", buildJsonObject {
            put("selected_index", settings.searchServiceSelected)
            put(
                "services",
                kotlinx.serialization.json.buildJsonArray {
                    settings.searchServices.forEach { svc ->
                        add(
                            buildJsonObject {
                                // SearchServiceOptions carries no stable public display
                                // name; the concrete subclass name is the reliable id.
                                put("type", svc::class.simpleName ?: "unknown")
                            }
                        )
                    }
                }
            )
        })
        put("providers", kotlinx.serialization.json.buildJsonArray {
            settings.providers.forEach { p ->
                add(providerSnapshot(p))
            }
        })
        put("assistants", kotlinx.serialization.json.buildJsonArray {
            settings.assistants.forEach { a ->
                add(assistantSnapshot(a))
            }
        })
        put("mcp_servers", kotlinx.serialization.json.buildJsonArray {
            settings.mcpServers.forEach { m ->
                add(mcpSnapshot(m))
            }
        })
    }

    private fun providerSnapshot(p: ProviderSetting): JsonObject = buildJsonObject {
        put("id", p.id.toString())
        put("name", p.name)
        put("type", p::class.simpleName ?: "unknown")
        put("enabled", p.enabled)
        put("built_in", p.builtIn)
        put("models", kotlinx.serialization.json.buildJsonArray {
            p.models.forEach { m ->
                add(
                    buildJsonObject {
                        put("id", m.id.toString())
                        put("model_id", m.modelId)
                        put("display_name", m.displayName)
                        put("context_length", m.contextLength ?: 0)
                    }
                )
            }
        })
    }

    private fun assistantSnapshot(a: Assistant): JsonObject = buildJsonObject {
        put("id", a.id.toString())
        put("name", a.name)
        put("chat_model_id", a.chatModelId?.toString())
        put("enable_web_search", a.enableWebSearch)
        put("enable_memory", a.enableMemory)
        put("use_global_memory", a.useGlobalMemory)
        put("enable_recent_chats_reference", a.enableRecentChatsReference)
        put("stream_output", a.streamOutput)
        put("reasoning_level", a.reasoningLevel.name)
        put("context_message_limit", a.contextMessageLimit)
        put("max_tokens", a.maxTokens)
        put("temperature", a.temperature)
        put("top_p", a.topP)
        put("workspace_id", a.workspaceId?.toString())
    }

    private fun mcpSnapshot(m: McpServerConfig): JsonObject = buildJsonObject {
        put("id", m.id.toString())
        put("name", m.commonOptions.name)
        put("enable", m.commonOptions.enable)
        put("type", when (m) {
            is McpServerConfig.SseTransportServer -> "sse"
            is McpServerConfig.StreamableHTTPServer -> "streamable_http"
        })
        put("tool_count", m.commonOptions.tools.size)
    }

    /** Whitelisted writes; every caller must mark needsApproval = true. */
    suspend fun applyChange(action: String, args: JsonObject): JsonObject = when (action) {
        "switch_assistant" -> switchAssistant(args)
        "set_chat_model" -> setChatModel(args)
        "set_fast_model" -> setFastModel(args)
        "update_assistant" -> updateAssistant(args)
        "toggle_provider_enabled" -> toggleProviderEnabled(args)
        "rename_provider" -> renameProvider(args)
        "toggle_mcp_server" -> toggleMcpServer(args)
        "set_web_server" -> setWebServer(args)
        // rhAppControlCron: 定时任务动作（2026-10-03 用户/AI 反馈补充）
        "schedule_cron_job" -> scheduleCronJob(args)
        "list_cron_jobs" -> listCronJobs()
        "delete_cron_job" -> deleteCronJob(args)
        "pause_cron_job" -> pauseCronJob(args)
        "resume_cron_job" -> resumeCronJob(args)
        "trigger_cron_job" -> triggerCronJob(args)
        // rhAppControlTheme: 主题 / 动态色 / 显示设置
        "set_theme" -> setTheme(args)
        "set_dynamic_color" -> setDynamicColor(args)
        "set_display_setting" -> setDisplaySetting(args)
        else -> buildJsonObject {
            put("error", "unknown_action")
            put(
                "detail",
                "action must be one of: switch_assistant, set_chat_model, set_fast_model, " +
                    "update_assistant, toggle_provider_enabled, rename_provider, " +
                    "toggle_mcp_server, set_web_server, schedule_cron_job, list_cron_jobs, " +
                    "delete_cron_job, pause_cron_job, resume_cron_job, trigger_cron_job, " +
                    "set_theme, set_dynamic_color, set_display_setting",
            )
        }
    }

    // ==== rhAppControlCron: 定时任务动作实现（v3: 修 contentOrNull import + jobs() suspend）====

    private fun cronStore(): me.rerere.rikkahub.data.cron.CronJobStore =
        org.koin.core.context.GlobalContext.get().get()

    private fun cronScheduler(): me.rerere.rikkahub.service.CronJobScheduler =
        org.koin.core.context.GlobalContext.get().get()

    private fun cronJobToJson(job: me.rerere.rikkahub.data.model.CronJob): JsonObject =
        buildJsonObject {
            put("id", job.id)
            put("name", job.name)
            put("cron", job.cronExpression)
            put("prompt", job.prompt)
            if (job.assistantId != null) put("assistant_id", job.assistantId)
            if (job.conversationId != null) put("conversation_id", job.conversationId)
            put("enabled", job.enabled)
            put("created_at_ms", job.createdAt)
        }

    private fun strArg(args: JsonObject, key: String): String? =
        (args[key] as? JsonPrimitive)?.contentOrNull

    private suspend fun scheduleCronJob(args: JsonObject): JsonObject {
        // rhCronPresets: 与 CronTools 共用 CronPresets（单一数据源），显式参数优先
        val presetId = strArg(args, "preset")
        val preset = if (presetId != null) {
            me.rerere.rikkahub.data.cron.CronPresets.resolve(presetId)
                ?: return errorJson(
                    "unknown preset id: " + presetId + " (available: " + me.rerere.rikkahub.data.cron.CronPresets.ids() + ")",
                )
        } else null
        val name = strArg(args, "name") ?: preset?.title ?: return errorJson("name required")
        val cron = strArg(args, "cron") ?: preset?.cronExpression ?: return errorJson("cron required")
        val prompt = strArg(args, "prompt") ?: preset?.suggestedPrompt?.takeIf { it.isNotBlank() }
            ?: return errorJson("prompt required")
        if (!me.rerere.rikkahub.data.model.CronParser.isValid(cron)) {
            return errorJson("not a valid 5-field cron expression: $cron")
        }
        val rawConversation = strArg(args, "conversation_id")
        val targetConversation = when {
            rawConversation == null -> null
            rawConversation == "new" -> null
            else -> rawConversation
        }
        val job = me.rerere.rikkahub.data.model.CronJob(
            id = kotlin.uuid.Uuid.random().toString(),
            name = name,
            prompt = prompt,
            cronExpression = cron,
            assistantId = strArg(args, "assistant_id"),
            conversationId = targetConversation,
            enabled = true,
            createdAt = System.currentTimeMillis(),
        )
        cronStore().upsert(job)
        cronScheduler().schedule(job)
        return successJson("scheduled cron job ${job.id} ($name)")
    }

    private suspend fun listCronJobs(): JsonObject = buildJsonObject {
        put("jobs", kotlinx.serialization.json.buildJsonArray {
            cronStore().jobs().forEach { add(cronJobToJson(it)) }
        })
    }

    private suspend fun deleteCronJob(args: JsonObject): JsonObject {
        val jobId = strArg(args, "job_id") ?: return errorJson("job_id required")
        cronStore().delete(jobId)
        cronScheduler().cancel(jobId)
        return successJson("deleted job $jobId")
    }

    private suspend fun pauseCronJob(args: JsonObject): JsonObject {
        val jobId = strArg(args, "job_id") ?: return errorJson("job_id required")
        val job = cronStore().jobs().firstOrNull { it.id == jobId }
            ?: return errorJson("no such job: $jobId")
        cronStore().upsert(job.copy(enabled = false))
        cronScheduler().cancel(jobId)
        return successJson("paused job $jobId")
    }

    private suspend fun resumeCronJob(args: JsonObject): JsonObject {
        val jobId = strArg(args, "job_id") ?: return errorJson("job_id required")
        val job = cronStore().jobs().firstOrNull { it.id == jobId }
            ?: return errorJson("no such job: $jobId")
        val resumed = job.copy(enabled = true)
        cronStore().upsert(resumed)
        cronScheduler().schedule(resumed)
        return successJson("resumed job $jobId")
    }

    private suspend fun triggerCronJob(args: JsonObject): JsonObject {
        val jobId = strArg(args, "job_id") ?: return errorJson("job_id required")
        if (cronStore().jobs().none { it.id == jobId }) {
            return errorJson("no such job: $jobId")
        }
        cronScheduler().triggerNow(jobId)
        return successJson("triggered job $jobId")
    }

    private suspend fun switchAssistant(args: JsonObject): JsonObject {
        val id = parseUuid(args, "assistant_id") ?: return errorJson("assistant_id required")
        if (settings.assistants.none { it.id == id }) {
            return errorJson("assistant_id not found: $id")
        }
        settingsStore.update { old -> old.copy(assistantId = id) }
        return successJson("switched assistant to $id")
    }

    private suspend fun setChatModel(args: JsonObject): JsonObject {
        val id = parseUuid(args, "model_id") ?: return errorJson("model_id required")
        settingsStore.update { old -> old.copy(chatModelId = id) }
        return successJson("chat model set to $id")
    }

    private suspend fun setFastModel(args: JsonObject): JsonObject {
        val id = parseUuid(args, "model_id") ?: return errorJson("model_id required")
        settingsStore.update { old -> old.copy(fastModelId = id) }
        return successJson("fast model set to $id")
    }

    private suspend fun updateAssistant(args: JsonObject): JsonObject {
        val id = parseUuid(args, "assistant_id") ?: return errorJson("assistant_id required")
        val target = settings.assistants.firstOrNull { it.id == id }
            ?: return errorJson("assistant_id not found: $id")
        val mutable = args.toMutableMap()
        mutable.remove("assistant_id")
        if (mutable.isEmpty()) return errorJson("no fields to update")

        var updated = target
        mutable.forEach { (key, value) ->
            updated = updated.applyField(key, value) ?: return errorJson("unsupported field: $key")
        }
        settingsStore.update { old ->
            old.copy(
                assistants = old.assistants.map { if (it.id == id) updated else it }
            )
        }
        return successJson("assistant $id updated")
    }

    private fun Assistant.applyField(
        key: String,
        value: kotlinx.serialization.json.JsonElement,
    ): Assistant? {
        val content = value.toString()
        return when (key) {
            "name" -> copy(name = content.trim('"'))
            "system_prompt" -> copy(systemPrompt = content.trim('"'))
            "enable_web_search" -> copy(enableWebSearch = content.toBooleanStrictOrNull() ?: return null)
            "enable_memory" -> copy(enableMemory = content.toBooleanStrictOrNull() ?: return null)
            "use_global_memory" -> copy(useGlobalMemory = content.toBooleanStrictOrNull() ?: return null)
            "enable_recent_chats_reference" ->
                copy(enableRecentChatsReference = content.toBooleanStrictOrNull() ?: return null)
            "stream_output" -> copy(streamOutput = content.toBooleanStrictOrNull() ?: return null)
            "temperature" -> copy(temperature = content.toFloatOrNull() ?: return null)
            "top_p" -> copy(topP = content.toFloatOrNull() ?: return null)
            "context_message_limit" -> copy(contextMessageLimit = content.toIntOrNull() ?: return null)
            "max_tokens" -> copy(maxTokens = content.toIntOrNull() ?: return null)
            else -> null
        }
    }

    private suspend fun toggleProviderEnabled(args: JsonObject): JsonObject {
        val id = parseUuid(args, "provider_id") ?: return errorJson("provider_id required")
        val enabled = args["enabled"]?.toString()?.toBooleanStrictOrNull()
            ?: return errorJson("enabled (boolean) required")
        if (settings.providers.none { it.id == id }) {
            return errorJson("provider_id not found: $id")
        }
        settingsStore.update { old ->
            old.copy(
                providers = old.providers.map { p ->
                    if (p.id == id) p.copyProvider(enabled = enabled) else p
                }
            )
        }
        return successJson("provider $id enabled=$enabled")
    }

    private suspend fun renameProvider(args: JsonObject): JsonObject {
        val id = parseUuid(args, "provider_id") ?: return errorJson("provider_id required")
        val name = args["name"]?.toString()?.trim('"')?.takeIf { it.isNotBlank() }
            ?: return errorJson("name required")
        if (settings.providers.none { it.id == id }) {
            return errorJson("provider_id not found: $id")
        }
        settingsStore.update { old ->
            old.copy(
                providers = old.providers.map { p ->
                    if (p.id == id) p.copyProvider(name = name) else p
                }
            )
        }
        return successJson("provider $id renamed to $name")
    }

    private suspend fun toggleMcpServer(args: JsonObject): JsonObject {
        val id = parseUuid(args, "server_id") ?: return errorJson("server_id required")
        val enable = args["enable"]?.toString()?.toBooleanStrictOrNull()
            ?: return errorJson("enable (boolean) required")
        if (settings.mcpServers.none { it.id == id }) {
            return errorJson("server_id not found: $id")
        }
        settingsStore.update { old ->
            old.copy(
                mcpServers = old.mcpServers.map { m ->
                    if (m.id == id) m.clone(commonOptions = m.commonOptions.copy(enable = enable)) else m
                }
            )
        }
        return successJson("mcp server $id enable=$enable")
    }

    private suspend fun setWebServer(args: JsonObject): JsonObject {
        val enabled = args["enabled"]?.toString()?.toBooleanStrictOrNull()
        val port = args["port"]?.toString()?.toIntOrNull()
        val jwt = args["jwt_enabled"]?.toString()?.toBooleanStrictOrNull()
        val localhostOnly = args["localhost_only"]?.toString()?.toBooleanStrictOrNull()
        if (enabled == null && port == null && jwt == null && localhostOnly == null) {
            return errorJson("at least one of enabled/port/jwt_enabled/localhost_only required")
        }
        val wasEnabled = settings.webServerEnabled
        settingsStore.update { old ->
            old.copy(
                webServerEnabled = enabled ?: old.webServerEnabled,
                webServerPort = port ?: old.webServerPort,
                webServerJwtEnabled = jwt ?: old.webServerJwtEnabled,
                webServerLocalhostOnly = localhostOnly ?: old.webServerLocalhostOnly,
            )
        }
        return successJson("web server updated (was enabled=$wasEnabled)")
    }

    // ==== rhAppControlTheme: 主题 / 动态色 / 显示设置实现 ====

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

    @OptIn(ExperimentalUuidApi::class)
    private fun parseUuid(args: JsonObject, key: String): Uuid? {
        val raw = args[key]?.toString()?.trim('"') ?: return null
        return runCatching { Uuid.parse(raw) }.getOrNull()
    }

    private fun errorJson(detail: String): JsonObject = buildJsonObject {
        put("error", "invalid_argument")
        put("detail", detail)
    }

    private fun successJson(detail: String): JsonObject = buildJsonObject {
        put("success", true)
        put("detail", detail)
    }
}

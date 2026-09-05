package me.rerere.rikkahub.data.ai.tools.appcontrol

import kotlinx.serialization.json.JsonObject
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
 * AppControl gateway (L0-L3 merged into one APK).
 *
 * Read side returns a redacted snapshot of the app settings: never exposes apiKey,
 * tokens, passwords, or headers. Write side is a whitelist; every write tool is
 * marked needsApproval = true by the tool factory in AppControlTools.kt.
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
                        add(kotlinx.serialization.json.buildJsonObject {
                            put("name", svc.name)
                        })
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
                add(kotlinx.serialization.json.buildJsonObject {
                    put("id", m.id.toString())
                    put("model_id", m.modelId)
                    put("display_name", m.displayName)
                    put("context_length", m.contextLength ?: 0)
                })
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
        "toggle_mcp_server" -> toggleMcpServer(args)
        "set_web_server" -> setWebServer(args)
        else -> buildJsonObject {
            put("error", "unknown_action")
            put(
                "detail",
                "action must be one of: switch_assistant, set_chat_model, set_fast_model, " +
                    "update_assistant, toggle_provider_enabled, toggle_mcp_server, set_web_server",
            )
        }
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

    private fun Assistant.applyField(key: String, value: kotlinx.serialization.json.JsonElement): Assistant? {
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
        val current = settings
        settingsStore.update { old ->
            old.copy(
                webServerEnabled = enabled ?: old.webServerEnabled,
                webServerPort = port ?: old.webServerPort,
                webServerJwtEnabled = jwt ?: old.webServerJwtEnabled,
                webServerLocalhostOnly = localhostOnly ?: old.webServerLocalhostOnly,
            )
        }
        return successJson("web server updated (was enabled=${current.webServerEnabled})")
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
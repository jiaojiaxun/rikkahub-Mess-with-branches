package me.rerere.rikkahub.data.ai.tools.appcontrol

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.put
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.Tool
import me.rerere.ai.ui.UIMessagePart
import me.rerere.rikkahub.data.datastore.SettingsStore

/**
 * AppControl gateway tools, ported from feat/app-control-v2.
 *
 * - rikkahub_capabilities: read-only; describes what the gateway can do.
 * - rikkahub_query: read-only; redacted app settings snapshot (no secrets).
 * - rikkahub_apply_change: write; whitelist actions, every call needsApproval.
 *
 * All writes funnel through [AppControlService.applyChange], so the whitelist is
 * the single source of truth for what the model may change on the device.
 */
fun createAppControlTools(
    settingsStore: SettingsStore,
): List<Tool> {
    val service = AppControlService(settingsStore)

    val capabilitiesTool = Tool(
        name = "rikkahub_capabilities",
        description = """
            List the capabilities of the RikkaHub app-control gateway. Read side
            (rikkahub_query) exposes a redacted snapshot of app settings; write side
            (rikkahub_apply_change) supports a whitelist of actions and every write requires
            user approval. Prefer this tool when the app-control surface is unknown.
        """.trimIndent().replace("\n", " "),
        parameters = {
            InputSchema.Obj(
                properties = buildJsonObject { },
                required = emptyList()
            )
        },
        execute = {
            listOf(
                UIMessagePart.Text(
                    buildJsonObject {
                        put("gateway", "rikkahub_app_control")
                        put("version", 3)
                        put("read_tools", kotlinx.serialization.json.buildJsonArray {
                            add(JsonPrimitive("rikkahub_capabilities"))
                            add(JsonPrimitive("rikkahub_query"))
                        })
                        put("write_tool", "rikkahub_apply_change (whitelist; needsApproval=true)")
                        put("query_domains", kotlinx.serialization.json.buildJsonArray {
                            add(JsonPrimitive("app_state"))
                            add(JsonPrimitive("providers"))
                            add(JsonPrimitive("assistants"))
                            add(JsonPrimitive("mcp_servers"))
                        })
                        put("write_actions", kotlinx.serialization.json.buildJsonArray {
                            add(JsonPrimitive("switch_assistant"))
                            add(JsonPrimitive("set_chat_model"))
                            add(JsonPrimitive("set_fast_model"))
                            add(JsonPrimitive("update_assistant"))
                            add(JsonPrimitive("toggle_provider_enabled"))
                            add(JsonPrimitive("rename_provider"))
                            add(JsonPrimitive("toggle_mcp_server"))
                            add(JsonPrimitive("set_web_server"))
                        })
                    }.toString()
                )
            )
        }
    )

    val queryTool = Tool(
        name = "rikkahub_query",
        description = """
            Query the RikkaHub app state. Returns a redacted snapshot: assistant id,
            chat/fast model ids, web server settings, search service selection, providers
            (with their models, no secrets), assistants, and MCP servers. Never returns API
            keys, tokens, passwords or custom headers. Read-only.
        """.trimIndent().replace("\n", " "),
        parameters = {
            InputSchema.Obj(
                properties = buildJsonObject { },
                required = emptyList()
            )
        },
        execute = {
            listOf(
                UIMessagePart.Text(
                    service.queryAppState().toString()
                )
            )
        }
    )

    val applyChangeTool = Tool(
        name = "rikkahub_apply_change",
        description = """
            Apply a whitelisted change to RikkaHub settings. Requires user approval on every call.
            Actions:
            - switch_assistant {assistant_id}
            - set_chat_model {model_id}
            - set_fast_model {model_id}
            - update_assistant {assistant_id, name?, system_prompt?, enable_web_search?,
              enable_memory?, use_global_memory?, enable_recent_chats_reference?,
              stream_output?, temperature?, top_p?, context_message_limit?, max_tokens?}
            - toggle_provider_enabled {provider_id, enabled}
            - rename_provider {provider_id, name}
            - toggle_mcp_server {server_id, enable}
            - set_web_server {enabled?, port?, jwt_enabled?, localhost_only?}
            All ids are UUIDs. Query first with rikkahub_query to get valid ids.
        """.trimIndent().replace("\n", " "),
        parameters = {
            InputSchema.Obj(
                properties = buildJsonObject {
                    put("action", buildJsonObject {
                        put("type", "string")
                        put("description", "Whitelisted action name (see tool description)")
                    })
                    put("args", buildJsonObject {
                        put("type", "object")
                        put("description", "Action arguments, e.g. {\"assistant_id\": \"...\"}")
                    })
                },
                required = listOf("action")
            )
        },
        needsApproval = { true },
        execute = { input ->
            val args = input as? JsonObject
                ?: return@Tool listOf(
                    UIMessagePart.Text(
                        buildJsonObject {
                            put("error", "invalid_argument")
                            put("detail", "arguments must be an object")
                        }.toString()
                    )
                )
            val action = (args["action"] as? JsonPrimitive)?.contentOrNull
                ?: return@Tool listOf(
                    UIMessagePart.Text(
                        buildJsonObject {
                            put("error", "invalid_argument")
                            put("detail", "action is required")
                        }.toString()
                    )
                )
            val actionArgs = args["args"] as? JsonObject ?: buildJsonObject { }
            listOf(
                UIMessagePart.Text(
                    service.applyChange(action, actionArgs).toString()
                )
            )
        }
    )

    return listOf(capabilitiesTool, queryTool, applyChangeTool)
}

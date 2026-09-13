package me.rerere.rikkahub.data.ai.tools.local

import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.Tool
import me.rerere.ai.ui.UIMessagePart
import me.rerere.rikkahub.data.datastore.SettingsStore
import java.io.File
import java.security.MessageDigest

/**
 * Chat UI dual-mode gateway: lets the model author an HTML "skin" that the chat page
 * renders as a full-bleed layer under (or instead of) the native message list.
 *
 * Design notes
 * - The HTML is written to `filesDir/chat-html/<sha>.html` and the active skin id +
 *   toggle state are kept in DataStore so the skin survives process death and can be
 * re-entered from any chat conversation (it is a global chat-layer, not per-conversation).
 * - Writes require user approval (needsApproval = true) because a skin can contain
 *   arbitrary script; the approval card shows a short reason field the model fills.
 * - The bridge contract is documented in [ChatHtmlBridge] (native side) and mirrored
 *   in the tool description so the model knows how to talk back.
 */
fun createChatUiTools(
    settingsStore: SettingsStore,
): List<Tool> {
    val skinsDir = File(settingsStore.context.filesDir, "chat-html").apply { mkdirs() }

    fun skinFile(id: String): File = File(skinsDir, "$id.html")

    fun listSkins(): List<String> = skinsDir.listFiles { f -> f.isFile && f.name.endsWith(".html") }
        ?.map { it.name.removeSuffix(".html") }
        ?.sorted()
        ?: emptyList()

    val writeTool = Tool(
        name = "chat_ui_write",
        description = """
            Author or replace the HTML skin used by the chat page in HTML mode. The HTML is
            rendered in a WebView layered under the native input bar, so background, chat
            bubbles, buttons and floating widgets (e.g. a character-info ball) can be styled
            freely while normal chat features (send text, attach files) keep working.
            Bridge contract: call AndroidChatBridge.postMessage(json-string) with
            {"type":"send_message","text":"..."} to send a chat message,
            {"type":"button_action","action":"...","payload":{...}} to report a button tap,
            {"type":"request_exit"} to leave HTML mode. The native side pushes
            {"type":"new_message","message":{...}} and {"type":"generation_done"} events via
            window.onNativeEvent(json-string). Every write needs user approval.
        """.trimIndent().replace("\n", " "),
        parameters = {
            InputSchema.Obj(
                properties = buildJsonObject {
                    put(
                        "html",
                        buildJsonObject {
                            put("type", "string")
                            put("description", "Full HTML document for the chat skin. Must be self-contained (inline CSS/JS, no external assets).")
                        }
                    )
                    put(
                        "skin_id",
                        buildJsonObject {
                            put("type", "string")
                            put("description", "Optional stable id for this skin (alphanumeric/dash). Defaults to a hash of the html.")
                        }
                    )
                },
                required = listOf("html")
            )
        },
        needsApproval = { true },
        execute = { input ->
            val html = input["html"]?.let { v ->
                (v as? kotlinx.serialization.json.JsonPrimitive)?.content
            } ?: return@Tool listOf(
                UIMessagePart.Text("""{"error":"invalid_argument","detail":"html is required"}""")
            )
            val requestedId = input["skin_id"]?.let { v ->
                (v as? kotlinx.serialization.json.JsonPrimitive)?.content
            }?.takeIf { it.matches(Regex("[A-Za-z0-9_-]{1,64}")) }
            val id = requestedId ?: "skin-" + MessageDigest.getInstance("SHA-256")
                .digest(html.toByteArray(Charsets.UTF_8))
                .take(8)
                .joinToString("") { "%02x".format(it) }
            // Defensive: forbid <script src>, external URLs and filesystem references so the
            // skin stays self-contained and cannot pull third-party payloads at runtime.
            val violations = buildList {
                if (Regex("""<script[^>]*\bsrc\s*=""").containsMatchIn(html)) add("script-src")
                if (Regex("""<link[^>]*\brel\s*=\s*["']?stylesheet""").containsMatchIn(html)) add("external-stylesheet")
                if (Regex("""\bfile://""").containsMatchIn(html)) add("file-url")
            }
            if (violations.isNotEmpty()) {
                return@Tool listOf(
                    UIMessagePart.Text(
                        buildJsonObject {
                            put("error", "policy_violation")
                            put("detail", "html must be self-contained: $violations")
                        }.toString()
                    )
                )
            }
            val f = skinFile(id)
            f.writeText(html)
            settingsStore.update { old ->
                old.copy(chatHtmlSkinId = id, chatHtmlModeEnabled = true)
            }
            listOf(
                UIMessagePart.Text(
                    buildJsonObject {
                        put("ok", true)
                        put("skin_id", id)
                        put("mode", "html")
                        put("path", f.absolutePath)
                    }.toString()
                )
            )
        }
    )

    val setModeTool = Tool(
        name = "chat_ui_set_mode",
        description = """
            Switch the chat page between native mode (default) and HTML mode (AI-authored
            skin). Switching to html requires an existing skin id; switching to native keeps
            the skin files on disk. Needs user approval.
        """.trimIndent().replace("\n", " "),
        parameters = {
            InputSchema.Obj(
                properties = buildJsonObject {
                    put(
                        "mode",
                        buildJsonObject {
                            put("type", "string")
                            put("enum", kotlinx.serialization.json.buildJsonArray {
                                add(kotlinx.serialization.json.JsonPrimitive("native"))
                                add(kotlinx.serialization.json.JsonPrimitive("html"))
                            })
                            put("description", "native or html")
                        }
                    )
                    put(
                        "skin_id",
                        buildJsonObject {
                            put("type", "string")
                            put("description", "Skin id to activate (required when mode=html).")
                        }
                    )
                },
                needsApproval = { true },
                required = listOf("mode")
            )
        },
        needsApproval = { true },
        execute = { input ->
            val mode = input["mode"]?.let { v ->
                (v as? kotlinx.serialization.json.JsonPrimitive)?.content
            }
            when (mode) {
                "native" -> {
                    settingsStore.update { old -> old.copy(chatHtmlModeEnabled = false) }
                    listOf(UIMessagePart.Text("""{"ok":true,"mode":"native"}"""))
                }
                "chat" -> {
                    settingsStore.update { old -> old.copy(chatHtmlModeEnabled = false) }
                    listOf(UIMessagePart.Text("""{"ok":true,"mode":"native"}"""))
                }
                "html" -> {
                    val skinId = input["skin_id"]?.let { v ->
                        (v as? kotlinx.serialization.json.JsonPrimitive)?.content
                    }?.takeIf { it.matches(Regex("[A-Za-z0-9_-]{1,64}")) }
                        ?: return@Tool listOf(
                            UIMessagePart.Text("""{"error":"invalid_argument","detail":"skin_id is required for html mode"}""")
                        )
                    if (!skinFile(skinId).exists()) {
                        return@Tool listOf(
                            UIMessagePart.Text("""{"error":"not_found","detail":"skin $skinId does not exist; write one first with chat_ui_write"}""")
                        )
                    }
                    settingsStore.update { old ->
                        old.copy(chatHtmlSkinId = skinId, chatHtmlModeEnabled = true)
                    }
                    listOf(UIMessagePart.Text("""{"ok":true,"mode":"html","skin_id":"$skinId"}"""))
                }
                else -> listOf(UIMessagePart.Text("""{"error":"invalid_argument","detail":"mode must be native or html"}"""))
            }
        }
    )

    val listTool = Tool(
        name = "chat_ui_list_skins",
        description = "List available chat HTML skins with their ids and sizes. Read-only.",
        parameters = {
            InputObjectParams()
        },
        execute = {
            val skins = listSkins()
            val arr = kotlinx.serialization.json.buildJsonArray {
                skins.forEach { id ->
                    add(buildJsonObject {
                        put("skin_id", id)
                        put("bytes", skinFile(id).length())
                        put("last_modified", skinFile(id).lastModified())
                    })
                }
            }
            listOf(UIMessagePart.Text(buildJsonObject {
                put("skins", arr)
                put("active_skin", settingsStore.settingsFlow.value.chatHtmlSkinId)
                put("html_mode_enabled", settingsStore.settingsFlow.value.chatHtmlModeEnabled)
            }.toString()))
        }
    )

    val deleteTool = Tool(
        skin_id_placeholder = null,
        name = "chat_ui_delete_skin",
        description = """
            Delete a chat HTML skin by id. Fails when the skin is active. Needs user approval.
        """.trimIndent().replace("\n", " "),
        parameters = {
            InputSchema.Obj(
                properties = buildJsonObject {
                    put("skin_id", buildJsonObject {
                        put("type", "string")
                        put("description", "Skin id to delete.")
                    })
                },
                required = listOf("skin_id")
            )
        },
        needsApproval = { true },
        execute = { input ->
            val skinId = input["skin_id"]?.let { v ->
                (v as? kotlinx.serialization.json.JsonPrimitive)?.content
            }?.takeIf { it.matches(Regex("[A-Za-z0-9_-]{1,64}")) }
                ?: return@Tool listOf(UIMessagePart.Text("""{"error":"invalid_argument","detail":"skin_id is required"}"""))
            if (settingsStore.settingsFlow.value.chatHtmlSkinId == skinId && settingsStore.settingsFlow.value.chatHtmlModeEnabled) {
                return@Tool listOf(UIMessagePart.Text("""{"error":"conflict","detail":"skin is active; switch to native first"}"""))
            }
            val deleted = skinFile(skinId).delete()
            listOf(UIMessagePart.Text(buildJsonObject {
                put("ok", deleted)
                put("skin_id", skinId)
            }.toString()))
        }
    )

    return listOf(writeTool, setModeTool, listTool, deleteTool)
}

private fun InputObjectParams(): InputSchema.Obj {
    return InputSchema.Obj(
        properties = buildJsonObject { },
        required = emptyList()
    )
}

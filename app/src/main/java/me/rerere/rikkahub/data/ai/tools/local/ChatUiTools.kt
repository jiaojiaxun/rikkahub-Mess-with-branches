package me.rerere.rikkahub.data.ai.tools.local

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.put
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.Tool
import me.rerere.ai.ui.UIMessagePart
import java.security.MessageDigest

/**
 * Chat UI dual-mode gateway tools (v4, global singleton store).
 *
 * Lets the model author an HTML "skin" that the chat page renders as a full-bleed
 * layer under the native input bar. The skin state lives in its own DataStore behind
 * [ChatHtmlSkinGlobal] (initialised at app start), so neither LocalTools' constructor
 * nor the DI graph needs a new parameter — a late-init global is the same pattern
 * AgentWorkspace already uses.
 *
 * Security notes
 * - Every write tool is needsApproval = true; the approval card surfaces the model's
 *   `reason` argument so the user sees WHY the skin should change before approving.
 * - The HTML must be self-contained: <script src>, external stylesheets, @import and
 *   file:// references are rejected by [policyViolations] before the file is written.
 * - Files live under filesDir/chat-html and are rendered via loadDataWithBaseURL with
 *   a synthetic https base URL, so the WebView cannot reach the real filesystem
 *   through relative paths.
 */
fun createChatUiTools(): List<Tool> {
    val store = ChatHtmlSkinGlobal.store

    /** Strict content-or-null that never throws on non-string primitives. */
    fun str(input: JsonObject, key: String): String? =
        (input[key] as? JsonPrimitive)?.contentOrNull

    fun error(detail: String, code: String = "invalid_argument") =
        UIMessagePart.Text(
            buildJsonObject {
                put("error", code)
                put("detail", detail)
            }.toString()
        )

    /**
     * Reject skins that reference external resources. Keeps the skin an inert
     * artifact reviewable in one file and blocks third-party payloads at render
     * time. Inline <script> (no src), inline <style> and https:// images allowed.
     */
    fun policyViolations(html: String): List<String> = buildList {
        if (Regex("""<script[^>]*\bsrc\s*=""").containsMatchIn(html)) add("script-src")
        if (Regex("""<link[^>]*\brel\s*=\s*["']?stylesheet""").containsMatchIn(html)) add("external-stylesheet")
        if (Regex("""@import""").containsMatchIn(html)) add("css-import")
        if (Regex("""\bfile://""").containsMatchIn(html)) add("file-url")
    }

    val writeTool = Tool(
        name = "chat_ui_write",
        description = """
            Author or replace the HTML skin used by the chat page in HTML mode. The skin is
            rendered full-screen above the chat background and below the native input bar, so
            background, chat bubbles, buttons and floating widgets (e.g. a character-info
            ball) can be styled freely while chat features (send text, attach files) keep
            working. The skin must be one self-contained HTML file: no <script src>, no
            external stylesheets, no @import, no file:// references; inline CSS/JS and
            https images are fine. Bridge contract: AndroidChatBridge.postMessage(json) with
            {"type":"send_message","text":"..."} sends a chat message;
            {"type":"button_action","action":"...","payload":{...}} reports a widget tap;
            {"type":"request_exit"} leaves HTML mode. Native pushes events via
            window.onNativeEvent(json) with types new_message / generation_done /
            html_mode_changed. Writes need user approval; explain the design in `reason`.
        """.trimIndent().replace("\n", " "),
        parameters = {
            InputSchema.Obj(
                properties = buildJsonObject {
                    put("html", buildJsonObject {
                        put("type", "string")
                        put("description", "Complete self-contained HTML document for the chat skin.")
                    })
                    put("skin_id", buildJsonObject {
                        put("type", "string")
                        put("description", "Optional stable id (A-Za-z0-9_- , max 64 chars). Default: hash of the html.")
                    })
                    put("reason", buildJsonObject {
                        put("type", "string")
                        put("description", "Short user-facing reason shown on the approval card.")
                    })
                },
                required = listOf("html")
            )
        },
        needsApproval = { true },
        execute = { input ->
            val args = input as? JsonObject
                ?: return@Tool listOf(error("arguments must be an object"))
            val html = str(args, "html")?.takeIf { it.isNotBlank() }
                ?: return@Tool listOf(error("html is required"))
            if (html.length > 512_000) {
                return@Tool listOf(error("html exceeds 512KB limit", "policy_violation"))
            }
            val requestedId = str(args, "skin_id")?.takeIf { it.matches(Regex("[A-Za-z0-9_-]{1,64}")) }
            val id = requestedId ?: "skin-" + MessageDigest.getInstance("SHA-256")
                .digest(html.toByteArray(Charsets.UTF_8))
                .take(8)
                .joinToString("") { "%02x".format(it) }
            val violations = policyViolations(html)
            if (violations.isNotEmpty()) {
                return@Tool listOf(error("html must be self-contained: $violations", "policy_violation"))
            }
            val f = store.skinFile(id)
            f.writeText(html)
            store.setActive(id)
            listOf(
                UIMessagePart.Text(
                    buildJsonObject {
                        put("ok", true)
                        put("skin_id", id)
                        put("mode", "html")
                        put("bytes", f.length())
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
            skin). mode=html requires skin_id of an existing skin. Skin files stay on disk
            when switching to native. Needs user approval.
        """.trimIndent().replace("\n", " "),
        parameters = {
            InputSchema.Obj(
                properties = buildJsonObject {
                    put("mode", buildJsonObject {
                        put("type", "string")
                        put("description", "native or html")
                    })
                    put("skin_id", buildJsonObject {
                        put("type", "string")
                        put("description", "Skin id to activate (required when mode=html).")
                    })
                    put("reason", buildJsonObject {
                        put("type", "string")
                        put("description", "Short reason shown on the approval card.")
                    })
                },
                required = listOf("mode")
            )
        },
        needsApproval = { true },
        execute = { input ->
            val args = input as? JsonObject
                ?: return@Tool listOf(error("arguments must be an object"))
            when (val mode = str(args, "mode")) {
                "native" -> {
                    store.setMode(false)
                    listOf(
                        UIMessagePart.Text(
                            buildJsonObject {
                                put("ok", true)
                                put("mode", "native")
                            }.toString()
                        )
                    )
                }
                "html" -> {
                    val skinId = str(args, "skin_id")?.takeIf { it.matches(Regex("[A-Za-z0-9_-]{1,64}")) }
                        ?: return@Tool listOf(error("skin_id is required for html mode"))
                    if (!store.skinFile(skinId).exists()) {
                        return@Tool listOf(
                            error("skin $skinId does not exist; write it first with chat_ui_write", "not_found")
                        )
                    }
                    store.setActive(skinId)
                    listOf(
                        UIMessagePart.Text(
                            buildJsonObject {
                                put("ok", true)
                                put("mode", "html")
                                put("skin_id", skinId)
                            }.toString()
                        )
                    )
                }
                else -> listOf(error("mode must be native or html (got: $mode)"))
            }
        }
    )

    val listTool = Tool(
        name = "chat_ui_list_skins",
        description = "List available chat HTML skins (ids, sizes, active state). Read-only.",
        parameters = { null },
        execute = {
            val arr = buildJsonArray {
                store.listSkinIds().forEach { id ->
                    add(
                        buildJsonObject {
                            put("skin_id", id)
                            put("bytes", store.skinFile(id).length())
                            put("last_modified", store.skinFile(id).lastModified())
                        }
                    )
                }
            }
            val state = store.stateFlow.value
            listOf(
                UIMessagePart.Text(
                    buildJsonObject {
                        put("skins", arr)
                        put("active_skin", state.activeSkinId)
                        put("html_mode_enabled", state.htmlModeEnabled)
                    }.toString()
                )
            )
        }
    )

    val deleteTool = Tool(
        name = "chat_ui_delete_skin",
        description = """
            Delete a chat HTML skin by id. Fails when the skin is active (switch to native
            first). Needs user approval.
        """.trimIndent().replace("\n", " "),
        parameters = {
            InputSchema.Obj(
                properties = buildJsonObject {
                    put("skin_id", buildJsonObject {
                        put("type", "string")
                        put("description", "Skin id to delete.")
                    })
                    put("reason", buildJsonObject {
                        put("type", "string")
                        put("description", "Short reason shown on the approval card.")
                    })
                },
                required = listOf("skin_id")
            )
        },
        needsApproval = { true },
        execute = { input ->
            val args = input as? JsonObject
                ?: return@Tool listOf(error("arguments must be an object"))
            val skinId = str(args, "skin_id")?.takeIf { it.matches(Regex("[A-Za-z0-9_-]{1,64}")) }
                ?: return@Tool listOf(error("skin_id is required"))
            val state = store.stateFlow.value
            if (state.activeSkinId == skinId && state.htmlModeEnabled) {
                return@Tool listOf(error("skin is active; switch to native first", "conflict"))
            }
            val deleted = store.skinFile(skinId).delete()
            if (deleted && state.activeSkinId == skinId) {
                store.setMode(false)
            }
            listOf(
                UIMessagePart.Text(
                    buildJsonObject {
                        put("ok", deleted)
                        put("skin_id", skinId)
                    }.toString()
                )
            )
        }
    )

    return listOf(writeTool, setModeTool, listTool, deleteTool)
}

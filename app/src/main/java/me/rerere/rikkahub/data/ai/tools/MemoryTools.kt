package me.rerere.rikkahub.data.ai.tools

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.add
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.Tool
import me.rerere.ai.ui.UIMessagePart
import me.rerere.rikkahub.data.model.AssistantMemory
import me.rerere.rikkahub.utils.toLocalString
import java.time.LocalDate

// rhShortMem + rhMemPolish240: 短期记忆与长期记忆使用完全独立的两套工具介绍, 只向模型暴露当前开启的那一种
fun buildMemoryTools(
    json: Json,
    sessionScoped: Boolean = false,
    onCreation: suspend (String) -> AssistantMemory,
    onUpdate: suspend (Int, String) -> AssistantMemory,
    onDelete: suspend (Int) -> Unit
): List<Tool> = listOf(
    Tool(
        name = "memory_tool",
        description = if (sessionScoped) {
            """
                [SHORT-TERM MEMORY — CURRENT CONVERSATION ONLY]
                The memory tool stores short-term context and notes private to THIS conversation only.
                Use `action` to control the operation: `create` (add), `edit` (update), `delete` (remove).
                - No relevant record: `create` + `content`
                - Existing relevant record: `edit` + `id` + `content`
                - Outdated/irrelevant record: `delete` + `id`
                Short-term memories automatically appear in the <memories> tag within THIS conversation only, and are NEVER shared with other conversations.
                You may store: current session goals, temporary constraints, progress notes, or roleplay state specific to this chat.
                Do not show memory content directly in the conversation unless the user explicitly asks.
                Today is ${LocalDate.now().toLocalString(true)}.
                Similar memories should be merged; prefer updating existing records.

                Examples:
                {"action":"create","content":"In this conversation, user wants concise code-only answers."}
                {"action":"edit","id":12,"content":"Current session task updated to refactoring the backup dialog."}
                {"action":"delete","id":7}
            """.trimIndent()
        } else {
            """
                [LONG-TERM MEMORY — SHARED ACROSS CONVERSATIONS]
                The memory tool stores long-term information shared across all conversations of this assistant.
                Use `action` to control the operation: `create` (add), `edit` (update), `delete` (remove).
                - No relevant record: `create` + `content`
                - Existing relevant record: `edit` + `id` + `content`
                - Outdated/irrelevant record: `delete` + `id`
                Long-term memories automatically appear in the <memories> tag in all future conversations.
                Do not store sensitive information (e.g., ethnicity, religion, sexual orientation, political views, sex life, criminal records).
                You may store: preferred name, preferences, plans, work-related notes, chat style preferences, first chat time, etc.
                Do not show memory content directly in the conversation unless the user explicitly asks.
                Today is ${LocalDate.now().toLocalString(true)}.
                Similar memories should be merged; prefer updating existing records.

                Examples:
                {"action":"create","content":"User prefers brief replies and is more active on weekends."}
                {"action":"edit","id":12,"content":"User’s preferred name updated to “A-Xing”, prefers Chinese replies."}
                {"action":"delete","id":7}
            """.trimIndent()
        },
        parameters = {
            InputSchema.Obj(
                properties = buildJsonObject {
                    put("action", buildJsonObject {
                        put("type", "string")
                        put(
                            "enum",
                            buildJsonArray {
                                add("create")
                                add("edit")
                                add("delete")
                            }
                        )
                        put("description", "Operation to perform: create, edit, or delete")
                    })
                    put("id", buildJsonObject {
                        put("type", "integer")
                        put("description", "The id of the memory record (required for edit/delete)")
                    })
                    put("content", buildJsonObject {
                        put("type", "string")
                        put("description", "The content of the memory record (required for create/edit)")
                    })
                },
                required = listOf("action")
            )
        },
        execute = {
            val params = it.jsonObject
            val action = params["action"]?.jsonPrimitive?.contentOrNull ?: error("action is required")
            val payload = when (action) {
                "create" -> {
                    val content = params["content"]?.jsonPrimitive?.contentOrNull ?: error("content is required")
                    json.encodeToJsonElement(AssistantMemory.serializer(), onCreation(content))
                }

                "edit" -> {
                    val id = params["id"]?.jsonPrimitive?.intOrNull ?: error("id is required")
                    val content = params["content"]?.jsonPrimitive?.contentOrNull ?: error("content is required")
                    json.encodeToJsonElement(AssistantMemory.serializer(), onUpdate(id, content))
                }

                "delete" -> {
                    val id = params["id"]?.jsonPrimitive?.intOrNull ?: error("id is required")
                    onDelete(id)
                    buildJsonObject {
                        put("success", true)
                        put("id", id)
                        put("scope", if (sessionScoped) "short" else "long")
                    }
                }

                else -> error("unknown action: $action, must be one of [create, edit, delete]")
            }
            listOf(UIMessagePart.Text(payload.toString()))
        }
    )
)

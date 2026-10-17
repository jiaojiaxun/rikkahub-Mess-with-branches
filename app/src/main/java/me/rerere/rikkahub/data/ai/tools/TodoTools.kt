package me.rerere.rikkahub.data.ai.tools

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.add
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.Tool
import me.rerere.ai.ui.UIMessagePart

/** rhPlanBar228: todo_write 工具名(文档5.1) */
const val TODO_TOOL_NAME = "todo_write"

private val TODO_STATUSES = listOf("pending", "in_progress", "completed")

/**
 * rhPlanBar228: 计划清单工具(移植自 YuiHub 的 todo_write,文档5.1)。
 * 无副作用:不写库、不改任何全局状态;只做校验与归一化,把清单 JSON 原样返回。
 * UI 从消息历史里取「最后一次已执行的调用」派生计划栏,持久化/崩溃恢复全部免费。
 */
fun createTodoTool(): Tool = Tool(
    name = TODO_TOOL_NAME,
    description = """
        Create or update the task plan for the current work. Use it to break a multi-step
        task into an explicit checklist and keep it current as you make progress.

        Rules:
        - Call it BEFORE starting a multi-step task (3+ distinct steps), and again every
          time a step's status changes. Skip it for simple single-step requests.
        - Always pass the FULL list (not just the changed items); previously sent items
          must be repeated.
        - Exactly one item may be "in_progress" at a time; mark an item "completed" only
          when it is truly done (tests passing, file written, etc.).
        - Keep items short, actionable, and starting with a verb (e.g. "Add DB migration").
        - Do not mention this tool or the plan bookkeeping in your final answer to the
          user; the UI already shows the checklist.
    """.trimIndent(),
    parameters = {
        InputSchema.Obj(
            properties = buildJsonObject {
                put("todos", buildJsonObject {
                    put("type", "array")
                    put("description", "The complete todo list; replaces any previous list")
                    put("items", buildJsonObject {
                        put("type", "object")
                        put("properties", buildJsonObject {
                            put("content", buildJsonObject {
                                put("type", "string")
                                put("description", "Short imperative description of the step")
                            })
                            put("status", buildJsonObject {
                                put("type", "string")
                                put("description", "pending | in_progress | completed")
                            })
                        })
                        put("required", buildJsonArray { add("content"); add("status") })
                    })
                })
            },
            required = listOf("todos"),
        )
    },
    execute = { args ->
        val todos = args.jsonObject["todos"] as? JsonArray
            ?: error("todos is required and must be an array")
        val normalized = todos.mapIndexed { index, element ->
            val item = element.jsonObject
            val content = item["content"]?.jsonPrimitive?.contentOrNull?.trim().orEmpty()
            if (content.isBlank()) error("todos[$index].content must not be blank")
            val status = item["status"]?.jsonPrimitive?.contentOrNull.orEmpty()
            if (status !in TODO_STATUSES) {
                error("todos[$index].status must be one of ${TODO_STATUSES.joinToString()}")
            }
            buildJsonObject {
                put("content", content)
                put("status", status)
            }
        }
        val inProgressCount = normalized.count {
            it["status"]?.jsonPrimitive?.contentOrNull == "in_progress"
        }
        val payload = buildJsonObject {
            put("todos", JsonArray(normalized))
            if (inProgressCount > 1) {
                // 软提示:模型偶发多个 in_progress 时不硬拒,附 warning 便于自我纠正
                put("warning", "More than one item is in_progress ($inProgressCount). Keep exactly one.")
            }
        }
        listOf(UIMessagePart.Text(payload.toString()))
    },
)

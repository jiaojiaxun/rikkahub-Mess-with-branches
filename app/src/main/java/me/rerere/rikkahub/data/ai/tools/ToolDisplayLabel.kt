package me.rerere.rikkahub.data.ai.tools

import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.Tool

/**
 * rhToolDisplay (batch229): 让 AI 为工具调用行生成人话文案。
 *
 * 给每个工具的 schema 注入一个可选的 [RH_DISPLAY_PARAM] 参数, 模型调用工具时
 * 顺手填一句面向用户的简短描述(如「用 GitHub 修改了仓库 README」); 渲染层
 * (ToolUI.kt 默认 title) 优先展示该描述, 未填时回退到美化后的工具名。
 *
 * execute 包装层在真正执行前把该字段从入参剥掉 —— 本地工具与 MCP server
 * 永远收不到这个纯展示字段, 对工具行为零影响。
 */
const val RH_DISPLAY_PARAM = "_display"

private val RH_DISPLAY_SCHEMA = buildJsonObject {
    put("type", JsonPrimitive("string"))
    put(
        "description",
        JsonPrimitive(
            "Optional UI label: one short user-facing phrase describing what this call does, " +
                "in the user's language, max 20 chars. " +
                "Never include parameter values, secrets or private data. Display only."
        )
    )
}

fun Tool.withRhDisplayLabel(): Tool {
    val originalParams = parameters
    val originalExecute = execute
    return copy(
        parameters = {
            when (val schema = originalParams()) {
                is InputSchema.Obj ->
                    if (schema.properties.containsKey(RH_DISPLAY_PARAM)) schema
                    else schema.copy(
                        properties = JsonObject(schema.properties + (RH_DISPLAY_PARAM to RH_DISPLAY_SCHEMA))
                    )

                else -> InputSchema.Obj(
                    properties = JsonObject(mapOf(RH_DISPLAY_PARAM to RH_DISPLAY_SCHEMA))
                )
            }
        },
        execute = { args ->
            val stripped = (args as? JsonObject)?.let { obj ->
                if (obj.containsKey(RH_DISPLAY_PARAM)) JsonObject(obj - RH_DISPLAY_PARAM) else obj
            } ?: args
            originalExecute(stripped)
        },
    )
}

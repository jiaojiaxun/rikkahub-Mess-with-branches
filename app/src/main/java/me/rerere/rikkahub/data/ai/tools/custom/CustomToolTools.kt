// rhCustomTools (batch213) — AI 自定义工具：manage_custom_tool 元工具 + 动态注册 + 执行
package me.rerere.rikkahub.data.ai.tools.custom

import android.content.Context
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.Tool
import me.rerere.ai.ui.UIMessagePart
import me.rerere.rikkahub.skills.js.JsSkillRunner
import java.io.File

private fun ctErr(code: String, detail: String): List<UIMessagePart> =
    listOf(UIMessagePart.Text(buildJsonObject {
        put("ok", false)
        put("error", code)
        put("detail", detail)
    }.toString()))

private fun isValidToolName(name: String): Boolean {
    if (name.isEmpty() || name.length > 40) return false
    val first = name[0]
    if (!(first in 'a'..'z' || first == '_')) return false
    return name.all { it in 'a'..'z' || it in '0'..'9' || it == '_' }
}

private fun normalizeSchema(schema: JsonObject?): JsonObject {
    val props = (schema?.get("properties") as? JsonObject) ?: buildJsonObject { }
    val req = (schema?.get("required") as? JsonArray)?.mapNotNull { el ->
        runCatching { el.jsonPrimitive.contentOrNull }.getOrNull()
    } ?: emptyList()
    return buildJsonObject {
        put("type", "object")
        put("properties", props)
        put("required", buildJsonArray { req.forEach { item -> add(JsonPrimitive(item)) } })
    }
}

private fun parseSchemaParam(raw: JsonElement?): JsonObject? = when (raw) {
    null -> null
    is JsonObject -> raw
    is JsonPrimitive -> raw.contentOrNull?.let { s ->
        runCatching { Json.parseToJsonElement(s) }.getOrNull() as? JsonObject
    }
    else -> null
}

private fun defSummary(d: CustomToolDef): JsonObject = buildJsonObject {
    put("id", d.id)
    put("name", d.name)
    put("description", d.description)
    put("enabled", d.enabled)
    put("created_at_ms", d.createdAt)
    put("updated_at_ms", d.updatedAt)
}

private suspend fun runCustomTool(
    store: CustomToolStore,
    def: CustomToolDef,
    dataJson: String,
    runner: JsSkillRunner,
): List<UIMessagePart> {
    if (dataJson.length > JsSkillRunner.MAX_DATA_LENGTH) {
        return ctErr("data_too_large", "arguments exceed the 64KB cap")
    }
    val dir = store.toolDir(def.id)
    store.writeScript(def, dir)
    val outcome = runner.runScript(
        scriptFile = File(dir, "index.html"),
        skillRootDir = dir,
        data = dataJson,
        secret = "",
    )
    return when (outcome) {
        is JsSkillRunner.Result.Err -> ctErr(outcome.code, outcome.detail)
        is JsSkillRunner.Result.Ok -> {
            val parsed = outcome.parsed
            val jsError = parsed.error
            if (jsError != null) {
                ctErr("js_error", jsError)
            } else {
                val text = parsed.text
                if (text.isNullOrBlank()) {
                    listOf(UIMessagePart.Text("(custom tool returned no result)"))
                } else {
                    listOf(UIMessagePart.Text(text))
                }
            }
        }
    }
}

private fun buildCustomTool(store: CustomToolStore, def: CustomToolDef, runner: JsSkillRunner): Tool = Tool(
    name = def.name,
    description = def.description,
    parameters = {
        InputSchema.Obj(
            properties = (def.parameters["properties"] as? JsonObject) ?: buildJsonObject { },
            required = (def.parameters["required"] as? JsonArray)?.mapNotNull { el ->
                runCatching { el.jsonPrimitive.contentOrNull }.getOrNull()
            },
        )
    },
    execute = { args ->
        runCustomTool(store, def, args.toString(), runner)
    },
)

private fun manageCustomTool(store: CustomToolStore, runner: JsSkillRunner): Tool = Tool(
    name = "manage_custom_tool",
    description = """
        Manage AI-authored custom tools: persistent JavaScript snippets that become callable tools.
        Actions: list (all tools, no code), get (full definition with code), create (name, description, code, optional parameters schema), update (id plus fields to change), delete (id), test (id plus optional args JSON string; runs without writing).
        A custom tool MUST define: async function main(args) { ... return "text"; } — args is the JSON object the model passes; non-string results are JSON.stringify'd. The code runs in a sandboxed WebView with browser APIs (fetch, crypto, DOM storage) and a 60s timeout.
        Name rules: lowercase a-z, 0-9, underscore; start with a letter or underscore; max 40 chars.
        create/update/delete need user approval. New tools become callable from the next model turn while the assistant's custom-tools toggle is on. Users can view and edit tools in Settings - Advanced - AI Custom Tools.
    """.trimIndent().replace("\n", " "),
    parameters = {
        InputSchema.Obj(
            properties = buildJsonObject {
                put("action", buildJsonObject {
                    put("type", "string")
                    put("enum", buildJsonArray {
                        add(JsonPrimitive("list"))
                        add(JsonPrimitive("get"))
                        add(JsonPrimitive("create"))
                        add(JsonPrimitive("update"))
                        add(JsonPrimitive("delete"))
                        add(JsonPrimitive("test"))
                    })
                    put("description", "Operation to perform")
                })
                put("id", buildJsonObject {
                    put("type", "string")
                    put("description", "Tool id (for get/update/delete/test)")
                })
                put("name", buildJsonObject {
                    put("type", "string")
                    put("description", "Tool name shown to the model (create; a-z 0-9 _)")
                })
                put("description", buildJsonObject {
                    put("type", "string")
                    put("description", "What the tool does (create/update)")
                })
                put("parameters", buildJsonObject {
                    put("description", "JSON Schema object for the tool input (create/update); a JSON string is also accepted")
                })
                put("code", buildJsonObject {
                    put("type", "string")
                    put("description", "JavaScript defining async function main(args) (create/update)")
                })
                put("enabled", buildJsonObject {
                    put("type", "boolean")
                    put("description", "Whether the tool is callable (create/update)")
                })
                put("args", buildJsonObject {
                    put("type", "string")
                    put("description", "Sample args as a JSON string (test)")
                })
            },
            required = listOf("action"),
        )
    },
    needsApproval = { args ->
        val a = runCatching { args.jsonObject["action"]?.jsonPrimitive?.contentOrNull }.getOrNull()
        a == "create" || a == "update" || a == "delete"
    },
    execute = { args ->
        val params = runCatching { args.jsonObject }.getOrNull()
            ?: return@Tool ctErr("invalid_args", "arguments must be a JSON object")
        when (params["action"]?.jsonPrimitive?.contentOrNull) {
            "list" -> {
                val arr = buildJsonArray {
                    store.all().forEach { d -> add(defSummary(d)) }
                }
                listOf(UIMessagePart.Text(buildJsonObject {
                    put("ok", true)
                    put("count", store.all().size)
                    put("tools", arr)
                }.toString()))
            }

            "get" -> {
                val want = params["id"]?.jsonPrimitive?.contentOrNull
                    ?: return@Tool ctErr("missing_id", "id is required")
                val d = store.get(want) ?: store.findByName(want)
                if (d == null) return@Tool ctErr("unknown_tool", "no tool with id/name: " + want)
                listOf(UIMessagePart.Text(buildJsonObject {
                    put("ok", true)
                    put("tool", buildJsonObject {
                        put("id", d.id)
                        put("name", d.name)
                        put("description", d.description)
                        put("enabled", d.enabled)
                        put("parameters", d.parameters)
                        put("code", d.code)
                        put("created_at_ms", d.createdAt)
                        put("updated_at_ms", d.updatedAt)
                    })
                }.toString()))
            }

            "create" -> {
                val name = params["name"]?.jsonPrimitive?.contentOrNull
                    ?: return@Tool ctErr("missing_name", "name is required")
                if (!isValidToolName(name)) {
                    return@Tool ctErr("invalid_name", "name must be a-z 0-9 _ , start with letter/underscore, max 40 chars")
                }
                if (name == "manage_custom_tool") {
                    return@Tool ctErr("invalid_name", "manage_custom_tool is reserved")
                }
                if (store.findByName(name) != null) {
                    return@Tool ctErr("name_taken", "a custom tool named this already exists; use update with its id")
                }
                val description = params["description"]?.jsonPrimitive?.contentOrNull.orEmpty()
                val code = params["code"]?.jsonPrimitive?.contentOrNull
                    ?: return@Tool ctErr("missing_code", "code is required")
                if (code.isBlank()) return@Tool ctErr("missing_code", "code is blank")
                if (!code.contains("main")) {
                    return@Tool ctErr("missing_main", "code must define async function main(args)")
                }
                val schema = normalizeSchema(parseSchemaParam(params["parameters"]))
                val def = store.upsert(
                    CustomToolDef(
                        id = store.newId(),
                        name = name,
                        description = description,
                        parameters = schema,
                        code = code,
                        enabled = params["enabled"]?.jsonPrimitive?.booleanOrNull ?: true,
                    )
                )
                listOf(UIMessagePart.Text(buildJsonObject {
                    put("ok", true)
                    put("created", true)
                    put("tool", defSummary(def))
                    put("note", "Registered. Callable from the next model turn while the custom-tools toggle is on.")
                }.toString()))
            }

            "update" -> {
                val want = params["id"]?.jsonPrimitive?.contentOrNull
                    ?: return@Tool ctErr("missing_id", "id is required")
                val prev = store.get(want) ?: store.findByName(want)
                if (prev == null) return@Tool ctErr("unknown_tool", "no tool with id/name: " + want)
                var next = prev
                val newName = params["name"]?.jsonPrimitive?.contentOrNull
                if (newName != null && newName != prev.name) {
                    if (!isValidToolName(newName) || newName == "manage_custom_tool") {
                        return@Tool ctErr("invalid_name", "invalid or reserved name: " + newName)
                    }
                    val clash = store.findByName(newName)
                    if (clash != null && clash.id != prev.id) {
                        return@Tool ctErr("name_taken", "name already used by another tool: " + newName)
                    }
                    next = next.copy(name = newName)
                }
                val newDesc = params["description"]?.jsonPrimitive?.contentOrNull
                if (newDesc != null) next = next.copy(description = newDesc)
                val newCode = params["code"]?.jsonPrimitive?.contentOrNull
                if (newCode != null) {
                    if (newCode.isBlank() || !newCode.contains("main")) {
                        return@Tool ctErr("invalid_code", "code must define async function main(args)")
                    }
                    next = next.copy(code = newCode)
                }
                val newSchema = parseSchemaParam(params["parameters"])
                if (newSchema != null) next = next.copy(parameters = normalizeSchema(newSchema))
                val newEnabled = params["enabled"]?.jsonPrimitive?.booleanOrNull
                if (newEnabled != null) next = next.copy(enabled = newEnabled)
                val saved = store.upsert(next)
                listOf(UIMessagePart.Text(buildJsonObject {
                    put("ok", true)
                    put("updated", true)
                    put("tool", defSummary(saved))
                }.toString()))
            }

            "delete" -> {
                val want = params["id"]?.jsonPrimitive?.contentOrNull
                    ?: return@Tool ctErr("missing_id", "id is required")
                val prev = store.get(want) ?: store.findByName(want)
                if (prev == null) return@Tool ctErr("unknown_tool", "no tool with id/name: " + want)
                store.delete(prev.id)
                listOf(UIMessagePart.Text(buildJsonObject {
                    put("ok", true)
                    put("deleted", prev.id)
                    put("name", prev.name)
                }.toString()))
            }

            "test" -> {
                val want = params["id"]?.jsonPrimitive?.contentOrNull
                    ?: return@Tool ctErr("missing_id", "id is required")
                val prev = store.get(want) ?: store.findByName(want)
                if (prev == null) return@Tool ctErr("unknown_tool", "no tool with id/name: " + want)
                val argStr = params["args"]?.jsonPrimitive?.contentOrNull ?: "{}"
                runCustomTool(store, prev, argStr, runner)
            }

            else -> ctErr("invalid_action", "action must be one of list/get/create/update/delete/test")
        }
    },
)

/** 注册入口：元工具 + 每个启用的自定义工具。由 LocalTools.getTools 在开关打开时调用。 */
fun customTools(context: Context, runner: JsSkillRunner): List<Tool> {
    val store = CustomToolStore.get(context)
    val list = mutableListOf<Tool>()
    list.add(manageCustomTool(store, runner))
    store.enabled().forEach { def ->
        list.add(buildCustomTool(store, def, runner))
    }
    return list
}

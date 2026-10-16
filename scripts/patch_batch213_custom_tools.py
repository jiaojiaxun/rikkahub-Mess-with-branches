#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch213 v2: AI 自定义工具（高级功能）—— AI 可自行编写 / 调用 / 管理持久化 JS 工具

v1 死因（run #400, patch 步骤 12s 挂）: 本文件头 docstring 里写了 r 前缀三引号的
字面量示例, 把 docstring 提前终止 → SyntaxError(line 36) → python 退出码非 0 →
工作流 if ! python3 触发 exit 1 → 整个构建链断。教训: docstring 内不得出现三连单引号。

v2 变更:
  1. docstring 去掉全部三连单引号字样(本文件内不出现三连单引号)
  2. 每处编辑独立幂等 marker(LocalTools.enum / LocalTools.gate / Route.val /
     Route.entry / AssistantPage / SettingRow / SearchIndex), 支持安全重跑
  3. 注册块门控 enum 成功 + F_TOOLS 已写入(避免引用缺失符号导致编译红)
  4. main 每阶段独立 try/except(单阶段崩溃不影响后续阶段, 全部 skip + 末尾正常退出)

需求: 在「设置 -> 高级功能」里加 AI 自定义工具。AI 可以调用元工具创建/编写工具，
      之后直接按名字调用它创建的工具。

架构（3 新文件 + 6 处编辑）:
  新文件:
    data/ai/tools/custom/CustomToolStore.kt   —— 文件型存储(files/custom-tools/id/tool.json
                                                 为唯一事实源, index.html 为执行派生物)
    data/ai/tools/custom/CustomToolTools.kt   —— manage_custom_tool 元工具 + 动态注册 +
                                                 JsSkillRunner 执行(复用 WebView 引擎, 60s 超时)
    ui/pages/setting/SettingCustomToolsPage.kt —— 管理页(查看/开关/编辑/删除/新建)
  编辑(全部锚定在链脚本注入行, 零新增 import, 全限定名调用):
    LocalTools.kt             + enum CustomTools(锚 batch87 行) + getTools 注册块(锚 batch96 行)
    AssistantLocalToolPage.kt + 开关行(锚 batch96 Notification 行, 同形状)
    RouteActivity.kt          + Screen val(锚 batch37 行) + entry(锚 batch37 行)
    SettingPage.kt            + 高级功能入口 item(锚 batch37/149 后唯一的定时任务 item)
    SettingsSearchIndex.kt    + 搜索条目(锚定时任务条目; 依赖 strings 先成功)
    values/strings.xml + values-zh/strings.xml + 2 个字符串(插入最后的 resources 闭合标签前)

warn-only: 任何锚点/校验失败只 ::warning + 跳过该阶段, 不阻塞构建。
阶段门控(编译依赖): strings -> SI; Screen val -> entry/设置行/SI; enum -> 开关行/注册块;
                    F_TOOLS -> 注册块; F_PAGE -> entry。

=========================== 五查 ===========================
1. import: 编辑文件零新增(FQN 调用 + 已存在的图标/组件 import); 新文件自带完整 import
2. 同文件冲突: 锚点全部选在 batch37/87/96 注入行(唯一, 带专属 marker);
   避开 patch_chat_ui_tools(Archive 区)/patch_local_tool_page(javascript_engine 区)
3. 作用域: enum 在 sealed class 内; 注册块在 getTools 函数体内; item 与既有 item 同级
4. 括号配对: 每个编辑文件写入前断言 balance 不变
5. 函数签名: 不改任何既有签名(新增均为独立文件/独立块)
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhCustomTools'
BATCH = 'batch213'

LT = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt'
AP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/detail/AssistantLocalToolPage.kt'
RA = 'app/src/main/java/me/rerere/rikkahub/RouteActivity.kt'
SP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPage.kt'
SI = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingsSearchIndex.kt'
SE = 'app/src/main/res/values/strings.xml'
SZ = 'app/src/main/res/values-zh/strings.xml'
F_STORE = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/custom/CustomToolStore.kt'
F_TOOLS = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/custom/CustomToolTools.kt'
F_PAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingCustomToolsPage.kt'

applied = []
skipped = []


def ok(tag):
    if tag not in applied:
        applied.append(tag)


def skip(tag, why):
    skipped.append(tag + '<' + str(why)[:90] + '>')


def safe(name, fn, default=None):
    try:
        return fn()
    except Exception as exc:
        skip(name, 'crash:' + str(exc)[:70])
        return default


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def concat(lines):
    t = ''
    for i, ln in enumerate(lines):
        if i > 0:
            t += NL
        t += ln
    return t


def joinlist(items):
    t = ''
    for i, s in enumerate(items):
        if i > 0:
            t += ','
        t += s
    return t


def read(path):
    p = ROOT / path
    if not p.exists():
        return None
    try:
        return p.read_text(encoding='utf-8')
    except Exception:
        return None


def write(path, text):
    p = ROOT / path
    if not p.parent.exists():
        p.parent.mkdir(parents=True)
    p.write_text(text, encoding='utf-8')


def find_item_end(lines, start):
    '''从 start 行(以 item( 开头)起按圆括号/花括号深度找闭合行。'''
    depth = 0
    for j in range(start, len(lines)):
        depth += lines[j].count('(') - lines[j].count(')')
        depth += lines[j].count('{') - lines[j].count('}')
        if depth <= 0 and j > start:
            return j
    return -1


# ============================================================
# 新文件 1: CustomToolStore.kt
# ============================================================
STORE_KT = r'''// rhCustomTools (batch213) — AI 自定义工具：存储层（tool.json 唯一事实源 + index.html 派生物）
package me.rerere.rikkahub.data.ai.tools.custom

import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import java.io.File
import java.util.UUID

/**
 * AI 自定义工具的定义。name 是暴露给模型的工具名；parameters 是 JSON Schema object；
 * code 是 JavaScript，需定义 async function main(args) { ... return "text"; }。
 */
@Serializable
data class CustomToolDef(
    val id: String,
    val name: String,
    val description: String,
    val parameters: JsonObject,
    val code: String,
    val enabled: Boolean = true,
    val createdAt: Long = 0L,
    val updatedAt: Long = 0L,
)

/**
 * 文件型存储：每个工具一个目录（tool.json 为唯一事实源；index.html 是执行用派生物）。
 * 懒加载全局单例 —— AI 侧与设置页共享同一实例，改动即时互相可见，无需 Application 初始化。
 */
class CustomToolStore private constructor(context: Context) {

    private val appContext = context.applicationContext
    private val json = Json { ignoreUnknownKeys = true }

    private val _tools = MutableStateFlow<List<CustomToolDef>>(emptyList())
    val toolsFlow: StateFlow<List<CustomToolDef>> = _tools.asStateFlow()

    @Volatile
    private var loaded = false

    fun rootDir(): File = File(appContext.filesDir, "custom-tools").apply { mkdirs() }

    fun toolDir(id: String): File = File(rootDir(), id).apply { mkdirs() }

    private fun ensureLoaded() {
        if (loaded) return
        synchronized(this) {
            if (loaded) return
            _tools.value = scanDisk()
            loaded = true
        }
    }

    private fun scanDisk(): List<CustomToolDef> {
        val dirs = rootDir().listFiles { f -> f.isDirectory } ?: return emptyList()
        return dirs.mapNotNull { dir ->
            val f = File(dir, "tool.json")
            if (!f.isFile) return@mapNotNull null
            runCatching {
                json.decodeFromString(CustomToolDef.serializer(), f.readText())
            }.getOrNull()
        }.sortedBy { it.createdAt }
    }

    fun all(): List<CustomToolDef> {
        ensureLoaded()
        return _tools.value
    }

    fun enabled(): List<CustomToolDef> = all().filter { it.enabled }

    fun get(id: String): CustomToolDef? = all().firstOrNull { it.id == id }

    fun findByName(name: String): CustomToolDef? = all().firstOrNull { it.name == name }

    fun newId(): String = UUID.randomUUID().toString()

    fun upsert(def: CustomToolDef): CustomToolDef {
        ensureLoaded()
        val now = System.currentTimeMillis()
        val safeId = if (def.id.isBlank()) newId() else def.id
        val prev = if (def.id.isBlank()) null else get(def.id)
        val finalDef = def.copy(
            id = safeId,
            createdAt = prev?.createdAt ?: (if (def.createdAt > 0L) def.createdAt else now),
            updatedAt = now,
        )
        val dir = toolDir(finalDef.id)
        File(dir, "tool.json").writeText(json.encodeToString(CustomToolDef.serializer(), finalDef))
        writeScript(finalDef, dir)
        val list = _tools.value.toMutableList()
        val idx = list.indexOfFirst { it.id == finalDef.id }
        if (idx >= 0) {
            list[idx] = finalDef
        } else {
            list.add(finalDef)
        }
        _tools.value = list
        return finalDef
    }

    fun delete(id: String): Boolean {
        ensureLoaded()
        val existed = get(id) != null
        toolDir(id).deleteRecursively()
        _tools.value = _tools.value.filterNot { it.id == id }
        return existed
    }

    /**
     * 生成执行用 index.html：包装器在前（把模型传入的 JSON 交给 main(args)），
     * 用户代码在后（定义 main；若自行定义 ai_edge_gallery_get_result 则覆盖包装器）。
     */
    fun writeScript(def: CustomToolDef, dir: File) {
        val sb = StringBuilder()
        sb.append("<!DOCTYPE html>\n<html>\n<head><meta charset='utf-8'></head>\n<body>\n<script>\n")
        sb.append(WRAPPER_JS)
        sb.append("\n</script>\n<script>\n")
        sb.append(def.code)
        sb.append("\n</script>\n</body>\n</html>\n")
        File(dir, "index.html").writeText(sb.toString())
    }

    companion object {
        @Volatile
        private var instance: CustomToolStore? = null

        fun get(context: Context): CustomToolStore {
            instance?.let { return it }
            return synchronized(this) {
                instance ?: CustomToolStore(context.applicationContext).also { instance = it }
            }
        }

        /** 把 AI 写的 main(args) 适配到 JsSkillRunner 的执行契约。 */
        val WRAPPER_JS: String = """window.ai_edge_gallery_get_result = async function (data, secret) {
    var args = {};
    try { args = JSON.parse(data || '{}'); } catch (e) { args = { raw: String(data) }; }
    if (typeof main !== 'function') {
        return { error: 'custom tool must define: async function main(args) { ... return text; }' };
    }
    try {
        var out = await main(args);
        if (typeof out === 'string') { return { result: out }; }
        if (out === undefined || out === null) { return { result: '' }; }
        return { result: JSON.stringify(out) };
    } catch (e) {
        return { error: 'main() threw: ' + (e && e.message ? e.message : String(e)) };
    }
};"""
    }
}
'''

# ============================================================
# 新文件 2: CustomToolTools.kt
# ============================================================
TOOLS_KT = r'''// rhCustomTools (batch213) — AI 自定义工具：manage_custom_tool 元工具 + 动态注册 + 执行
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
'''

# ============================================================
# 新文件 3: SettingCustomToolsPage.kt
# ============================================================
PAGE_KT = r'''// rhCustomTools (batch213) — AI 自定义工具管理页：查看 / 开关 / 编辑 / 删除 / 新建
package me.rerere.rikkahub.ui.pages.setting

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.LargeFlexibleTopAppBar
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import me.rerere.rikkahub.data.ai.tools.custom.CustomToolDef
import me.rerere.rikkahub.data.ai.tools.custom.CustomToolStore
import me.rerere.rikkahub.ui.components.nav.BackButton
import me.rerere.rikkahub.ui.components.ui.CardGroup
import me.rerere.rikkahub.ui.theme.CustomColors
import me.rerere.rikkahub.utils.plus

@Composable
fun SettingCustomToolsPage() {
    val context = LocalContext.current
    val store = remember { CustomToolStore.get(context) }
    val tools by store.toolsFlow.collectAsStateWithLifecycle()
    val scrollBehavior = TopAppBarDefaults.exitUntilCollapsedScrollBehavior()
    var editing by remember { mutableStateOf<CustomToolDef?>(null) }
    var creating by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            LargeFlexibleTopAppBar(
                title = { Text("AI 自定义工具") },
                navigationIcon = { BackButton() },
                actions = {
                    TextButton(onClick = { creating = true }) { Text("新建") }
                },
                scrollBehavior = scrollBehavior,
                colors = CustomColors.topBarColors,
            )
        },
        modifier = Modifier.nestedScroll(scrollBehavior.nestedScrollConnection),
        containerColor = CustomColors.topBarColors.containerColor,
    ) { contentPadding ->
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = contentPadding + PaddingValues(8.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item("intro") {
                CardGroup(
                    modifier = Modifier.padding(horizontal = 8.dp),
                    title = { Text("这是什么") },
                ) {
                    item(
                        headlineContent = { Text("让 AI 自己写工具") },
                        supportingContent = {
                            Text("在助手的本地工具里开启「AI 自定义工具」后，AI 可以通过 manage_custom_tool 编写 JavaScript 工具并持久保存，之后的对话里按名字直接调用。代码在沙箱 WebView 里运行，可用 fetch 等浏览器能力，超时 60 秒。")
                        },
                    )
                }
            }

            item("tools") {
                CardGroup(
                    modifier = Modifier.padding(horizontal = 8.dp),
                    title = { Text("已创建的工具（" + tools.size + "）") },
                ) {
                    if (tools.isEmpty()) {
                        item(
                            headlineContent = { Text("还没有自定义工具") },
                            supportingContent = {
                                Text("在聊天里对 AI 说「帮我创建一个工具：……」，或点右上角新建")
                            },
                        )
                    } else {
                        tools.forEach { tool ->
                            item(
                                onClick = { editing = tool },
                                headlineContent = { Text(tool.name) },
                                supportingContent = {
                                    Column {
                                        if (tool.description.isNotBlank()) {
                                            Text(tool.description.take(80))
                                        }
                                        Text(
                                            text = "更新于 " + formatToolTime(tool.updatedAt),
                                            style = MaterialTheme.typography.labelSmall,
                                        )
                                    }
                                },
                                trailingContent = {
                                    Switch(
                                        checked = tool.enabled,
                                        onCheckedChange = { checked ->
                                            store.upsert(tool.copy(enabled = checked))
                                        },
                                    )
                                },
                            )
                        }
                    }
                }
            }
        }
    }

    editing?.let { tool ->
        CustomToolEditDialog(
            initial = tool,
            onDismiss = { editing = null },
            onSave = { updated ->
                store.upsert(updated)
                editing = null
            },
            onDelete = {
                store.delete(tool.id)
                editing = null
            },
        )
    }

    if (creating) {
        CustomToolEditDialog(
            initial = null,
            onDismiss = { creating = false },
            onSave = { updated ->
                store.upsert(updated)
                creating = false
            },
            onDelete = null,
        )
    }
}

@Composable
private fun CustomToolEditDialog(
    initial: CustomToolDef?,
    onDismiss: () -> Unit,
    onSave: (CustomToolDef) -> Unit,
    onDelete: (() -> Unit)?,
) {
    var name by remember { mutableStateOf(initial?.name ?: "") }
    var description by remember { mutableStateOf(initial?.description ?: "") }
    var code by remember { mutableStateOf(initial?.code ?: "") }
    val isCreate = initial == null

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (isCreate) "新建自定义工具" else ("编辑 " + (initial?.name ?: ""))) },
        text = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("工具名（小写字母/数字/下划线）") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it },
                    label = { Text("描述（AI 靠它决定何时调用）") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = code,
                    onValueChange = { code = it },
                    label = { Text("JavaScript 代码（需定义 main）") },
                    textStyle = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace),
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 6,
                )
                Text(
                    text = "代码约定：async function main(args) { ... return 文本; }，args 为模型传入的 JSON 对象。",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        },
        confirmButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                if (onDelete != null) {
                    TextButton(onClick = onDelete) {
                        Text("删除", color = MaterialTheme.colorScheme.error)
                    }
                }
                TextButton(
                    onClick = {
                        val base = initial
                        val def = CustomToolDef(
                            id = base?.id ?: "",
                            name = name.trim(),
                            description = description.trim(),
                            parameters = base?.parameters ?: kotlinx.serialization.json.buildJsonObject { },
                            code = code,
                            enabled = base?.enabled ?: true,
                            createdAt = base?.createdAt ?: 0L,
                        )
                        onSave(def)
                    },
                    enabled = name.trim().isNotEmpty() && code.isNotBlank(),
                ) {
                    Text("保存")
                }
            }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("取消") }
        },
    )
}

private fun formatToolTime(millis: Long): String =
    if (millis <= 0L) {
        "未知时间"
    } else {
        java.text.SimpleDateFormat("MM-dd HH:mm", java.util.Locale.getDefault())
            .format(java.util.Date(millis))
    }
'''


# ============================================================
# 阶段 1: 写 3 个新文件
# ============================================================
def phase_new_files():
    files = (
        (F_STORE, STORE_KT, ('class CustomToolStore', 'data class CustomToolDef')),
        (F_TOOLS, TOOLS_KT, ('fun customTools(', 'manage_custom_tool', 'async function main(args)')),
        (F_PAGE, PAGE_KT, ('fun SettingCustomToolsPage()',)),
    )
    for path, content, needles in files:
        cur = read(path)
        if cur is not None and MARK in cur:
            ok('new:' + path.split('/')[-1] + '-exists')
            continue
        write(path, content)
        chk = read(path) or ''
        bad = None
        for n in needles:
            if n not in chk:
                bad = n
        if bad is not None or MARK not in chk:
            skip('new:' + path.split('/')[-1], 'verify:' + str(bad))
        else:
            ok('new:' + path.split('/')[-1])
    return (read(F_PAGE) is not None, read(F_TOOLS) is not None)


# ============================================================
# 阶段 2: LocalTools.kt —— enum + getTools 注册块（各自独立幂等 marker）
# ============================================================
def phase_local_tools(tools_file_ok):
    src = read(LT)
    if src is None:
        skip('LocalTools', 'missing')
        return (False, False)
    lines = src.split(NL)
    bal0 = balance(src)
    enum_ok = False
    gate_ok = False
    changed = False

    # --- enum 项（幂等: rhCustomToolsEnum） ---
    if 'rhCustomToolsEnum' in src:
        enum_ok = True
        ok('LocalTools.enum-exists')
    else:
        hits = [i for i, ln in enumerate(lines)
                if 'data object Notification' in ln and 'rhSendNotification' in ln]
        if len(hits) != 1:
            hits = [i for i, ln in enumerate(lines)
                    if 'data object Toast' in ln and 'LocalToolOption()' in ln]
        if len(hits) == 1:
            ei = hits[0]
            d = ind(lines[ei])
            lines.insert(ei + 1, d + '@Serializable @SerialName("custom_tools") data object CustomTools : LocalToolOption() // rhCustomToolsEnum')
            enum_ok = True
            changed = True
        else:
            skip('LocalTools.enum', 'anchor=' + str(len(hits)))

    # --- getTools 注册块（幂等: rhCustomToolsGate; 依赖 enum + F_TOOLS） ---
    if 'rhCustomToolsGate' in src:
        gate_ok = True
        ok('LocalTools.gate-exists')
    elif not tools_file_ok:
        skip('LocalTools.gate', 'tools-file-missing')
    elif not enum_ok:
        skip('LocalTools.gate', 'enum-missing')
    else:
        hits = [i for i, ln in enumerate(lines) if 'rhNotifScope' in ln]
        if len(hits) == 1:
            gi = hits[0]
            if gi + 2 < len(lines) and lines[gi + 1].strip().startswith('tools.add(notificationTool') and lines[gi + 2].strip() == '}':
                d0 = ind(lines[gi])
                block = [
                    d0 + 'if (options.contains(LocalToolOption.CustomTools)) { // rhCustomToolsGate (batch213)',
                    d0 + '    tools.addAll(me.rerere.rikkahub.data.ai.tools.custom.customTools(context, jsSkillRunner))',
                    d0 + '}',
                ]
                lines[gi + 3:gi + 3] = block
                gate_ok = True
                changed = True
            else:
                skip('LocalTools.gate', 'shape')
        else:
            skip('LocalTools.gate', 'anchor=' + str(len(hits)))

    if not changed:
        return (enum_ok, gate_ok)
    out = concat(lines)
    if balance(out) != bal0:
        skip('LocalTools', 'balance')
        return (enum_ok, gate_ok)
    checks = []
    if enum_ok and 'rhCustomToolsEnum' not in out:
        checks.append('enum')
    if gate_ok and 'rhCustomToolsGate' not in out:
        checks.append('gate')
    if checks:
        skip('LocalTools', 'selfcheck:' + joinlist(checks))
        return (enum_ok, gate_ok)
    write(LT, out)
    ok('LocalTools')
    return (enum_ok, gate_ok)


# ============================================================
# 阶段 3: AssistantLocalToolPage.kt —— 开关行
# ============================================================
def phase_local_tool_page(enum_ok):
    if not enum_ok:
        skip('AssistantPage', 'enum-missing')
        return
    src = read(AP)
    if src is None:
        skip('AssistantPage', 'missing')
        return
    if 'rhCustomToolsRow' in src:
        ok('AssistantPage-exists')
        return
    lines = src.split(NL)
    bal0 = balance(src)
    hits = [i for i, ln in enumerate(lines)
            if 'toggleLocalTool(LocalToolOption.Notification, it)' in ln]
    if len(hits) != 1:
        skip('AssistantPage', 'anchor=' + str(len(hits)))
        return
    oc = hits[0]
    if not (lines[oc + 1].strip() == ')' and lines[oc + 2].strip() == '}' and lines[oc + 3].strip() == ')'):
        skip('AssistantPage', 'shape')
        return
    item_start = -1
    for j in range(oc, max(oc - 20, -1), -1):
        if lines[j].strip().startswith('item('):
            item_start = j
            break
    if item_start < 0:
        skip('AssistantPage', 'item-start')
        return
    di = ind(lines[item_start])
    block = [
        di + 'item( // rhCustomToolsRow (batch213)',
        di + '    headlineContent = {',
        di + '        Text("AI 自定义工具")',
        di + '    },',
        di + '    supportingContent = {',
        di + '        Text("允许 AI 自己编写 JavaScript 工具并调用（在 设置-高级功能 里管理）")',
        di + '    },',
        di + '    trailingContent = {',
        di + '        Switch(',
        di + '            checked = assistant.localTools.contains(LocalToolOption.CustomTools),',
        di + '            onCheckedChange = { toggleLocalTool(LocalToolOption.CustomTools, it) }',
        di + '        )',
        di + '    }',
        di + ')',
    ]
    lines[oc + 4:oc + 4] = block
    out = concat(lines)
    if 'rhCustomToolsRow' not in out or 'LocalToolOption.CustomTools' not in out:
        skip('AssistantPage', 'selfcheck')
        return
    if balance(out) != bal0:
        skip('AssistantPage', 'balance')
        return
    write(AP, out)
    ok('AssistantPage')


# ============================================================
# 阶段 4: RouteActivity.kt —— Screen val + entry（各自独立幂等 marker）
# ============================================================
def phase_route(page_ok):
    src = read(RA)
    if src is None:
        skip('Route', 'missing')
        return (False, False)
    lines = src.split(NL)
    bal0 = balance(src)
    val_ok = False
    entry_ok = False
    changed = False

    # --- Screen val（幂等: data object SettingCustomTools） ---
    if 'data object SettingCustomTools : Screen' in src:
        val_ok = True
        ok('Route.val-exists')
    else:
        hits = [i for i, ln in enumerate(lines)
                if ln.strip() == 'data object SettingScheduledJobs : Screen']
        if len(hits) == 1:
            vi = hits[0]
            d = ind(lines[vi])
            block = [
                '',
                d + '/** rhCustomTools */',
                d + '@Serializable',
                d + 'data object SettingCustomTools : Screen',
            ]
            lines[vi + 1:vi + 1] = block
            val_ok = True
            changed = True
        else:
            skip('Route.val', 'anchor=' + str(len(hits)))

    # --- entry（幂等: entry<Screen.SettingCustomTools>; 依赖 val + 页面文件） ---
    if 'entry<Screen.SettingCustomTools>' in src:
        entry_ok = True
        ok('Route.entry-exists')
    elif not val_ok:
        skip('Route.entry', 'val-missing')
    elif not page_ok:
        skip('Route.entry', 'page-missing')
    else:
        hits = [i for i, ln in enumerate(lines)
                if ln.strip() == 'entry<Screen.SettingScheduledJobs> {']
        if len(hits) == 1:
            ei = hits[0]
            if ei + 2 < len(lines) and 'SettingScheduledJobsPage()' in lines[ei + 1] and lines[ei + 2].strip() == '}':
                d = ind(lines[ei])
                block = [
                    '',
                    d + '/* rhCustomTools */',
                    d + 'entry<Screen.SettingCustomTools> {',
                    d + '    me.rerere.rikkahub.ui.pages.setting.SettingCustomToolsPage()',
                    d + '}',
                ]
                lines[ei + 3:ei + 3] = block
                entry_ok = True
                changed = True
            else:
                skip('Route.entry', 'shape')
        else:
            skip('Route.entry', 'anchor=' + str(len(hits)))

    if not changed:
        return (val_ok, entry_ok)
    out = concat(lines)
    if balance(out) != bal0:
        skip('Route', 'balance')
        return (val_ok, entry_ok)
    checks = []
    if val_ok and 'data object SettingCustomTools : Screen' not in out:
        checks.append('val')
    if entry_ok and 'entry<Screen.SettingCustomTools>' not in out:
        checks.append('entry')
    if checks:
        skip('Route', 'selfcheck:' + joinlist(checks))
        return (val_ok, entry_ok)
    write(RA, out)
    ok('Route')
    return (val_ok, entry_ok)


# ============================================================
# 阶段 5: SettingPage.kt —— 高级功能入口 item
# ============================================================
def phase_setting_page(val_ok, entry_ok):
    if not (val_ok and entry_ok):
        skip('SettingRow', 'route-incomplete')
        return
    src = read(SP)
    if src is None:
        skip('SettingRow', 'missing')
        return
    if 'Screen.SettingCustomTools' in src:
        ok('SettingRow-exists')
        return
    lines = src.split(NL)
    bal0 = balance(src)
    hits = [i for i, ln in enumerate(lines) if 'Screen.SettingScheduledJobs' in ln]
    if len(hits) != 1:
        skip('SettingRow', 'anchor=' + str(len(hits)))
        return
    ni = hits[0]
    item_start = -1
    for j in range(ni, max(ni - 12, -1), -1):
        if lines[j].strip().startswith('item('):
            item_start = j
            break
    if item_start < 0:
        skip('SettingRow', 'item-start')
        return
    item_end = find_item_end(lines, item_start)
    if item_end < 0 or (item_end - item_start) > 30:
        skip('SettingRow', 'item-end')
        return
    di = ind(lines[item_start])
    block = [
        di + '/* rhCustomTools (batch213) */',
        di + 'item(',
        di + '    onClick = { navController.navigate(Screen.SettingCustomTools) },',
        di + '    leadingContent = { Icon(HugeIcons.Console, null) },',
        di + '    supportingContent = { Text("让 AI 自己编写 JavaScript 工具并调用") },',
        di + '    headlineContent = { Text("AI 自定义工具") },',
        di + ')',
    ]
    lines[item_end + 1:item_end + 1] = block
    out = concat(lines)
    if 'Screen.SettingCustomTools' not in out or 'rhCustomTools' not in out:
        skip('SettingRow', 'selfcheck')
        return
    if balance(out) != bal0:
        skip('SettingRow', 'balance')
        return
    write(SP, out)
    ok('SettingRow')


# ============================================================
# 阶段 6: strings.xml（en + zh）
# ============================================================
def insert_strings(path, pair):
    src = read(path)
    if src is None:
        skip('strings:' + path.split('/')[-2], 'missing')
        return False
    if 'setting_page_custom_tools' in src:
        ok('strings:' + path.split('/')[-2] + '-exists')
        return True
    lines = src.split(NL)
    idx = -1
    for i, ln in enumerate(lines):
        if '</resources>' in ln:
            idx = i
    if idx < 0:
        skip('strings:' + path.split('/')[-2], 'no-close-tag')
        return False
    block = [
        '    <string name="' + pair[0] + '">' + pair[1] + '</string>',
        '    <string name="' + pair[0] + '_desc">' + pair[2] + '</string>',
    ]
    lines[idx:idx] = block
    out = concat(lines)
    if pair[0] not in out or '</resources>' not in out:
        skip('strings:' + path.split('/')[-2], 'selfcheck')
        return False
    write(path, out)
    ok('strings:' + path.split('/')[-2])
    return True


def phase_strings():
    en_ok = insert_strings(
        SE,
        ('setting_page_custom_tools', 'AI Custom Tools',
         'Let the AI write and call its own JavaScript tools'),
    )
    zh_ok = insert_strings(
        SZ,
        ('setting_page_custom_tools', 'AI 自定义工具',
         '让 AI 自己编写并调用 JavaScript 工具'),
    )
    return (en_ok, zh_ok)


# ============================================================
# 阶段 7: SettingsSearchIndex.kt —— 搜索条目
# ============================================================
def phase_search_index(val_ok, entry_ok, en_ok):
    if not (val_ok and entry_ok):
        skip('SearchIndex', 'route-incomplete')
        return
    if not en_ok:
        skip('SearchIndex', 'strings-missing')
        return
    src = read(SI)
    if src is None:
        skip('SearchIndex', 'missing')
        return
    if 'route = Screen.SettingCustomTools' in src:
        ok('SearchIndex-exists')
        return
    lines = src.split(NL)
    bal0 = balance(src)
    hits = [i for i, ln in enumerate(lines) if 'Screen.SettingScheduledJobs' in ln]
    if len(hits) != 1:
        skip('SearchIndex', 'anchor=' + str(len(hits)))
        return
    ri = hits[0]
    entry_start = -1
    for j in range(ri, max(ri - 8, -1), -1):
        if lines[j].strip().startswith('SettingsSearchEntry('):
            entry_start = j
            break
    if entry_start < 0:
        skip('SearchIndex', 'entry-start')
        return
    entry_end = -1
    for j in range(ri, min(ri + 8, len(lines))):
        if lines[j].strip() == '),':
            entry_end = j
            break
    if entry_end < 0:
        skip('SearchIndex', 'entry-end')
        return
    d = ind(lines[entry_start])
    block = [
        d + 'SettingsSearchEntry( /* rhCustomTools (batch213) */',
        d + '    titleRes = R.string.setting_page_custom_tools,',
        d + '    descriptionRes = R.string.setting_page_custom_tools_desc,',
        d + '    groupRes = R.string.setting_page_model_and_services,',
        d + '    route = Screen.SettingCustomTools,',
        d + '),',
    ]
    lines[entry_end + 1:entry_end + 1] = block
    out = concat(lines)
    if 'route = Screen.SettingCustomTools' not in out:
        skip('SearchIndex', 'selfcheck')
        return
    if balance(out) != bal0:
        skip('SearchIndex', 'balance')
        return
    write(SI, out)
    ok('SearchIndex')


# ============================================================
# main（每阶段独立隔离）
# ============================================================
def main():
    r1 = safe('new-files', phase_new_files, (False, False))
    page_ok = r1[0] if r1 else False
    tools_ok = r1[1] if r1 else False

    r2 = safe('LocalTools', lambda: phase_local_tools(tools_ok), (False, False))
    enum_ok = r2[0] if r2 else False
    gate_ok = r2[1] if r2 else False

    safe('AssistantPage', lambda: phase_local_tool_page(enum_ok))

    r3 = safe('Route', lambda: phase_route(page_ok), (False, False))
    val_ok = r3[0] if r3 else False
    entry_ok = r3[1] if r3 else False

    safe('SettingRow', lambda: phase_setting_page(val_ok, entry_ok))

    r4 = safe('strings', phase_strings, (False, False))
    en_ok = r4[0] if r4 else False
    zh_ok = r4[1] if r4 else False

    safe('SearchIndex', lambda: phase_search_index(val_ok, entry_ok, en_ok))

    print(BATCH + ': applied=[' + joinlist(applied) + ']')
    print(':warning:' + BATCH + ' skipped=[' + joinlist(skipped) + ']')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(':warning:' + BATCH + ' crashed: ' + str(exc)[:600])
    sys.exit(0)
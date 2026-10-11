#!/usr/bin/env python3
# batch147 v2: 移植上游 2.5.6 MCP 工具 schema $ref 内联修复 (rikkahub #1974 / 上游 cf79246b)
#
# v1 死因: run #363 patch 步 45s 挂。自查根因 = 预检断言写错:
#   registry.count(".toSchema()") 实际为 3 (mergeTools 2 处调用 + 尾部旧函数签名
#   "private fun ToolSchema.toSchema()" 也含该子串), v1 误写成 != 2, fail-loud 正确拦下。
# v2 改法: 预检计数 2->3, 并在注释里写明构成; 其余不变。
#
# 变更:
#   1) 新增 app/src/main/java/me/rerere/rikkahub/data/ai/mcp/McpToolSchema.kt
#      —— 把工具 inputSchema 里的文档内 $ref 内联展开, 保留 $defs 内容,
#         修复悬空 $ref 导致 provider 400 (#1974)
#   2) 新增 app/src/test/java/me/rerere/rikkahub/data/ai/mcp/McpToolSchemaTest.kt (上游单测)
#   3) McpSessionRegistry.kt: 删除旧 toSchema() 尾部函数 + 两个随之下线的 import
#
# 兼容性(已核实): 官方 kotlin-sdk 0.15.0 的 ToolSchema 自带
#   defs: JsonObject? (@SerialName "\$defs") 与 type: String,
#   见 0.15.0 tag 的 types/tools.kt —— 无需升级 SDK。
# 不适用项: 上游同区修复 7a53065 (OAuth 回调 127.0.0.1→localhost) 不移植 ——
#   fork 的 MCP OAuth 回调是 rikkahub:// 自定义 scheme (McpOAuthCallback.kt),
#   不经 127.0.0.1, 无 WAF 拦 IPv4 主机问题。
#
# 锚点: 已按 fix/batch1 实况逐字核对 (2026-10-11)。
# 幂等: 新文件含特征串即跳过; 注册表旧函数不在即跳过。
# 引号纪律: 锚点均不含引号; 新文件内容用 r''' 原文整块内嵌
#   (内容含 ${'$'} / "\$ref" 等, 逐行拼接引号风险更高 —— batch94/95 教训)。

import io
import os
import sys

NL = chr(10)
REGISTRY = "app/src/main/java/me/rerere/rikkahub/data/ai/mcp/McpSessionRegistry.kt"
NEW_FILE = "app/src/main/java/me/rerere/rikkahub/data/ai/mcp/McpToolSchema.kt"
TEST_FILE = "app/src/test/java/me/rerere/rikkahub/data/ai/mcp/McpToolSchemaTest.kt"
NEW_MARK = "内联展开"
TEST_MARK = "McpToolSchemaTest"

IMPORT_TOOLSCHEMA = "import io.modelcontextprotocol.kotlin.sdk.types.ToolSchema" + NL
IMPORT_INPUTSCHEMA = "import me.rerere.ai.core.InputSchema" + NL
OLD_TAIL = NL + "private fun ToolSchema.toSchema(): InputSchema =" + NL + "    InputSchema.Obj(properties = properties ?: JsonObject(emptyMap()), required = required)" + NL

NEW_FILE_CONTENT = r'''package me.rerere.rikkahub.data.ai.mcp

import io.modelcontextprotocol.kotlin.sdk.types.ToolSchema
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import me.rerere.ai.core.InputSchema

private const val REF = "\$ref"

/**
 * 将 MCP 工具的 inputSchema 转成内部 [InputSchema]。
 *
 * [InputSchema.Obj] 不携带 `$defs`，且部分 provider（如 Gemini）不接受 `$ref`，
 * 因此在这里把文档内引用（`#/...`）内联展开，避免发出悬空引用导致整个请求被拒绝。
 */
internal fun ToolSchema.toSchema(): InputSchema {
    val properties = properties ?: JsonObject(emptyMap())
    val root = JsonObject(buildMap {
        put("type", JsonPrimitive(type))
        put("properties", properties)
        defs?.let { put("\$defs", it) }
    })
    return InputSchema.Obj(
        properties = inlineSchemaMap(properties, root, emptySet()),
        required = required,
    )
}

// 值为子 Schema（或子 Schema 数组）的关键字
private val SCHEMA_KEYWORDS = setOf(
    "items", "prefixItems", "additionalItems", "unevaluatedItems", "contains",
    "additionalProperties", "unevaluatedProperties", "propertyNames",
    "allOf", "anyOf", "oneOf", "not", "if", "then", "else", "contentSchema",
)

// 值为「名称 -> 子 Schema」映射的关键字
private val SCHEMA_MAP_KEYWORDS = setOf(
    "properties", "patternProperties", "dependentSchemas", "\$defs", "definitions",
)

private fun inlineSchemaMap(schemas: JsonObject, root: JsonObject, resolving: Set<String>): JsonObject =
    JsonObject(schemas.mapValues { inlineSchema(it.value, root, resolving) })

/**
 * 只沿承载子 Schema 的关键字向下遍历；`enum`、`const`、`default`、`examples` 等字面量数据
 * 即使含有 `$ref` 字段也原样保留。
 */
private fun inlineSchema(schema: JsonElement, root: JsonObject, resolving: Set<String>): JsonElement {
    if (schema !is JsonObject) return schema
    val ref = (schema[REF] as? JsonPrimitive)?.takeIf { it.isString }?.content
    val inlined = (if (ref != null) schema - REF else schema).mapValues { (key, value) ->
        when {
            key in SCHEMA_KEYWORDS && value is JsonArray ->
                JsonArray(value.map { inlineSchema(it, root, resolving) })

            key in SCHEMA_KEYWORDS -> inlineSchema(value, root, resolving)
            key in SCHEMA_MAP_KEYWORDS && value is JsonObject -> inlineSchemaMap(value, root, resolving)
            else -> value
        }
    }
    if (ref == null) return JsonObject(inlined)

    val target = root.resolvePointer(ref) as? JsonObject
    val expanded = when {
        // 无法解析的引用（外部 URL、指针不存在）退化为不限制类型
        target == null -> emptyMap()
        // 循环引用无法完全展开，在回到自身的位置只保留类型
        ref in resolving -> target.filterKeys { it == "type" }
        else -> inlineSchema(target, root, resolving + ref) as JsonObject
    }
    // 与 $ref 同级的关键字（description、default 等）覆盖被引用的定义
    return JsonObject(expanded + inlined)
}

/** 解析文档内 JSON Pointer 引用（如 `#/$defs/Foo`），找不到时返回 null。 */
private fun JsonObject.resolvePointer(ref: String): JsonElement? {
    if (!ref.startsWith("#")) return null
    val tokens = ref.removePrefix("#").split("/").drop(1)
        .map { it.replace("~1", "/").replace("~0", "~") }
    return tokens.fold<String, JsonElement?>(this) { current, token ->
        when (current) {
            is JsonObject -> current[token]
            is JsonArray -> token.toIntOrNull()?.let(current::getOrNull)
            else -> null
        }
    }
}
'''

TEST_FILE_CONTENT = r'''package me.rerere.rikkahub.data.ai.mcp

import io.modelcontextprotocol.kotlin.sdk.types.ToolSchema
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import me.rerere.ai.core.InputSchema
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class McpToolSchemaTest {
    private fun json(text: String): JsonObject = Json.parseToJsonElement(text).jsonObject

    private fun convert(properties: String, defs: String? = null): JsonObject {
        val schema = ToolSchema(
            properties = json(properties),
            required = listOf("trigger"),
            defs = defs?.let(::json),
        ).toSchema() as InputSchema.Obj
        assertEquals(listOf("trigger"), schema.required)
        return schema.properties
    }

    @Test
    fun `schema without refs is kept as is`() {
        val properties = """{"query":{"type":"string","description":"keyword"}}"""

        assertEquals(json(properties), convert(properties))
    }

    @Test
    fun `refs are inlined and sibling keywords override the definition`() {
        val result = convert(
            properties = """
                {
                  "trigger": {"${'$'}ref": "#/${'$'}defs/Trigger", "description": "override"},
                  "items": {"type": "array", "items": {"${'$'}ref": "#/${'$'}defs/Trigger"}},
                  "choice": {"anyOf": [{"${'$'}ref": "#/${'$'}defs/Trigger"}, {"type": "null"}]}
                }
            """,
            defs = """
                {
                  "Trigger": {
                    "type": "object",
                    "description": "original",
                    "properties": {"spec": {"${'$'}ref": "#/${'$'}defs/Spec"}}
                  },
                  "Spec": {"type": "string", "enum": ["a", "b"]}
                }
            """,
        )

        val trigger = """{"type":"object","description":"original","properties":{"spec":{"type":"string","enum":["a","b"]}}}"""
        assertEquals(
            json(
                """
                {
                  "trigger": {"type":"object","description":"override","properties":{"spec":{"type":"string","enum":["a","b"]}}},
                  "items": {"type": "array", "items": $trigger},
                  "choice": {"anyOf": [$trigger, {"type": "null"}]}
                }
                """
            ),
            result,
        )
    }

    @Test
    fun `literal data containing a ref field is kept as is`() {
        val properties = """
            {
              "trigger": {
                "enum": [{"${'$'}ref": "document.json"}],
                "const": {"${'$'}ref": "#/${'$'}defs/Spec"},
                "default": {"${'$'}ref": "document.json"},
                "examples": [{"${'$'}ref": "#/${'$'}defs/Spec"}]
              }
            }
        """

        assertEquals(json(properties), convert(properties, defs = """{"Spec": {"type": "string"}}"""))
    }

    @Test
    fun `properties named like keywords are still treated as schemas`() {
        val result = convert(
            properties = """
                {
                  "default": {"${'$'}ref": "#/${'$'}defs/Spec"},
                  "trigger": {"type": "object", "properties": {"enum": {"${'$'}ref": "#/${'$'}defs/Spec"}}}
                }
            """,
            defs = """{"Spec": {"type": "string"}}""",
        )

        assertEquals(
            json(
                """
                {
                  "default": {"type": "string"},
                  "trigger": {"type": "object", "properties": {"enum": {"type": "string"}}}
                }
                """
            ),
            result,
        )
    }

    @Test
    fun `cyclic refs are cut instead of expanding forever`() {
        val result = convert(
            properties = """{"trigger": {"${'$'}ref": "#/${'$'}defs/Node"}}""",
            defs = """
                {
                  "Node": {
                    "type": "object",
                    "properties": {"children": {"type": "array", "items": {"${'$'}ref": "#/${'$'}defs/Node"}}}
                  }
                }
            """,
        )

        assertEquals(
            json(
                """
                {
                  "trigger": {
                    "type": "object",
                    "properties": {"children": {"type": "array", "items": {"type": "object"}}}
                  }
                }
                """
            ),
            result,
        )
    }

    @Test
    fun `unresolvable refs are dropped so no dangling ref is sent`() {
        val result = convert(
            properties = """
                {
                  "trigger": {"${'$'}ref": "#/${'$'}defs/Missing", "description": "kept"},
                  "remote": {"${'$'}ref": "https://example.com/schema.json"}
                }
            """,
        )

        assertEquals(json("""{"trigger": {"description": "kept"}, "remote": {}}"""), result)
        assertFalse(result.toString().contains("\$ref"))
    }
}
'''


def fail(msg):
    print("::error::" + msg)
    sys.exit(1)


def read_file(path):
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as exc:
        fail("batch147: read failed :: " + path + " :: " + str(exc))
    return ""


def write_new_file(path, content, mark):
    if os.path.exists(path):
        existing = read_file(path)
        if mark in existing:
            print("batch147: already present, skip :: " + path)
            return
        fail("batch147: unexpected existing file without mark :: " + path)
    if not content.startswith("package me.rerere.rikkahub.data.ai.mcp"):
        fail("batch147: embedded content sanity check failed :: " + path)
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    try:
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as exc:
        fail("batch147: write failed :: " + path + " :: " + str(exc))
    print("batch147: wrote " + path + " (" + str(len(content)) + " chars)")


def main():
    write_new_file(NEW_FILE, NEW_FILE_CONTENT, NEW_MARK)
    write_new_file(TEST_FILE, TEST_FILE_CONTENT, TEST_MARK)

    registry = read_file(REGISTRY)

    if "private fun ToolSchema.toSchema()" not in registry:
        print("batch147: registry already clean, skip edits")
        return

    if registry.count(IMPORT_TOOLSCHEMA) != 1:
        fail("batch147: ToolSchema import count=" + str(registry.count(IMPORT_TOOLSCHEMA)))
    if registry.count(IMPORT_INPUTSCHEMA) != 1:
        fail("batch147: InputSchema import count=" + str(registry.count(IMPORT_INPUTSCHEMA)))
    if registry.count(OLD_TAIL) != 1:
        fail("batch147: tail anchor count=" + str(registry.count(OLD_TAIL)))
    # 构成: mergeTools 内 2 处调用 + 尾部旧函数签名 1 处 = 3
    if registry.count(".toSchema()") != 3:
        fail("batch147: toSchema occurrence count=" + str(registry.count(".toSchema()")) + " (expect 3)")

    updated = registry.replace(IMPORT_TOOLSCHEMA, "")
    updated = updated.replace(IMPORT_INPUTSCHEMA, "")
    updated = updated.replace(OLD_TAIL, "")

    if "ToolSchema" in updated:
        fail("batch147: ToolSchema residue after edit")
    if "InputSchema" in updated:
        fail("batch147: InputSchema residue after edit")
    if updated.count(".toSchema()") != 2:
        fail("batch147: toSchema call count after edit=" + str(updated.count(".toSchema()")) + " (expect 2)")
    if updated.count("(") != updated.count(")"):
        fail("batch147: paren imbalance after edit")
    if updated.count("{") != updated.count("}"):
        fail("batch147: brace imbalance after edit")
    if not updated.endswith("}" + NL):
        fail("batch147: unexpected file tail after edit")

    try:
        with io.open(REGISTRY, "w", encoding="utf-8") as f:
            f.write(updated)
    except Exception as exc:
        fail("batch147: write failed :: " + REGISTRY + " :: " + str(exc))
    print("batch147: registry tail removed; toSchema now provided by McpToolSchema.kt")


if __name__ == "__main__":
    main()

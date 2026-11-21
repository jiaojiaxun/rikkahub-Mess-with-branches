#!/usr/bin/env python3
# upfix381: 回移上游 4 个已实锤的官方修复 (run671 静态定位, 2026-11-21)
# attempt2: run672 在 setup-java 阶段基础设施抖动失败 (patch/compile 未执行),
#           本提交仅为重触发, 代码零改动。
#
#  A1 (#2000, 上游 c211c0d44): search_web 结果超 32KB 被 maybeTruncateToolOutput
#     截成 4KB 文本预览, UI 渲染器读不到 JSON 字段 → 搜索结果显示为空。
#     修: TOOLS_WITHOUT_OUTPUT_TRUNCATION 豁免集 + toolName 参数。
#  A2 (#2137, 上游 240deb5fe): 部分中转在 SSE 流里夹 `data: null` 行,
#     `parseToJsonElement(line).jsonObject` 直接抛异常 → 整条响应崩溃。
#     修: 两处改 jsonObjectOrNull ?: return@forEach(-Indexed)。
#  A3 (上游 85af5b910): OpenRouter 没有 /images/edits 端点, editImage 一律
#     POST ${baseUrl}/images/edits → 404。
#     修: host == openrouter.ai 时改走图像生成接口 + input_references。
#  A4 (上游 1575d179d, 官方 master 未发版): 部分中转的流式/非流式响应里
#     role 返回空串/非标值, MessageRole.valueOf 直接 IllegalArgumentException。
#     修: MessageRole.fromValueOrNull 宽松匹配, 两处调用点退 ASSISTANT。
#
# 锚点全部取自 run671 snapshot 实读 (与脚本运行时看到的状态一致:
# 368/369/373/374 已在本批同推送中禁用, 且不触碰 ai/app 模块的这五个文件)。
# 幂等: probe 用最终态特征, 已存在即跳过。

import os
import sys

MARK = "upfix381"
REPO = os.getcwd()
GH = os.path.join(REPO, "app", "src", "main", "java", "me", "rerere", "rikkahub", "data", "ai", "GenerationHandler.kt")
DEC = os.path.join(REPO, "ai", "src", "main", "java", "me", "rerere", "ai", "provider", "providers", "openai", "ChatCompletionsStreamDecoder.kt")
API = os.path.join(REPO, "ai", "src", "main", "java", "me", "rerere", "ai", "provider", "providers", "openai", "ChatCompletionsAPI.kt")
PRV = os.path.join(REPO, "ai", "src", "main", "java", "me", "rerere", "ai", "provider", "providers", "openai", "OpenAIProvider.kt")
ROLE = os.path.join(REPO, "ai", "src", "main", "java", "me", "rerere", "ai", "core", "MessageRole.kt")
DIAG = os.path.join(REPO, "ci_diag_batch381_upfix_ai.txt")

OUT = []


def log(line):
    OUT.append(line)
    print(line)


def read(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return handle.read()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def apply(text, old, new, name, failures):
    count = text.count(old)
    if count != 1:
        log("anchor:" + name + ":count=" + str(count) + " (expect 1)")
        failures.append("anchor:" + name)
        return text
    return text.replace(old, new, 1)


def a1(text, failures):
    text = apply(
        text,
        "private const val TOOL_OUTPUT_PREVIEW_CHARS = 4 * 1024\n",
        "private const val TOOL_OUTPUT_PREVIEW_CHARS = 4 * 1024\n"
        "// " + MARK + ": 搜索结果 JSON 被截断后 UI 渲染器读不到字段, 显示为空 (上游 #2000)\n"
        "private val TOOLS_WITHOUT_OUTPUT_TRUNCATION = setOf(\"search_web\")\n",
        "a1-const",
        failures,
    )
    text = apply(
        text,
        "                                output = maybeTruncateToolOutput(tool.toolCallId, result)",
        "                                output = maybeTruncateToolOutput(tool.toolCallId, result, tool.toolName)",
        "a1-call",
        failures,
    )
    text = apply(
        text,
        "    private fun maybeTruncateToolOutput(\n"
        "        toolCallId: String,\n"
        "        output: List<UIMessagePart>,\n"
        "    ): List<UIMessagePart> {\n",
        "    private fun maybeTruncateToolOutput(\n"
        "        toolCallId: String,\n"
        "        output: List<UIMessagePart>,\n"
        "        toolName: String? = null,\n"
        "    ): List<UIMessagePart> {\n"
        "        // " + MARK + ": search_web 的结果 UI 依赖完整 JSON 结构, 不参与截断 (上游 #2000)\n"
        "        if (toolName != null && toolName in TOOLS_WITHOUT_OUTPUT_TRUNCATION) return output\n",
        "a1-func",
        failures,
    )
    return text, None


def a2(text, failures):
    text = apply(
        text,
        "                val payload = json.parseToJsonElement(line).jsonObject\n",
        "                // " + MARK + ": 部分中转在流中夹 data: null 行, 非对象行直接跳过 (上游 #2137)\n"
        "                val payload = json.parseToJsonElement(line).jsonObjectOrNull ?: return@forEach\n",
        "a2-payload",
        failures,
    )
    text = apply(
        text,
        "            val incoming = element.jsonObject\n",
        "            val incoming = element.jsonObjectOrNull ?: return@forEachIndexed\n",
        "a2-reasoning",
        failures,
    )
    return text, None


def a4_role(text, failures):
    text = apply(
        text,
        "    @SerialName(\"tool\")\n"
        "    TOOL,\n"
        "}\n",
        "    @SerialName(\"tool\")\n"
        "    TOOL,\n"
        "    ;\n"
        "\n"
        "    companion object {\n"
        "        // " + MARK + ": 宽松匹配 role, 部分中转返回空/非标值, 匹配不到返回 null (上游 1575d179d)\n"
        "        fun fromValueOrNull(value: String?): MessageRole? =\n"
        "            entries.firstOrNull { it.name.equals(value, ignoreCase = true) }\n"
        "    }\n"
        "}\n",
        "a4-enum",
        failures,
    )
    return text, None


def a4_decoder(text, failures):
    text = apply(
        text,
        "        val role = MessageRole.valueOf(\n"
        "            payload[\"role\"]?.jsonPrimitive?.contentOrNull?.uppercase() ?: \"ASSISTANT\"\n"
        "        )\n",
        "        val role = MessageRole.fromValueOrNull(\n"
        "            payload[\"role\"]?.jsonPrimitiveOrNull?.contentOrNull\n"
        "        ) ?: MessageRole.ASSISTANT\n",
        "a4-decoder",
        failures,
    )
    return text, None


def a4_api(text, failures):
    text = apply(
        text,
        "        val role = MessageRole.valueOf(\n"
        "            jsonObject[\"role\"]?.jsonPrimitive?.contentOrNull?.uppercase() ?: \"ASSISTANT\"\n"
        "        )\n",
        "        val role = MessageRole.fromValueOrNull(\n"
        "            jsonObject[\"role\"]?.jsonPrimitiveOrNull?.contentOrNull\n"
        "        ) ?: MessageRole.ASSISTANT\n",
        "a4-api",
        failures,
    )
    return text, None


A3_FUNCTION = (
    "    // " + MARK + ": OpenRouter 没有 /images/edits, 参考图改走图像生成接口的 input_references (移植上游 85af5b910)\n"
    "    @OptIn(ExperimentalEncodingApi::class)\n"
    "    private suspend fun editImageWithInputReferences(\n"
    "        providerSetting: ProviderSetting.OpenAI,\n"
    "        params: ImageEditParams,\n"
    "        key: String,\n"
    "    ): List<ImageGenerationItem> = withContext(Dispatchers.IO) {\n"
    "        val requestBody = json.encodeToString(\n"
    "            buildJsonObject {\n"
    "                put(\"model\", params.model.modelId)\n"
    "                put(\"prompt\", params.prompt)\n"
    "                put(\"n\", params.numOfImages)\n"
    "                put(\n"
    "                    \"size\",\n"
    "                    when (params.aspectRatio) {\n"
    "                        ImageAspectRatio.SQUARE -> \"1024x1024\"\n"
    "                        ImageAspectRatio.LANDSCAPE -> \"1536x1024\"\n"
    "                        ImageAspectRatio.PORTRAIT -> \"1024x1536\"\n"
    "                    }\n"
    "                )\n"
    "                putJsonArray(\"input_references\") {\n"
    "                    params.images.forEach { path ->\n"
    "                        val imageFile = File(path)\n"
    "                        require(imageFile.exists()) {\n"
    "                            \"Image file does not exist: $path\"\n"
    "                        }\n"
    "                        addJsonObject {\n"
    "                            put(\"type\", \"image_url\")\n"
    "                            putJsonObject(\"image_url\") {\n"
    "                                put(\n"
    "                                    \"url\",\n"
    "                                    \"data:${imageFile.imageMediaType()};base64,${Base64.encode(imageFile.readBytes())}\"\n"
    "                                )\n"
    "                            }\n"
    "                        }\n"
    "                    }\n"
    "                }\n"
    "            }.mergeCustomBody(params.customBody)\n"
    "        )\n"
    "\n"
    "        val request = Request.Builder()\n"
    "            .url(\"${providerSetting.baseUrl}/images/generations\")\n"
    "            .headers(params.customHeaders.toHeaders())\n"
    "            .addHeader(\"Authorization\", \"Bearer $key\")\n"
    "            .post(requestBody.toRequestBody(\"application/json\".toMediaType()))\n"
    "            .configureReferHeaders(providerSetting.baseUrl)\n"
    "            .build()\n"
    "\n"
    "        val response = client.newCall(request).await()\n"
    "        if (!response.isSuccessful) {\n"
    "            error(\"Failed to edit image: ${response.code} ${response.body?.string()}\")\n"
    "        }\n"
    "        parseImageResponse(response.body.string())\n"
    "    }\n"
    "\n"
)


def a3(text, failures):
    text = apply(
        text,
        "import kotlinx.serialization.json.putJsonArray\n",
        "import kotlinx.serialization.json.putJsonArray\n"
        "import kotlinx.serialization.json.putJsonObject\n",
        "a3-import-put",
        failures,
    )
    text = apply(
        text,
        "import kotlinx.serialization.json.add\n",
        "import kotlinx.serialization.json.add\n"
        "import kotlinx.serialization.json.addJsonObject\n",
        "a3-import-add",
        failures,
    )
    text = apply(
        text,
        "import okhttp3.OkHttpClient\n",
        "import okhttp3.HttpUrl.Companion.toHttpUrlOrNull\n"
        "import okhttp3.OkHttpClient\n",
        "a3-import-http",
        failures,
    )
    text = apply(
        text,
        "        val key = keyRoulette.next(providerSetting.apiKey, providerSetting.id.toString())\n"
        "        val bodyBuilder = MultipartBody.Builder()\n",
        "        val key = keyRoulette.next(providerSetting.apiKey, providerSetting.id.toString())\n"
        "\n"
        "        // " + MARK + ": OpenRouter 无 /images/edits 端点, 参考图走图像生成接口 (上游 85af5b910)\n"
        "        if (providerSetting.baseUrl.toHttpUrlOrNull()?.host?.lowercase() == \"openrouter.ai\") {\n"
        "            editImageWithInputReferences(providerSetting, params, key).forEach { emit(it) }\n"
        "            return@flow\n"
        "        }\n"
        "\n"
        "        val bodyBuilder = MultipartBody.Builder()\n",
        "a3-branch",
        failures,
    )
    text = apply(
        text,
        "    private suspend fun parseImageResponse(bodyStr: String): List<ImageGenerationItem> {\n",
        A3_FUNCTION +
        "    private suspend fun parseImageResponse(bodyStr: String): List<ImageGenerationItem> {\n",
        "a3-function",
        failures,
    )
    return text, None


def balanced(path):
    text = read(path)
    return text.count("{") == text.count("}")


def main():
    failures = []

    # ---- A1: GenerationHandler.kt
    text = read(GH)
    if "TOOLS_WITHOUT_OUTPUT_TRUNCATION" in text:
        log("already:a1")
    else:
        text, err = a1(text, failures)
        if not failures or all(not f.startswith("anchor:a1") for f in failures):
            write(GH, text)
            log("applied:a1")

    # ---- A2 + A4(decoder): ChatCompletionsStreamDecoder.kt
    text = read(DEC)
    if "json.parseToJsonElement(line).jsonObjectOrNull" in text:
        log("already:a2")
    else:
        text, err = a2(text, failures)
        if not any(f.startswith("anchor:a2") for f in failures):
            write(DEC, text)
            log("applied:a2")
    text = read(DEC)
    if "fromValueOrNull" in text and "MessageRole.valueOf(" not in text:
        log("already:a4-decoder")
    else:
        text, err = a4_decoder(text, failures)
        if not any(f == "a4-decoder" or f.startswith("anchor:a4-decoder") for f in failures):
            write(DEC, text)
            log("applied:a4-decoder")

    # ---- A4: MessageRole.kt
    text = read(ROLE)
    if "fromValueOrNull" in text:
        log("already:a4-enum")
    else:
        text, err = a4_role(text, failures)
        if not any(f.startswith("anchor:a4-enum") for f in failures):
            write(ROLE, text)
            log("applied:a4-enum")

    # ---- A4: ChatCompletionsAPI.kt
    text = read(API)
    if "fromValueOrNull" in text:
        log("already:a4-api")
    else:
        text, err = a4_api(text, failures)
        if not any(f.startswith("anchor:a4-api") for f in failures):
            write(API, text)
            log("applied:a4-api")

    # ---- A3: OpenAIProvider.kt
    text = read(PRV)
    if "editImageWithInputReferences" in text:
        log("already:a3")
    else:
        text, err = a3(text, failures)
        if not any(f.startswith("anchor:a3") for f in failures):
            write(PRV, text)
            log("applied:a3")

    # ---- 复核: 最终态 probe + 括号平衡
    checks = [
        ("a1-present", "TOOLS_WITHOUT_OUTPUT_TRUNCATION" in read(GH)),
        ("a1-toolname", "maybeTruncateToolOutput(tool.toolCallId, result, tool.toolName)" in read(GH)),
        ("a2-present", "json.parseToJsonElement(line).jsonObjectOrNull" in read(DEC)),
        ("a2-reasoning", "val incoming = element.jsonObjectOrNull" in read(DEC)),
        ("a3-present", "editImageWithInputReferences" in read(PRV)),
        ("a3-host-check", 'host?.lowercase() == "openrouter.ai"' in read(PRV)),
        ("a4-enum", "fromValueOrNull" in read(ROLE)),
        ("a4-decoder", "fromValueOrNull" in read(DEC) and "MessageRole.valueOf(" not in read(DEC)),
        ("a4-api", "fromValueOrNull" in read(API) and "MessageRole.valueOf(" not in read(API)),
        ("braces-gh", balanced(GH)),
        ("braces-dec", balanced(DEC)),
        ("braces-api", balanced(API)),
        ("braces-prv", balanced(PRV)),
        ("braces-role", balanced(ROLE)),
    ]
    for name, ok in checks:
        log("check:" + name + ":" + ("ok" if ok else "FAIL"))
        if not ok:
            failures.append("check:" + name)

    if failures:
        log("RESULT:FAIL")
        log("failures:" + "|".join(failures))
        print("::error title=upfix381::anchor/check failures: " + ",".join(failures))
    else:
        log("RESULT:OK")

    with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()

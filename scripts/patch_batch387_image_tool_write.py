#!/usr/bin/env python3
# rhImageId387: 真正写入 ImageGenerationTool.kt（386 只检查、未落盘）
# 关键：Kotlin 源码用 Python raw 三引号，换行是真实换行，文件内反斜杠数为 0。
import os, sys
from pathlib import Path

ROOT = Path(os.environ.get("GITHUB_WORKSPACE") or ".")
P = ROOT / "app/src/main/java/me/rerere/rikkahub/data/ai/tools/local/ImageGenerationTool.kt"
D = ROOT / "ci_diag_batch387_tool.txt"
OUT = []

SRC = r'''package me.rerere.rikkahub.data.ai.tools.local

import kotlinx.serialization.json.add
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import kotlinx.serialization.json.putJsonObject
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.Tool
import me.rerere.ai.ui.ImageAspectRatio
import me.rerere.ai.ui.UIMessagePart
import me.rerere.rikkahub.data.ai.ImageGenerationService
import me.rerere.rikkahub.utils.RhImageIdRegistry
import org.koin.core.context.GlobalContext

/**
 * rhImageId382: every saved picture is registered under a stable SHA-256 id, and the ids
 * are returned inside the result envelope. That lets the model bring hop back into the
 * reply body with the `!img[<id>]` marker instead of leaving it buried in this tool call.
 */
fun createImageGenerationTool(): Tool = Tool(
    name = "generate_image",
    description = "Generate images from a text prompt with the user's configured image model. " +
        "The images are saved to the app gallery and shown to the user in the chat. " +
        "Write a detailed visual prompt (subject, style, composition, lighting). " +
        "Each call costs the user money; do not call it repeatedly without being asked.",
    parameters = {
        InputSchema.Obj(
            properties = buildJsonObject {
                putJsonObject("prompt") {
                    put("type", "string")
                    put("description", "Detailed description of the image to create")
                }
                putJsonObject("count") {
                    put("type", "integer")
                    put("description", "Number of images, 1-4 (default 1)")
                }
                putJsonObject("aspect_ratio") {
                    put("type", "string")
                    put("description", "Aspect ratio (default " + ImageAspectRatio.SQUARE.name + ")")
                    putJsonArray("enum") { ImageAspectRatio.entries.forEach { add(it.name) } }
                }
            },
            required = listOf("prompt"),
        )
    },
    execute = { input ->
        val args = input.jsonObject
        val prompt = args["prompt"]?.jsonPrimitive?.contentOrNull?.trim()
        if (prompt.isNullOrBlank()) {
            return@Tool listOf(UIMessagePart.Text(fmErrEnvelope("missing_prompt", "prompt is required")))
        }
        val count = (args["count"]?.jsonPrimitive?.intOrNull ?: 1).coerceIn(1, 4)
        val rawRatio = args["aspect_ratio"]?.jsonPrimitive?.contentOrNull
        val ratio = ImageAspectRatio.entries.firstOrNull { it.name.equals(rawRatio, ignoreCase = true) }
            ?: ImageAspectRatio.SQUARE
        val service = GlobalContext.get().get<ImageGenerationService>()
        val images = runCatching { service.generateForTool(prompt, count, ratio) }
            .getOrElse { error ->
                if (error is kotlinx.coroutines.CancellationException) throw error
                return@Tool listOf(
                    UIMessagePart.Text(fmErrEnvelope("generation_failed", error.message ?: error.toString()))
                )
            }
        if (images.isEmpty()) {
            return@Tool listOf(UIMessagePart.Text(fmErrEnvelope("no_image", "The image model returned no image")))
        }
        val idPairs = images.mapNotNull { image ->
            RhImageIdRegistry.register(image.filePath)?.let { id -> id to image.filePath }
        }
        images.map { UIMessagePart.Image(url = "file://" + it.filePath) } + UIMessagePart.Text(
            buildJsonObject {
                put("success", true)
                put("count", images.size)
                put("saved_to_gallery", true)
                put("model", images.first().model)
                putJsonArray("paths") { images.forEach { add(it.filePath) } }
                putJsonArray("image_ids") { idPairs.forEach { pair -> add(pair.first) } }
                put(
                    "how_to_show",
                    "The picture already sits inside this tool call, which the user usually does not open. " +
                        "To show it again in the reply body, write the marker !img[<id>] on its own line, " +
                        "using the exact id from image_ids. It renders as the real image. " +
                        "Never invent an id and never paste file paths to the user."
                )
                put("note", "The images are already displayed to the user. Do not paste the paths unless asked.")
            }.toString()
        )
    },
)
'''

try:
    OUT.appendbefor(0) if False else None
    P.write_text(SRC, encoding="utf-8")
    OUT.append("wrote:" + str(len(SRC)))
    OUT.append("backslash:" + str(SRC.count(chr(92))))
    OUT.append("paren:" + str(SRC.count("(") - SRC.count(")")))
    OUT.append("brace:" + str(SRC.count("{") - SRC.count("}")))
except Exception as exc:
    OUT.append("EX:" + repr(exc))
    print("::error title=b387::" + repr(exc))

D.write_text("\n".join(OUT) + "\n", encoding="utf-8")
sys.exit(0)

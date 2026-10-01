package me.rerere.rikkahub.data.ai.tools.local

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
import org.koin.core.context.GlobalContext

/**
 * `generate_image` - lets the assistant create pictures with the image model selected on
 * the image creation page. Images are saved to the gallery and shown inline in the chat.
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
                    put("description", "Aspect ratio (default ${ImageAspectRatio.SQUARE.name})")
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
        images.map { UIMessagePart.Image(url = "file://${it.filePath}") } + UIMessagePart.Text(
            buildJsonObject {
                put("success", true)
                put("count", images.size)
                put("saved_to_gallery", true)
                put("model", images.first().model)
                putJsonArray("paths") { images.forEach { add(it.filePath) } }
                put("note", "The images are already displayed to the user. Do not paste the paths unless asked.")
            }.toString()
        )
    },
)

package me.rerere.rikkahub.data.ai.tools

import kotlinx.serialization.json.JsonObjectBuilder
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.Tool
import me.rerere.ai.ui.DiffMetadata
import me.rerere.ai.ui.UIMessagePart
import me.rerere.ai.ui.toMetadata
import me.rerere.rikkahub.data.files.FilesManager
import me.rerere.rikkahub.data.repository.WorkspaceRepository
import me.rerere.rikkahub.utils.generateUnifiedDiff
import me.rerere.workspace.WorkspaceFileEntry
import me.rerere.workspace.WorkspaceTreeResult
import org.koin.java.KoinJavaComponent.getKoin
import java.io.ByteArrayOutputStream

private const val MAX_READ_FILE_BYTES = 8L * 1024 * 1024

val WorkspaceToolDefaultApprovals: Map<String, Boolean> = mapOf(
    "workspace_read_file" to false,
    "workspace_write_file" to false,
    "workspace_edit_file" to false,
    "workspace_create_folder" to false,
    "workspace_read_folder" to false,
)

fun resolveWorkspaceToolApproval(name: String, overrides: Map<String, Boolean>): Boolean {
    if (name !in WorkspaceToolDefaultApprovals) return false
    return overrides[name] ?: WorkspaceToolDefaultApprovals.getValue(name)
}

suspend fun createWorkspaceTools(
    workspaceId: String?,
    workspaceRepository: WorkspaceRepository,
    cwd: String? = null,
): List<Tool> {
    if (workspaceId.isNullOrBlank()) return emptyList()
    val approvalOverrides = workspaceRepository.getById(workspaceId)?.toolApprovalOverrides().orEmpty()
    fun needsApproval(name: String) = resolveWorkspaceToolApproval(name, approvalOverrides)

    return listOf(
        createReadFileTool(workspaceId, ::needsApproval, workspaceRepository),
        createWriteFileTool(workspaceId, ::needsApproval, workspaceRepository),
        createEditFileTool(workspaceId, ::needsApproval, workspaceRepository),
        createCreateFolderTool(workspaceId, ::needsApproval, workspaceRepository),
        createReadFolderTool(workspaceId, ::needsApproval, workspaceRepository),
    )
}

private val IMAGE_EXTENSIONS = setOf(
    "png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "heic", "heif", "avif", "ico",
)

private fun String.isImagePath(): Boolean =
    substringAfterLast('.', "").lowercase() in IMAGE_EXTENSIONS

private fun createReadFileTool(
    workspaceId: String,
    needsApproval: (String) -> Boolean,
    workspaceRepository: WorkspaceRepository,
) = Tool(
    name = "workspace_read_file",
    description = "Read a UTF-8 text or image file from the assistant's bound file workspace. Use a path relative to the workspace root.",
    parameters = {
        InputSchema.Obj(
            properties = buildJsonObject { putPathProperty(required = true) },
            required = listOf("path"),
        )
    },
    needsApproval = { needsApproval("workspace_read_file") },
    execute = {
        val path = it.jsonObject.workspacePath("path")
        if (path.isImagePath()) {
            readImageFile(workspaceId, path, workspaceRepository)
        } else {
            val text = workspaceRepository.readText(workspaceId, path)
            listOf(UIMessagePart.Text(buildJsonObject {
                put("path", path)
                put("text", text)
            }.toString()))
        }
    },
)

private fun createWriteFileTool(
    workspaceId: String,
    needsApproval: (String) -> Boolean,
    workspaceRepository: WorkspaceRepository,
) = Tool(
    name = "workspace_write_file",
    description = "Write a UTF-8 text file in the assistant's bound file workspace. The path is relative to the workspace root.",
    parameters = {
        InputSchema.Obj(
            properties = buildJsonObject {
                putPathProperty(required = true)
                put("text", buildJsonObject {
                    put("type", "string")
                    put("description", "UTF-8 text content to write")
                })
                put("overwrite", buildJsonObject {
                    put("type", "boolean")
                    put("description", "Whether to overwrite an existing file. Defaults to true.")
                })
            },
            required = listOf("path", "text"),
        )
    },
    needsApproval = { needsApproval("workspace_write_file") },
    execute = {
        val params = it.jsonObject
        val path = params.workspacePath("path")
        val text = params.string("text") ?: error("text is required")
        val overwrite = params["overwrite"]?.jsonPrimitive?.contentOrNull?.toBooleanStrictOrNull() ?: true
        val entry = workspaceRepository.writeText(workspaceId, path, text, overwrite)
        listOf(UIMessagePart.Text(entry.toJson().toString()))
    },
)

private fun createEditFileTool(
    workspaceId: String,
    needsApproval: (String) -> Boolean,
    workspaceRepository: WorkspaceRepository,
) = Tool(
    name = "workspace_edit_file",
    description = "Edit a UTF-8 text file in the assistant's bound file workspace using old_text and new_text. The path is relative to the workspace root.",
    parameters = {
        InputSchema.Obj(
            properties = buildJsonObject {
                putPathProperty(required = true)
                put("old_text", buildJsonObject {
                    put("type", "string")
                    put("description", "Exact text to replace")
                })
                put("new_text", buildJsonObject {
                    put("type", "string")
                    put("description", "Replacement text")
                })
                put("replace_all", buildJsonObject {
                    put("type", "boolean")
                    put("description", "Whether to replace every occurrence. Defaults to false.")
                })
            },
            required = listOf("path", "old_text", "new_text"),
        )
    },
    needsApproval = { needsApproval("workspace_edit_file") },
    execute = {
        val params = it.jsonObject
        val path = params.workspacePath("path")
        val oldText = params.string("old_text") ?: error("old_text is required")
        val newText = params.string("new_text") ?: error("new_text is required")
        val replaceAll = params["replace_all"]?.jsonPrimitive?.contentOrNull?.toBooleanStrictOrNull() ?: false
        require(oldText.isNotEmpty()) { "old_text must not be empty" }

        val original = workspaceRepository.readText(workspaceId, path)
        val result = try {
            replaceText(original, oldText, newText, replaceAll)
        } catch (e: IllegalArgumentException) {
            error("${e.message} (path: $path)")
        }
        val entry = workspaceRepository.writeText(workspaceId, path, result.updated, overwrite = true)
        val diff = generateUnifiedDiff(original, result.updated, entry.path)
        listOf(UIMessagePart.Text(
            text = buildJsonObject {
                put("path", entry.path)
                put("replacements", result.replacements)
                if (result.strategy != ExactReplacer.name) put("matchStrategy", result.strategy)
                put("sizeBytes", entry.sizeBytes)
                put("updatedAt", entry.updatedAt)
            }.toString(),
            metadata = diff?.let { DiffMetadata(diff = it).toMetadata() },
        ))
    },
)

private fun createCreateFolderTool(
    workspaceId: String,
    needsApproval: (String) -> Boolean,
    workspaceRepository: WorkspaceRepository,
) = Tool(
    name = "workspace_create_folder",
    description = "Create a directory and any missing parents in the bound file workspace. The path is relative to the workspace root.",
    parameters = {
        InputSchema.Obj(
            properties = buildJsonObject { putPathProperty(required = true) },
            required = listOf("path"),
        )
    },
    needsApproval = { needsApproval("workspace_create_folder") },
    execute = {
        val path = it.jsonObject.workspacePath("path")
        val entry = workspaceRepository.createFolder(workspaceId, path)
        listOf(UIMessagePart.Text(entry.toJson().toString()))
    },
)

private fun createReadFolderTool(
    workspaceId: String,
    needsApproval: (String) -> Boolean,
    workspaceRepository: WorkspaceRepository,
) = Tool(
    name = "workspace_read_folder",
    description = "Recursively list a directory in the bound file workspace as an indented tree. The path is relative to the workspace root.",
    parameters = {
        InputSchema.Obj(
            properties = buildJsonObject { putPathProperty(required = true) },
            required = listOf("path"),
        )
    },
    needsApproval = { needsApproval("workspace_read_folder") },
    execute = {
        val path = it.jsonObject.workspacePath("path")
        val result = workspaceRepository.readFolderTree(workspaceId, path = path)
        listOf(UIMessagePart.Text(formatWorkspaceTree(path, result)))
    },
)

private suspend fun readImageFile(
    workspaceId: String,
    path: String,
    repository: WorkspaceRepository,
): List<UIMessagePart> {
    val bytes = ByteArrayOutputStream().also { repository.exportFile(workspaceId, me.rerere.workspace.WorkspaceStorageArea.FILES, path, it) }.toByteArray()
    require(bytes.size <= MAX_READ_FILE_BYTES) { "Image is too large to read: $path" }
    val filesManager = getKoin().get<FilesManager>()
    val uris = filesManager.createChatFilesByByteArrays(listOf(bytes))
    return listOf(
        UIMessagePart.Image(url = uris.first().toString()),
        UIMessagePart.Text(buildJsonObject {
            put("path", path)
            put("description", "Image file read successfully")
        }.toString()),
    )
}

private fun kotlinx.serialization.json.JsonObject.string(name: String): String? =
    this[name]?.jsonPrimitive?.contentOrNull

private fun kotlinx.serialization.json.JsonObject.workspacePath(name: String): String {
    val raw = string(name)?.replace('\\', '/')?.trim() ?: error("$name is required")
    require(raw.isNotBlank()) { "$name is required" }
    require(!raw.contains('\u0000')) { "$name contains invalid character" }
    val normalized = raw.removePrefix("/workspace/").removePrefix("/workspace").trim('/')
    if (normalized.isBlank()) return "."
    require(normalized.split('/').none { it.isEmpty() || it == "." || it == ".." }) {
        "$name must stay inside the workspace"
    }
    return normalized
}

private fun JsonObjectBuilder.putPathProperty(required: Boolean) {
    put("path", buildJsonObject {
        put("type", "string")
        put("description", if (required) "Path relative to the file workspace root." else "Optional path relative to the file workspace root.")
    })
}

/** 纯函数：把递归目录树格式化为紧凑的缩进文本。 */
internal fun formatWorkspaceTree(rootPath: String, result: WorkspaceTreeResult): String = buildString {
    append(rootPath.trimEnd('/').ifEmpty { "." }).append('/')
    if (result.entries.isEmpty()) {
        append(if (result.truncated) " (empty, truncated)" else " (empty)")
        return@buildString
    }
    result.entries.forEach { entry ->
        append('\n')
        append("  ".repeat(entry.depth))
        append(entry.name)
        if (entry.isDirectory) append('/') else append(" (").append(entry.sizeBytes).append(" bytes)")
    }
    if (result.truncated) {
        append('\n')
        append("... (truncated: showing ${result.entries.size} entries; narrow the path for a complete listing)")
    }
}

private fun WorkspaceFileEntry.toJson() = buildJsonObject {
    put("path", path)
    put("name", name)
    put("isDirectory", isDirectory)
    put("sizeBytes", sizeBytes)
    put("updatedAt", updatedAt)
}

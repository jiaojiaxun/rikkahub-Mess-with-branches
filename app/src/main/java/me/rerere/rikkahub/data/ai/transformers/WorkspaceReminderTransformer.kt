package me.rerere.rikkahub.data.ai.transformers

import android.util.Log
import kotlinx.coroutines.CancellationException
import me.rerere.ai.core.MessageRole
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart
import me.rerere.rikkahub.data.db.entity.WorkspaceEntity
import me.rerere.rikkahub.data.repository.WorkspaceRepository
import me.rerere.workspace.WorkspaceStorageArea

/**
 * 将已绑定的持久文件工作区及其安全文件工具加入系统提示，
 * 并读取工作区根目录与当前目录中的 AGENTS.md 作为工作区指令（对应上游 2.5.2 2689e753）。
 *
 * 与上游的差异：本分支的工作区是纯文件区（没有 Linux rootfs / ~/.agents），
 * 因此只读取 `AGENTS.md` 与 `<cwd>/AGENTS.md`，并做截断保护。
 */
class WorkspaceReminderTransformer(
    private val workspaceRepository: WorkspaceRepository,
) : InputMessageTransformer {
    override suspend fun transform(
        ctx: TransformerContext,
        messages: List<UIMessage>,
    ): List<UIMessage> {
        val workspaceId = ctx.assistant.workspaceId?.toString()
        val workspace = workspaceId?.let { workspaceRepository.getById(it) }
        val hasAnyWorkspace = workspace != null || workspaceRepository.getAll().isNotEmpty()
        val reminder = buildWorkspaceReminder(workspace, hasAnyWorkspace, ctx.workspaceCwd)
            ?: return messages
        val prompt = if (workspace != null && workspaceId != null) {
            reminder + buildAgentsPrompt(workspaceId, ctx.workspaceCwd)
        } else {
            reminder
        }

        val systemIndex = messages.indexOfFirst { it.role == MessageRole.SYSTEM }
        return if (systemIndex >= 0) {
            messages.toMutableList().apply {
                this[systemIndex] = this[systemIndex].appendText("\n\n$prompt")
            }
        } else {
            listOf(UIMessage.system(prompt)) + messages
        }
    }

    private suspend fun buildAgentsPrompt(workspaceId: String, cwd: String?): String {
        var budget = MAX_TOTAL_CHARS
        val sections = mutableListOf<Pair<String, String>>()
        for (path in agentsCandidatePaths(cwd)) {
            if (budget <= 0) break
            val content = try {
                val size = workspaceRepository.fileSize(workspaceId, WorkspaceStorageArea.FILES, path)
                if (size <= 0L || size > MAX_FILE_BYTES) null
                else workspaceRepository.readText(workspaceId, path)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                Log.d(TAG, "Skipping workspace instructions $path: ${e.message}")
                null
            }
            val text = content?.trim()?.takeIf { it.isNotEmpty() } ?: continue
            val limit = minOf(MAX_FILE_CHARS, budget)
            val clipped = if (text.length > limit) {
                text.take(limit) + "\n...[truncated, ${text.length - limit} more characters]"
            } else {
                text
            }
            budget -= clipped.length
            sections += path to clipped
        }
        if (sections.isEmpty()) return ""
        return buildString {
            appendLine()
            appendLine()
            appendLine("<workspace_instructions>")
            appendLine("Follow the AGENTS.md instructions below.")
            sections.forEach { (path, text) ->
                appendLine()
                appendLine("AGENTS.md source: $path")
                appendLine(text)
            }
            append("</workspace_instructions>")
        }
    }

    private companion object {
        const val TAG = "WorkspaceReminder"
        const val MAX_FILE_BYTES = 256L * 1024
        const val MAX_FILE_CHARS = 8_000
        const val MAX_TOTAL_CHARS = 16_000
    }
}

/** 纯函数：AGENTS.md 候选路径（相对工作区根）。含 `..` 的 cwd 忽略，不允许跳出工作区。 */
internal fun agentsCandidatePaths(cwd: String?): List<String> {
    val segments = cwd
        ?.trim()
        ?.removePrefix("/workspace")
        ?.split('/')
        ?.filter { it.isNotEmpty() && it != "." }
        .orEmpty()
    val relative = segments.takeIf { s -> s.none { it == ".." } }?.joinToString("/").orEmpty()
    return if (relative.isEmpty()) listOf("AGENTS.md") else listOf("AGENTS.md", "$relative/AGENTS.md")
}

/** 纯函数：生成当前绑定工作区的模型可见说明。 */
internal fun buildWorkspaceReminder(
    workspace: WorkspaceEntity?,
    hasAnyWorkspace: Boolean,
    cwd: String? = null,
): String? = when {
    workspace != null -> buildWorkspacePrompt(workspace, cwd)
    hasAnyWorkspace -> buildWorkspaceUnboundPrompt()
    else -> null
}

private fun buildWorkspacePrompt(workspace: WorkspaceEntity, cwd: String? = null): String = buildString {
    appendLine("<workspace>")
    appendLine("You have access to a persistent file workspace named \"${workspace.name}\".")
    appendLine("- Use paths relative to the workspace root; files persist across turns of this conversation.")
    appendLine("- Available tools:")
    appendLine("  - `workspace_read_file`: read UTF-8 text or image files.")
    appendLine("  - `workspace_write_file` / `workspace_edit_file`: create files or make precise edits.")
    appendLine("  - `workspace_create_folder`: create a directory and missing parents.")
    appendLine("  - `workspace_read_folder`: recursively list a directory as an indented tree.")
    appendLine("- Do not execute operating-system commands or assume background-task capabilities.")
    if (!cwd.isNullOrBlank()) appendLine("- Current working directory for file operations: `$cwd`.")
    append("</workspace>")
}

private fun buildWorkspaceUnboundPrompt(): String = buildString {
    appendLine("<workspace-setup>")
    appendLine("The user has a file workspace, but none is bound to this assistant, so workspace file tools are not available in this conversation.")
    appendLine("If the user asks to save or inspect files, explain in the user's language how to bind a workspace from the chat input workspace selector.")
    appendLine("Do not claim to have workspace file tools until a workspace is bound.")
    append("</workspace-setup>")
}

private fun UIMessage.appendText(extra: String): UIMessage {
    val updatedParts = parts.toMutableList()
    val firstTextIndex = updatedParts.indexOfFirst { it is UIMessagePart.Text }
    if (firstTextIndex >= 0) {
        val text = updatedParts[firstTextIndex] as UIMessagePart.Text
        updatedParts[firstTextIndex] = text.copy(text = text.text + extra)
    } else {
        updatedParts.add(UIMessagePart.Text(extra))
    }
    return copy(parts = updatedParts)
}

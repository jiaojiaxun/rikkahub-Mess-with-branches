package me.rerere.rikkahub.data.ai.transformers

import me.rerere.ai.core.MessageRole
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart
import me.rerere.rikkahub.data.db.entity.WorkspaceEntity
import me.rerere.rikkahub.data.repository.WorkspaceRepository

/** 将已绑定的持久文件工作区及其安全文件工具加入系统提示。 */
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
        val prompt = buildWorkspaceReminder(workspace, hasAnyWorkspace, ctx.workspaceCwd)
            ?: return messages

        val systemIndex = messages.indexOfFirst { it.role == MessageRole.SYSTEM }
        return if (systemIndex >= 0) {
            messages.toMutableList().apply {
                this[systemIndex] = this[systemIndex].appendText("\n\n$prompt")
            }
        } else {
            listOf(UIMessage.system(prompt)) + messages
        }
    }
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

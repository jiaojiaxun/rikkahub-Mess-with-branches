package me.rerere.rikkahub.data.ai.transformers

import android.util.Log
import kotlinx.coroutines.CancellationException
import me.rerere.ai.core.MessageRole
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart
import me.rerere.rikkahub.data.db.entity.WorkspaceEntity
import me.rerere.rikkahub.data.repository.WorkspaceRepository
import me.rerere.workspace.WorkspaceLayout
import me.rerere.workspace.WorkspaceStorageArea
import java.io.ByteArrayOutputStream
import java.util.concurrent.ConcurrentHashMap

/**
 * 将已绑定的持久工作区及其工具说明加入系统提示。
 *
 * 本地工作区: 保留 fork 现有行为(纯文件区提示 + AGENTS.md 指令)。
 * 远程 SSH 工作区: 注入远程环境信息(shell/发行版)、非沙箱警告、工具指引;
 * shell 与发行版读到一次后缓存, 连不上时只注入说明不阻塞对话。
 */
class WorkspaceReminderTransformer(
    private val workspaceRepository: WorkspaceRepository,
) : InputMessageTransformer {
    private val remoteEnvironments = RemoteEnvironmentCache()

    override suspend fun transform(
        ctx: TransformerContext,
        messages: List<UIMessage>,
    ): List<UIMessage> {
        val workspaceId = ctx.assistant.workspaceId?.toString()
        val workspace = workspaceId?.let { workspaceRepository.getById(it) }

        // SSH 分支: 不读 AGENTS.md (每步少几次远程往返), 只注入环境说明
        if (workspace != null && workspaceId != null && workspace.isSsh()) {
            val layout = workspaceRepository.layout(workspaceId) ?: return messages
            val prompt = try {
                val environment = remoteEnvironments.get(workspaceId, workspace.sshConfig) {
                    RemoteEnvironment(
                        shell = workspaceRepository.shell(workspaceId),
                        distro = readDistroName(workspaceId),
                    )
                }.getOrElse { e ->
                    Log.w(TAG, "SSH workspace unreachable: $workspaceId", e)
                    return messages.withPrompt(buildUnreachablePrompt(workspace, layout, e))
                }
                buildSshWorkspacePrompt(workspace, layout, environment.shell, environment.distro, ctx.workspaceCwd)
            } catch (e: CancellationException) {
                throw e
            }
            return messages.withPrompt(prompt)
        }

        // 本地分支: fork 现有逻辑
        val hasAnyWorkspace = workspace != null || workspaceRepository.getAll().isNotEmpty()
        val reminder = buildWorkspaceReminder(workspace, hasAnyWorkspace, ctx.workspaceCwd)
            ?: return messages
        val prompt = if (workspace != null && workspaceId != null) {
            reminder + buildAgentsPrompt(workspaceId, ctx.workspaceCwd)
        } else {
            reminder
        }
        return messages.withPrompt(prompt)
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

    private suspend fun readDistroName(workspaceId: String): String? =
        OS_RELEASE_PATHS.firstNotNullOfOrNull { path ->
            readRemoteText(workspaceId, path, MAX_OS_RELEASE_BYTES)?.let(::parseOsReleaseName)
        }

    // 文件不存在、过大或不可读时返回 null, 不影响提示词的其余部分
    private suspend fun readRemoteText(workspaceId: String, path: String, maxBytes: Long): String? = try {
        val size = workspaceRepository.rootfsFileSize(workspaceId, path)
        require(size <= maxBytes) { "$path exceeds $maxBytes bytes" }
        val content = ByteArrayOutputStream().use { output ->
            workspaceRepository.exportRootfsFile(workspaceId, path, output)
            output.toString(Charsets.UTF_8.name())
        }
        content.takeIf { it.isNotBlank() }
    } catch (e: CancellationException) {
        throw e
    } catch (e: Exception) {
        Log.d(TAG, "Skipping remote workspace file: $path", e)
        null
    }

    private companion object {
        const val TAG = "WorkspaceReminder"
        const val MAX_FILE_BYTES = 256L * 1024
        const val MAX_FILE_CHARS = 8_000
        const val MAX_TOTAL_CHARS = 16_000
        const val MAX_OS_RELEASE_BYTES = 16L * 1024
        val OS_RELEASE_PATHS = listOf("/etc/os-release", "/usr/lib/os-release")
    }
}

/** 远程工作区提示词里描述的执行环境 */
internal data class RemoteEnvironment(val shell: String, val distro: String?)

/**
 * 按工作区缓存远程执行环境。
 *
 * 读一次要好几次网络往返, 而每一步请求都要构建提示词; 远程环境很少变化, 读到后就一直沿用,
 * 直到连接配置改变。连不上的结果只保留 [failureTtlMillis]: 期间的后续步骤不必每步都等连接超时,
 * 过期后再重新尝试。
 */
internal class RemoteEnvironmentCache(
    private val failureTtlMillis: Long = DEFAULT_FAILURE_TTL_MS,
    private val now: () -> Long = { System.nanoTime() / 1_000_000 },
) {
    private class Entry(val config: String?, val result: Result<RemoteEnvironment>, val loadedAt: Long)

    private val entries = ConcurrentHashMap<String, Entry>()

    suspend fun get(
        workspaceId: String,
        config: String?,
        load: suspend () -> RemoteEnvironment,
    ): Result<RemoteEnvironment> {
        entries[workspaceId]
            ?.takeIf { it.config == config && (it.result.isSuccess || now() - it.loadedAt < failureTtlMillis) }
            ?.let { return it.result }
        val result = try {
            Result.success(load())
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Result.failure(e)
        }
        entries[workspaceId] = Entry(config, result, now())
        return result
    }

    private companion object {
        const val DEFAULT_FAILURE_TTL_MS = 60_000L
    }
}

private const val MAX_DISTRO_NAME_LENGTH = 80

/** 从 os-release 内容中取发行版名称, 优先 PRETTY_NAME, 其次 NAME + VERSION_ID */
internal fun parseOsReleaseName(content: String): String? {
    val values = content.lineSequence()
        .map { it.trim() }
        .filter { !it.startsWith("#") && it.indexOf('=') > 0 }
        .associate { line ->
            line.substringBefore('=') to line.substringAfter('=').trim().removeSurrounding("\"").removeSurrounding("'")
        }
    val name = values["PRETTY_NAME"]?.takeIf { it.isNotBlank() }
        ?: listOfNotNull(values["NAME"], values["VERSION_ID"]).joinToString(" ")
    // 内容来自远程机器的文件, 拼进系统提示前去掉控制字符并限制长度
    return name.filterNot { it.isISOControl() }.trim().take(MAX_DISTRO_NAME_LENGTH).ifBlank { null }
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
    appendLine("- Use paths relative to the workspace base; files persist across turns of this conversation.")
    appendLine("- Available tools:")
    appendLine("  - `workspace_read_file`: read UTF-8 text or image files.")
    appendLine("  - `workspace_write_file` / `workspace_edit_file`: create files or make precise edits.")
    appendLine("  - `workspace_create_folder`: create a directory and missing parents.")
    appendLine("  - `workspace_read_folder`: recursively list a directory as an indented tree.")
    appendLine("- Do not execute operating-system commands or assume background-task capabilities.")
    if (!cwd.isNullOrBlank()) appendLine("- Current working directory for file operations: `$cwd`.")
    append("</workspace>")
}

private fun buildSshWorkspacePrompt(
    workspace: WorkspaceEntity,
    layout: WorkspaceLayout,
    shell: String,
    distro: String?,
    cwd: String?,
): String = buildString {
    val address = workspace.sshSettings()?.let { "${it.username}@${it.host}" } ?: "the remote host"
    appendLine("<workspace>")
    appendLine(
        "You have access to a persistent remote workspace named \"${workspace.name}\" on a real machine, reached over SSH as `$address`."
    )
    appendLine(
        "- The workspace directory is `${layout.workspaceDir}`. Use it as your working directory; files written there persist across turns of this conversation."
    )
    appendLine(
        "- All paths passed to workspace tools must be absolute paths on the remote machine (for example `${layout.workspaceDir}/notes.md`)."
    )
    appendLine(
        "- This is not a sandbox: commands run with the SSH user's real permissions and can affect other data and services on the machine. Avoid destructive or system-wide changes unless the user asks for them."
    )
    if (distro != null) {
        appendLine("- The remote operating system is $distro.")
    }
    appendShellLine(shell)
    appendLine("- Available tools:")
    appendLine("  - `workspace_read_file`: read file contents.")
    appendLine("  - `workspace_shell`: run shell commands on the remote machine (defaults to the workspace directory).")
    appendLine(
        "- There are no file write or edit tools in this workspace. Create and modify files with `workspace_shell`, for example a quoted heredoc (`cat > file <<'EOF'`) for new content, or `sed`, `patch` or a short script for targeted edits. Prefer targeted edits over rewriting whole files."
    )
    if (!cwd.isNullOrBlank()) {
        appendLine(
            "- Current working directory: `$cwd`. Use this as the default context for file operations and shell commands."
        )
    }
    append("</workspace>")
}

private fun buildUnreachablePrompt(workspace: WorkspaceEntity, layout: WorkspaceLayout, error: Throwable): String =
    buildString {
        val address = workspace.sshSettings()?.let { "${it.username}@${it.host}" }
        appendLine("<workspace>")
        appendLine(
            "You are bound to a workspace named \"${workspace.name}\"" +
                (address?.let { " on `$it`" } ?: "") +
                " with directory `${layout.workspaceDir}`, but it is currently unreachable: ${error.message}"
        )
        appendLine(
            "- Workspace tools will fail until the connection is restored. If the user asks you to work in the workspace, tell them it is unreachable."
        )
        append("</workspace>")
    }

private fun StringBuilder.appendShellLine(shell: String) {
    if (shell.substringAfterLast('/') == "bash") {
        appendLine("- `workspace_shell` runs commands with `$shell`.")
    } else {
        appendLine(
            "- `workspace_shell` runs commands with `$shell`, a POSIX shell. Bash is not installed, so avoid bash-only syntax such as arrays, here-strings (`<<<`) and brace expansion."
        )
    }
}

private fun buildWorkspaceUnboundPrompt(): String = buildString {
    appendLine("<workspace-setup>")
    appendLine("The user has a file workspace, but none is bound to this assistant, so workspace file tools are not available in this conversation.")
    appendLine("If the user asks to save or inspect files, explain in the user's language how to bind a workspace from the chat input workspace selector.")
    appendLine("Do not claim to have workspace file tools until a workspace is bound.")
    append("</workspace-setup>")
}

private fun List<UIMessage>.withPrompt(prompt: String): List<UIMessage> {
    val systemIndex = indexOfFirst { it.role == MessageRole.SYSTEM }
    return if (systemIndex >= 0) {
        toMutableList().apply {
            this[systemIndex] = this[systemIndex].appendText("\n\n$prompt")
        }
    } else {
        listOf(UIMessage.system(prompt)) + this
    }
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

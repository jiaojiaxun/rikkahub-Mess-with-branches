package me.rerere.rikkahub.data.ai.tools

import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.Tool
import me.rerere.ai.ui.UIMessagePart
import me.rerere.rikkahub.data.repository.WorkspaceRepository

/**
 * 临时安装入口: 在详情页 UI 移植完成前, 让 AI 能通过一个工具把 Linux rootfs
 * 装进绑定的工作区, 使 workspace_shell 立即可用。后续 UI 批次可评估去留。
 */
fun createInstallRootfsTool(
    workspaceId: String,
    needsApproval: (String) -> Boolean,
    workspaceRepository: WorkspaceRepository,
) = Tool(
    name = "workspace_install_rootfs",
    description = "Download and install a Linux rootfs tarball (tar.gz / tar.xz) into the assistant's bound workspace, enabling workspace_shell. Pass an absolute http(s) URL of an Alpine minirootfs or a similar rootfs archive. Long-running; returns when the install finishes.",
    parameters = {
        InputSchema.Obj(
            properties = buildJsonObject {
                put("url", buildJsonObject {
                    put("type", "string")
                    put("description", "Absolute http(s) URL of the rootfs tarball")
                })
            },
            required = listOf("url"),
        )
    },
    needsApproval = { needsApproval("workspace_install_rootfs") },
    execute = {
        val url = it.jsonObject["url"]?.jsonPrimitive?.contentOrNull ?: error("url is required")
        workspaceRepository.installRootfs(workspaceId, url)
        listOf(
            UIMessagePart.Text(
                buildJsonObject {
                    put("status", "installed")
                }.toString()
            )
        )
    },
)

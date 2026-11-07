package me.rerere.ai.core

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import me.rerere.ai.provider.Model
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart

@Serializable
data class Tool(
    val name: String,
    val description: String,
    val parameters: () -> InputSchema? = { null },
    val systemPrompt: (model: Model, messages: List<UIMessage>) -> String = { _, _ -> "" },
    val needsApproval: (JsonElement) -> Boolean = { false },
    /**
     * rhApprovalIdentity: 审批身份键。默认 = 工具名；复合工具（如 rikkahub_apply_change）
     * 覆盖为 "工具名@子动作"，把「始终允许」细化到动作粒度。同一键既用于授权
     * 存储，也用于自动放行判定（见 ToolApprovalIdentity）。args 解析失败必须回落工具名。
     */
    val approvalKey: (JsonObject) -> String = { name },
    val execute: suspend (JsonElement) -> List<UIMessagePart>
)

@Serializable
sealed class InputSchema {
    @Serializable
    @SerialName("object")
    data class Obj(
        val properties: JsonObject,
        val required: List<String>? = null,
    ) : InputSchema()
}

package me.rerere.ai.core

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

@Serializable
enum class MessageRole {
    @SerialName("system")
    SYSTEM,

    @SerialName("user")
    USER,

    @SerialName("assistant")
    ASSISTANT,

    @SerialName("tool")
    TOOL,
    ;

    companion object {
        // upfix381: 宽松匹配 role, 部分中转返回空/非标值, 匹配不到返回 null (上游 1575d179d)
        fun fromValueOrNull(value: String?): MessageRole? =
            entries.firstOrNull { it.name.equals(value, ignoreCase = true) }
    }
}

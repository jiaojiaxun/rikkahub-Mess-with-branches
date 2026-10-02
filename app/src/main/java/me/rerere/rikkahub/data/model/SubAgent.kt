package me.rerere.rikkahub.data.model

import kotlinx.serialization.Serializable

/**
 * 子代理会话（独立于主会话，有自己的生命周期）
 */
@Serializable
data class SubAgentSession(
    val id: String,
    val parentConversationId: String,  // 所属主会话
    val name: String,  // 子代理名称（显示用）
    val objective: String,  // 目标/任务描述
    val status: SubAgentStatus = SubAgentStatus.PENDING,
    val createdAt: Long = System.currentTimeMillis(),
    val startedAt: Long? = null,
    val completedAt: Long? = null,
    val result: String? = null,  // 完成后的结果摘要
    val messages: List<SubAgentMessage> = emptyList(),  // 独立的对话历史
)

@Serializable
enum class SubAgentStatus {
    PENDING,    // 等待执行
    RUNNING,    // 执行中
    COMPLETED,  // 已完成
    FAILED,     // 失败
    CANCELLED,  // 已取消
}

@Serializable
data class SubAgentMessage(
    val id: String,
    val role: MessageRole,  // user / assistant / system
    val content: String,
    val timestamp: Long = System.currentTimeMillis(),
    val toolCalls: List<ToolCall> = emptyList(),
)

@Serializable
enum class MessageRole {
    USER,
    ASSISTANT,
    SYSTEM,
}

@Serializable
data class ToolCall(
    val id: String,
    val name: String,
    val arguments: String,
    val result: String? = null,
    val status: ToolCallStatus = ToolCallStatus.PENDING,
)

@Serializable
enum class ToolCallStatus {
    PENDING,
    RUNNING,
    COMPLETED,
    FAILED,
}

/**
 * 子代理管理器（负责创建、执行、销毁子代理会话）
 */
interface SubAgentManager {
    /**
     * 创建子代理会话
     */
    fun createSession(
        parentConversationId: String,
        name: String,
        objective: String,
    ): SubAgentSession

    /**
     * 启动子代理执行（异步）
     */
    fun startSession(sessionId: String)

    /**
     * 取消子代理
     */
    fun cancelSession(sessionId: String)

    /**
     * 删除子代理会话
     */
    fun deleteSession(sessionId: String)

    /**
     * 获取主会话的所有子代理
     */
    fun getSessions(parentConversationId: String): List<SubAgentSession>

    /**
     * 获取单个子代理详情
     */
    fun getSession(sessionId: String): SubAgentSession?

    /**
     * 同批次并行执行多个子代理
     */
    fun startBatch(sessionIds: List<String>)
}

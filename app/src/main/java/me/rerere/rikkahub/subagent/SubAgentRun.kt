package me.rerere.rikkahub.subagent

import kotlinx.serialization.Serializable
import kotlin.uuid.Uuid

/**
 * 子代理运行记录（移植自 AAAelina/rikkahub-agent，适配 fork）。
 * 内存 v1：只在进程内活（SubAgentRegistry StateFlow），不持久化。
 */
@Serializable
data class SubAgentRun(
    val id: String,
    val parentChatId: String?,
    val parentAssistantId: String,
    val label: String,
    val task: String,
    val modelId: String?,
    val tools: List<String>?,
    val runInBackground: Boolean,
    val timeoutSeconds: Int,
    val maxTrips: Int,
    val status: SubAgentStatus,
    val result: String? = null,
    val error: String? = null,
    val startedAtMs: Long,
    val finishedAtMs: Long? = null,
    val tokensIn: Long = 0,
    val tokensOut: Long = 0,
    val tripCount: Int = 0,
)

@Serializable
enum class SubAgentStatus {
    PENDING, RUNNING, SUCCEEDED, FAILED, TIMED_OUT, CANCELLED,
}

object SubAgentDefaults {
    const val DEFAULT_TIMEOUT_SECONDS = 300
    const val MAX_TIMEOUT_SECONDS = 1800
    const val DEFAULT_MAX_TRIPS = 12
    const val MAX_MAX_TRIPS = 30
    const val MAX_LABEL_LENGTH = 60
    const val GLOBAL_CONCURRENCY_CAP = 8
    const val MIN_PER_ASSISTANT_CAP = 1
    const val MAX_PER_ASSISTANT_CAP = 4
    const val REGISTRY_LRU_CAP = 50

    val DEFAULT_SYSTEM_PROMPT = """
        You are a focused sub-agent dispatched by a parent assistant to complete a single
        task and return a concise summary.

        Rules:
        - Stay tightly scoped to the task you were given. Do not expand scope.
        - Use tools to gather facts before answering when accuracy matters.
        - Return a clear, structured final summary as your last message — that summary is
          what the parent will see. Aim for 100-500 words unless the task asks otherwise.
        - If the task is impossible, return a single short paragraph explaining why.
        - Do not ask the parent for clarification — make the best judgment call you can
          and proceed.
    """.trimIndent()
}

@Serializable
data class SubAgentRequest(
    val task: String,
    val modelId: String? = null,
    val systemPrompt: String? = null,
    val tools: List<String>? = null,
    val runInBackground: Boolean = false,
    val timeoutSeconds: Int = SubAgentDefaults.DEFAULT_TIMEOUT_SECONDS,
    val maxTrips: Int = SubAgentDefaults.DEFAULT_MAX_TRIPS,
    val label: String? = null,
)

enum class SubAgentPromptSource { REQUEST, ASSISTANT, DEFAULT }

/** 分发时冻结的执行契约：模型/提示词/工具面/行程上限。 */
data class SubAgentExecutionProfile(
    val runId: String,
    val effectiveModelId: Uuid,
    val promptSource: SubAgentPromptSource,
    val effectiveSystemPrompt: String,
    val effectiveToolNames: Set<String>,
    val maxToolTrips: Int,
)

internal fun SubAgentExecutionProfile.allowsTool(toolName: String): Boolean =
    toolName in effectiveToolNames

object SubAgentRequestValidator {
    sealed class Result {
        data class Ok(val request: SubAgentRequest) : Result()
        data class Reject(val error: String, val detail: String) : Result()
    }

    fun validate(request: SubAgentRequest): Result {
        val task = request.task.trim()
        if (task.isEmpty()) return Result.Reject("invalid_task", "task is required and may not be blank")
        if (request.timeoutSeconds < 1) return Result.Reject("invalid_timeout", "timeout_seconds must be at least 1")
        if (request.timeoutSeconds > SubAgentDefaults.MAX_TIMEOUT_SECONDS) return Result.Reject("invalid_timeout", "timeout_seconds exceeds max ${SubAgentDefaults.MAX_TIMEOUT_SECONDS}; got ${request.timeoutSeconds}")
        if (request.maxTrips < 1) return Result.Reject("invalid_max_trips", "max_trips must be at least 1")
        if (request.maxTrips > SubAgentDefaults.MAX_MAX_TRIPS) return Result.Reject("invalid_max_trips", "max_trips exceeds max ${SubAgentDefaults.MAX_MAX_TRIPS}; got ${request.maxTrips}")
        request.label?.let {
            if (it.length > SubAgentDefaults.MAX_LABEL_LENGTH) return Result.Reject("invalid_label", "label exceeds ${SubAgentDefaults.MAX_LABEL_LENGTH} chars")
        }
        return Result.Ok(request.copy(task = task))
    }
}

sealed interface SubAgentExecutionProfileResolution {
    data class Resolved(val profile: SubAgentExecutionProfile) : SubAgentExecutionProfileResolution
    data class Rejected(val error: String, val detail: String) : SubAgentExecutionProfileResolution
}

/**
 * 把请求覆盖解析成一份冻结的子运行 profile。fork 适配：无 CapabilityCatalog/
 * ToolNameSnapshot，工具面用调用方传入的可用集做交集；提示词链 REQUEST→
 * ASSISTANT（父助手 systemPrompt）→DEFAULT。
 */
fun resolveSubAgentExecutionProfile(
    runId: String,
    request: SubAgentRequest,
    parentEffectiveModelId: Uuid,
    assistantDefaultModelId: Uuid?,
    assistantSystemPrompt: String,
    availableModelIds: Set<Uuid>,
    callerToolNames: Set<String>,
): SubAgentExecutionProfileResolution {
    val requestedModelId = request.modelId?.trim()?.takeIf(String::isNotEmpty)?.let { raw ->
        runCatching { Uuid.parse(raw) }.getOrElse {
            return SubAgentExecutionProfileResolution.Rejected("invalid_model_id", "model_id is not a valid UUID")
        }
    }
    val effectiveModelId = requestedModelId ?: assistantDefaultModelId ?: parentEffectiveModelId
    if (effectiveModelId !in availableModelIds) {
        return SubAgentExecutionProfileResolution.Rejected("unknown_model", "the selected child model is not available")
    }

    val requestedPrompt = request.systemPrompt?.trim().orEmpty()
    val assistantPrompt = assistantSystemPrompt.trim()
    val (promptSource, prompt) = when {
        requestedPrompt.isNotEmpty() -> SubAgentPromptSource.REQUEST to requestedPrompt
        assistantPrompt.isNotEmpty() -> SubAgentPromptSource.ASSISTANT to assistantPrompt
        else -> SubAgentPromptSource.DEFAULT to SubAgentDefaults.DEFAULT_SYSTEM_PROMPT
    }

    // fork 适配：请求工具必须全部在调用方工具面内；未指定则继承全部。
    val requestedTools = request.tools?.map(String::trim)?.filter(String::isNotEmpty)?.distinct()
    requestedTools?.forEach { toolName ->
        if (toolName !in callerToolNames) {
            return SubAgentExecutionProfileResolution.Rejected(
                "tool_not_authorized",
                "the parent turn did not expose tool: $toolName",
            )
        }
    }
    val effectiveTools = requestedTools?.toSet() ?: callerToolNames

    return SubAgentExecutionProfileResolution.Resolved(
        SubAgentExecutionProfile(
            runId = runId,
            effectiveModelId = effectiveModelId,
            promptSource = promptSource,
            effectiveSystemPrompt = prompt,
            effectiveToolNames = effectiveTools,
            maxToolTrips = request.maxTrips,
        ),
    )
}

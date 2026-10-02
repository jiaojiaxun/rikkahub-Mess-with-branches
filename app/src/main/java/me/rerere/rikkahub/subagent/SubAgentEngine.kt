package me.rerere.rikkahub.subagent

import android.util.Log
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import me.rerere.ai.ui.UIMessagePart
import me.rerere.rikkahub.AppScope
import me.rerere.rikkahub.data.datastore.SettingsStore
import me.rerere.rikkahub.data.datastore.getCurrentChatModel
import me.rerere.rikkahub.data.model.Conversation
import me.rerere.rikkahub.data.repository.ConversationRepository
import me.rerere.rikkahub.service.ChatService
import kotlin.uuid.Uuid

private const val TAG = "SubAgentEngine"

/**
 * 子代理引擎（移植自 AAAelina/rikkahub-agent，fork 适配版 v2）。
 *
 * 相对第一版的修复：
 * 1. 修复非法 Kotlin 标签语法（`} dispatchRecovery@ {` → 正常 `else`）。
 * 2. Assistant 字段名实称为 systemPrompt（不是 prompt）。
 * 3. ChatService 惰性解析改用 koin-core GlobalContext（不依赖 koin-java 工件）。
 * 4. 工具面不再硬编码集合——子对话复用父助手，自然继承其工具开关；
 *    callerToolNames 传空集表示「不做请求级工具过滤」。
 *
 * fork 适配（相对 AAAelina 原版）：无 AgentRunRepository 台账、无
 * HeadlessConversations/submitUserMessageTracked，改用 public API：
 * insertConversation → initializeConversation → sendMessage →
 * generationDoneFlow（先订阅后发送，避免 SharedFlow 无重放导致快完成丢事件）。
 */
class SubAgentEngine(
    private val registry: SubAgentRegistry,
    private val conversationRepo: ConversationRepository,
    private val settingsStore: SettingsStore,
    private val appScope: AppScope,
) {
    // 惰性解析打断 DI 环：ChatService → LocalTools → SubAgentEngine → ChatService。
    private val chatService: ChatService by lazy {
        org.koin.core.context.GlobalContext.get().get<ChatService>()
    }

    /** 引擎创建的对话集合（递归防护）。 */
    private val subAgentConversationIds = java.util.concurrent.ConcurrentHashMap.newKeySet<Uuid>()

    sealed class DispatchResult {
        data class Ok(val run: SubAgentRun) : DispatchResult()
        data class Reject(val error: String, val detail: String) : DispatchResult()
    }

    suspend fun dispatch(
        parentAssistantId: Uuid,
        parentConversationId: Uuid?,
        request: SubAgentRequest,
    ): DispatchResult = withContext(Dispatchers.Default) {
        // 递归防护：父对话本身是子代理对话时拒绝
        if (parentConversationId != null && parentConversationId in subAgentConversationIds) {
            return@withContext DispatchResult.Reject(
                "no_recursion",
                "sub-agent dispatch is not allowed from inside another sub-agent run",
            )
        }

        val validation = SubAgentRequestValidator.validate(request)
        if (validation is SubAgentRequestValidator.Result.Reject) {
            return@withContext DispatchResult.Reject(validation.error, validation.detail)
        }
        val cleaned = (validation as SubAgentRequestValidator.Result.Ok).request

        val settings = settingsStore.settingsFlow.first { !it.init }
        val parentAssistant = settings.assistants.firstOrNull { it.id == parentAssistantId }
            ?: return@withContext DispatchResult.Reject(
                "unknown_parent_assistant",
                "caller assistant no longer exists",
            )

        val runId = Uuid.random().toString()
        val parentEffectiveModelId = parentAssistant.chatModelId
            ?: settings.getCurrentChatModel()?.id
            ?: return@withContext DispatchResult.Reject(
                "no_model_available",
                "no model is available for the child run",
            )
        val availableModelIds = settings.providers
            .asSequence()
            .filter { it.enabled }
            .flatMap { it.models.asSequence() }
            .map { it.id }
            .toSet()

        val profile = when (val resolution = resolveSubAgentExecutionProfile(
            runId = runId,
            request = cleaned,
            parentEffectiveModelId = parentEffectiveModelId,
            assistantDefaultModelId = null,
            assistantSystemPrompt = parentAssistant.systemPrompt,
            availableModelIds = availableModelIds,
            callerToolNames = emptySet(),
        )) {
            is SubAgentExecutionProfileResolution.Resolved -> resolution.profile
            is SubAgentExecutionProfileResolution.Rejected ->
                return@withContext DispatchResult.Reject(resolution.error, resolution.detail)
        }

        val initialRun = SubAgentRun(
            id = runId,
            parentChatId = parentConversationId?.toString(),
            parentAssistantId = parentAssistantId.toString(),
            label = cleaned.label?.takeIf { it.isNotBlank() } ?: cleaned.task.take(60),
            task = cleaned.task,
            modelId = profile.effectiveModelId.toString(),
            tools = profile.effectiveToolNames.sorted(),
            runInBackground = cleaned.runInBackground,
            timeoutSeconds = cleaned.timeoutSeconds,
            maxTrips = profile.maxToolTrips,
            status = SubAgentStatus.PENDING,
            startedAtMs = System.currentTimeMillis(),
        )
        when (registry.reservePending(initialRun, SubAgentDefaults.GLOBAL_CONCURRENCY_CAP, SubAgentDefaults.MAX_PER_ASSISTANT_CAP)) {
            SubAgentRegistry.Reservation.RESERVED -> Unit
            SubAgentRegistry.Reservation.GLOBAL_CAP -> return@withContext DispatchResult.Reject("global_cap_reached", "global concurrency cap reached")
            SubAgentRegistry.Reservation.ASSISTANT_CAP -> return@withContext DispatchResult.Reject("assistant_cap_reached", "assistant concurrency cap reached")
            SubAgentRegistry.Reservation.DUPLICATE -> return@withContext DispatchResult.Reject("duplicate_run", "run already reserved")
        }

        val executionJob = appScope.launch(Dispatchers.IO, start = CoroutineStart.LAZY) {
            try {
                executeRun(runId, parentAssistantId, cleaned, profile)
            } finally {
                withContext(NonCancellable) {
                    val status = registry.get(runId)?.status
                    if (status == SubAgentStatus.PENDING || status == SubAgentStatus.RUNNING) {
                        registry.terminalizeIfActive(runId, SubAgentStatus.CANCELLED, "execution_ended_before_terminal")
                    }
                    registry.clearJob(runId)
                }
            }
        }
        registry.setJob(runId, executionJob)
        executionJob.start()

        if (cleaned.runInBackground) {
            DispatchResult.Ok(registry.get(runId) ?: initialRun)
        } else {
            // 前台：阻塞到终态
            executionJob.join()
            DispatchResult.Ok(registry.get(runId) ?: initialRun)
        }
    }

    private suspend fun executeRun(
        runId: String,
        parentAssistantId: Uuid,
        request: SubAgentRequest,
        profile: SubAgentExecutionProfile,
    ) {
        registry.update(runId) { it.copy(status = SubAgentStatus.RUNNING) }

        val conversation = Conversation.ofId(
            id = Uuid.random(),
            assistantId = parentAssistantId,
            newConversation = true,
        ).copy(
            title = "[Sub-agent] ${request.label?.take(40) ?: request.task.take(40)}",
            // fork 适配：Conversation.customSystemPrompt 承载子代理有效提示词，
            // chatModelId 承载有效模型；子对话复用父助手 → 工具开关自然继承。
            customSystemPrompt = profile.effectiveSystemPrompt,
            chatModelId = profile.effectiveModelId,
        )

        // 先订阅后发送：generationDoneFlow 是无重放的 SharedFlow，
        // 若发送后才订阅，快速完成的生成可能丢掉完成事件导致白等到超时。
        val done = CompletableDeferred<Unit>()
        val observer = appScope.launch {
            chatService.generationDoneFlow.collect { id ->
                if (id == conversation.id) done.complete(Unit)
            }
        }

        try {
            conversationRepo.insertConversation(conversation)
            chatService.initializeConversation(conversation.id)
            subAgentConversationIds.add(conversation.id)

            val taskWithWrapup = buildString {
                append(request.task)
                appendLine()
                appendLine()
                append(
                    "When finished, end with one concise plain-text summary. Do not stop on " +
                        "a tool call: the dispatcher exposes only your final assistant reply.",
                )
            }
            chatService.sendMessage(
                conversation.id,
                listOf(UIMessagePart.Text(taskWithWrapup)),
                true,
            )

            // v1 限制：超时只标记 run 为 TIMED_OUT，不取消底层生成（fork 的
            // ChatService 没有对 UI 层外安全的按对话停止 API）。
            val completed = withTimeoutOrNull(request.timeoutSeconds * 1000L) { done.await() }
            if (completed == null) {
                registry.terminalizeIfActive(runId, SubAgentStatus.TIMED_OUT, "exceeded ${request.timeoutSeconds}-second cap")
                return
            }

            val finalText = harvestFinalText(conversation.id)
            if (finalText.isBlank()) {
                registry.terminalizeIfActive(runId, SubAgentStatus.FAILED, "empty_final_answer")
                return
            }
            registry.update(runId) {
                it.copy(
                    status = SubAgentStatus.SUCCEEDED,
                    result = finalText,
                    finishedAtMs = System.currentTimeMillis(),
                )
            }
        } catch (cancellation: CancellationException) {
            registry.terminalizeIfActive(runId, SubAgentStatus.CANCELLED, "cancelled")
            throw cancellation
        } catch (failure: Throwable) {
            Log.w(TAG, "sub-agent run $runId failed", failure)
            registry.terminalizeIfActive(runId, SubAgentStatus.FAILED, failure.message ?: "execution_failed")
        } finally {
            subAgentConversationIds.remove(conversation.id)
            observer.cancel()
        }
    }

    private suspend fun harvestFinalText(conversationId: Uuid): String {
        val conversation = chatService.getConversationFlow(conversationId).first()
        return selectSubAgentFinalText(conversation.currentMessages)
    }
}

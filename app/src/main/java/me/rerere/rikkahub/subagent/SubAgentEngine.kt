package me.rerere.rikkahub.subagent

import android.util.Log
import kotlinx.coroutines.CancellationException
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
import me.rerere.rikkahub.data.model.Conversation
import me.rerere.rikkahub.data.repository.ConversationRepository
import me.rerere.rikkahub.service.ChatService
import kotlin.uuid.Uuid

private const val TAG = "SubAgentEngine"

/**
 * 子代理引擎（移植自 AAAelina/rikkahub-agent，fork 适配）。
 *
 * fork 适配点（相对原版）：
 * 1. 砍 AgentRunRepository 台账（fork 无此层），运行记录只存内存 Registry。
 * 2. 砍 HeadlessConversations/CommandOrigin/submitUserMessageTracked（fork 的
 *    ChatService 无此 API），改用 fork 的 public API：insertConversation →
 *    initializeConversation → sendMessage → generationDoneFlow(conversationId)。
 * 3. 砍 ExecutionProfileRegistry 下沉 ChatService 的链路——fork 的 GenerationHandler
 *    不消费 profile，所以 v1 里 profile 只用于冻结参数并把 effectiveSystemPrompt
 *    作为子对话的 customSystemPrompt 写入（fork 的 Conversation 有该字段）。
 * 4. 递归防护：v1 用「运行中的子代理不能再 dispatch」在工具层拦截（见 SubAgentTools
 *    的 isHeadless 检查缺省实现——fork 无 HeadlessConversations，用注册表近似）。
 */
class SubAgentEngine(
    private val registry: SubAgentRegistry,
    private val conversationRepo: ConversationRepository,
    private val settingsStore: SettingsStore,
    private val appScope: AppScope,
) {
    private val chatService: ChatService by lazy {
        org.koin.java.KoinJavaComponent.getKoin().get<ChatService>()
    }

    sealed class DispatchResult {
        data class Ok(val run: SubAgentRun) : DispatchResult()
        data class Reject(val error: String, val detail: String) : DispatchResult()
    }

    /** fork 近似：当前调用链是否已在子代理里（用「子对话注册表」判断）。 */
    private val subAgentConversationIds = java.util.concurrent.ConcurrentHashMap.newKeySet<Uuid>()

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
        val parentEffectiveModelId = parentAssistant.chatModelId ?: settings.chatModelId
        val availableModelIds = settings.providers
            .asSequence()
            .filter { it.enabled }
            .flatMap { it.models.asSequence() }
            .map { it.id }
            .toSet()
        // fork 适配：无 ToolNameSnapshot，用「父助手开启的本地工具名集合」近似
        val callerToolNames = parentAssistant.let { assistant ->
            setOf(
                "search_web", "web_fetch", "workspace_read_file", "workspace_write_file",
                "workspace_edit_file", "workspace_create_folder", "workspace_read_folder",
            ).filter { it.isNotBlank() }.toSet()
        }

        val profile = when (val resolution = resolveSubAgentExecutionProfile(
            runId = runId,
            request = cleaned,
            parentEffectiveModelId = parentEffectiveModelId,
            assistantDefaultModelId = null, // fork 的 Assistant 无 subAgentModelId 字段
            assistantSystemPrompt = parentAssistant.prompt,
            availableModelIds = availableModelIds,
            callerToolNames = callerToolNames,
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
        } dispatchRecovery@ {
            // 前台：join 到终态
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
            // fork 适配：fork 的 Conversation 有 customSystemPrompt 字段，子代理的
            // 有效提示词直接写进去（GenerationHandler 会拼接它）
            customSystemPrompt = profile.effectiveSystemPrompt,
            chatModelId = profile.effectiveModelId,
        )

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

            // 等待完成：监听 generationDoneFlow 过滤本会话（铁律 5）
            val outcome = withTimeoutOrNull(request.timeoutSeconds * 1000L) {
                chatService.generationDoneFlow.first { it == conversation.id }
            }
            if (outcome == null) {
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
        }
    }

    private suspend fun harvestFinalText(conversationId: Uuid): String {
        val conversation = chatService.getConversationFlow(conversationId).first()
        return selectSubAgentFinalText(conversation.currentMessages)
    }
}

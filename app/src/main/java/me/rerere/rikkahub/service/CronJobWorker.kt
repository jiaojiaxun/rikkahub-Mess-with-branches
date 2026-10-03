package me.rerere.rikkahub.service

import android.content.Context
import android.util.Log
import androidx.work.CoroutineWorker
import androidx.work.WorkerParameters
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull
import me.rerere.ai.ui.UIMessagePart
import me.rerere.rikkahub.AppScope
import me.rerere.rikkahub.data.cron.CronJobStore
import me.rerere.rikkahub.data.cron.ScheduledJobRunRecord
import me.rerere.rikkahub.data.datastore.SettingsStore
import me.rerere.rikkahub.data.datastore.getCurrentAssistant
import me.rerere.rikkahub.data.model.Conversation
import me.rerere.rikkahub.data.model.CronJob
import me.rerere.rikkahub.data.repository.ConversationRepository
import kotlin.uuid.Uuid

private const val TAG = "CronJobWorker"
private const val GENERATION_TIMEOUT_MS = 600_000L

/**
 * 定时任务执行器（fork 适配版）：触发时把 prompt 发到目标会话并等生成完成。
 *
 * v1 限制（诚实声明）：
 * - 生成等待上限固定 10 分钟；超时只记录 timeout，不取消生成。
 * - conversationId 只做解析不做存在性校验（会话被删则 sendMessage 失败，记为 failure）。
 */
class CronJobWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    override suspend fun doWork(): Result {
        val jobId = inputData.getString(KEY_JOB_ID) ?: return Result.failure()
        val manual = inputData.getBoolean(KEY_MANUAL, false)

        val koin = org.koin.core.context.GlobalContext.get()
        val store = koin.get<CronJobStore>()
        val scheduler = koin.get<CronJobScheduler>()
        val conversationRepo = koin.get<ConversationRepository>()
        val settingsStore = koin.get<SettingsStore>()
        val chatService = koin.get<ChatService>()
        val appScope = koin.get<AppScope>()

        val job = store.jobs().firstOrNull { it.id == jobId }
        if (job == null) {
            Log.w(TAG, "cron job $jobId not found; cancelling pending work")
            scheduler.cancel(jobId)
            return Result.failure()
        }
        if (!manual && !job.enabled) {
            scheduler.cancel(jobId)
            return Result.success()
        }

        val now = System.currentTimeMillis()
        if (!manual) {
            store.upsert(job.copy(lastRunAt = now))
        }

        var outcome = "success"
        var errorText: String? = null
        try {
            val conversationId = resolveConversationId(job, conversationRepo, settingsStore, chatService)

            // 先订阅后发送（SharedFlow 无重放，快完成会丢事件）
            val done = CompletableDeferred<Unit>()
            val observer = appScope.launch {
                chatService.generationDoneFlow.collect { id ->
                    if (id == conversationId) done.complete(Unit)
                }
            }
            try {
                chatService.sendMessage(
                    conversationId,
                    listOf(UIMessagePart.Text(job.prompt)),
                    true,
                )
                val completed = withTimeoutOrNull(GENERATION_TIMEOUT_MS) { done.await() }
                if (completed == null) {
                    outcome = "timeout"
                    errorText = "generation did not finish within ${GENERATION_TIMEOUT_MS / 1000}s"
                }
            } finally {
                observer.cancel()
            }
        } catch (failure: Throwable) {
            outcome = "failure"
            errorText = failure.message ?: failure::class.simpleName
            Log.w(TAG, "cron job $jobId fire failed", failure)
        }

        runCatching {
            store.addHistory(
                ScheduledJobRunRecord(
                    id = Uuid.random().toString(),
                    jobId = job.id,
                    jobName = job.name,
                    scheduledAtMs = now,
                    startedAtMs = now,
                    finishedAtMs = System.currentTimeMillis(),
                    outcome = outcome,
                    error = errorText,
                )
            )
        }

        // 续期：常规触发后重新计算下次时间；手动触发不碰常规调度
        if (!manual) {
            runCatching {
                val latest = store.jobs().firstOrNull { it.id == job.id } ?: job
                scheduler.schedule(latest)
            }.onFailure { Log.w(TAG, "cron job $jobId reschedule failed", it) }
        }
        return Result.success()
    }

    private suspend fun resolveConversationId(
        job: CronJob,
        conversationRepo: ConversationRepository,
        settingsStore: SettingsStore,
        chatService: ChatService,
    ): Uuid {
        val existing = job.conversationId
            ?.let { runCatching { Uuid.parse(it) }.getOrNull() }
        if (existing != null) return existing

        // 新开对话：conversationId 为 null 的任务每次触发都新建会话
        val settings = settingsStore.settingsFlow.first { !it.init }
        val assistantId = job.assistantId
            ?.let { runCatching { Uuid.parse(it) }.getOrNull() }
            ?: settings.getCurrentAssistant().id
        val conversation = Conversation.ofId(
            id = Uuid.random(),
            assistantId = assistantId,
            newConversation = true,
        ).copy(title = "[定时] ${job.name.take(40)}")
        conversationRepo.insertConversation(conversation)
        chatService.initializeConversation(conversation.id)
        return conversation.id
    }

    companion object {
        const val KEY_JOB_ID = "job_id"
        const val KEY_MANUAL = "manual"
    }
}

package me.rerere.rikkahub.service

import android.content.Context
import androidx.work.Data
import androidx.work.ExistingWorkPolicy
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import me.rerere.rikkahub.data.cron.CronJobStore
import me.rerere.rikkahub.data.model.CronJob
import me.rerere.rikkahub.data.model.CronParser
import java.util.concurrent.TimeUnit
import kotlin.math.max

/**
 * 定时任务调度器（移植自 AAAelina/rikkahub-agent 的 CronJobScheduler，fork 适配：
 * Room 仓库 → DataStore 存储；CronExpressionParser → fork 自带 CronParser）。
 *
 * 每个任务一个唯一 work 名 "cron_job_<id>"，可确定性替换/取消；
 * 周期任务在 Worker 结束时自我续期；开机/更新后由 CronBootReceiver 重建。
 */
class CronJobScheduler(
    private val context: Context,
    private val store: CronJobStore,
) {
    private val wm get() = WorkManager.getInstance(context)

    suspend fun schedule(job: CronJob) {
        val nowMs = System.currentTimeMillis()
        val nextRun = if (job.enabled) CronParser.parseNextRun(job.cronExpression, nowMs) else null
        store.upsert(job.copy(nextRunAt = nextRun))
        if (nextRun == null) {
            cancel(job.id)
            return
        }
        val delayMs = max(0L, nextRun - nowMs)
        val req = OneTimeWorkRequestBuilder<CronJobWorker>()
            .setInitialDelay(delayMs, TimeUnit.MILLISECONDS)
            .setInputData(
                Data.Builder().putString(CronJobWorker.KEY_JOB_ID, job.id).build()
            )
            .build()
        wm.enqueueUniqueWork(workNameFor(job.id), ExistingWorkPolicy.REPLACE, req)
    }

    /**
     * 立即触发（trigger_job_now）。独立 work 名 + KEY_MANUAL=true：
     * 手动触发不干扰常规调度的计数与续期。
     */
    fun triggerNow(jobId: String) {
        val req = OneTimeWorkRequestBuilder<CronJobWorker>()
            .setInitialDelay(0L, TimeUnit.MILLISECONDS)
            .setInputData(
                Data.Builder()
                    .putString(CronJobWorker.KEY_JOB_ID, jobId)
                    .putBoolean(CronJobWorker.KEY_MANUAL, true)
                    .build()
            )
            .build()
        wm.enqueueUniqueWork(manualWorkNameFor(jobId), ExistingWorkPolicy.REPLACE, req)
    }

    fun cancel(jobId: String) {
        wm.cancelUniqueWork(workNameFor(jobId))
    }

    suspend fun scheduleAllEnabled() {
        store.jobs().filter { it.enabled }.forEach { schedule(it) }
    }

    private fun workNameFor(jobId: String) = "cron_job_$jobId"
    private fun manualWorkNameFor(jobId: String) = "cron_job_${jobId}_manual"
}

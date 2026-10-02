package me.rerere.rikkahub.data.cron

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.serialization.Serializable
import me.rerere.rikkahub.data.model.CronJob
import me.rerere.rikkahub.utils.JsonInstant

private val Context.cronJobsDataStore by preferencesDataStore(name = "scheduled_cron_jobs")

/**
 * 定时任务的一次触发记录（最近 100 条）。
 */
@Serializable
data class ScheduledJobRunRecord(
    val id: String,
    val jobId: String,
    val jobName: String,
    val scheduledAtMs: Long,
    val startedAtMs: Long,
    val finishedAtMs: Long? = null,
    val outcome: String, // success | failure | timeout
    val error: String? = null,
)

/**
 * 定时任务存储（DataStore JSON，避开 Room 迁移风险）。
 * jobs：当前任务列表；history：最近 100 条触发记录。
 */
class CronJobStore(private val context: Context) {
    private val jobsKey = stringPreferencesKey("jobs_json")
    private val historyKey = stringPreferencesKey("history_json")

    val jobsFlow: Flow<List<CronJob>> = context.cronJobsDataStore.data.map { prefs ->
        prefs[jobsKey]?.let {
            runCatching { JsonInstant.decodeFromString<List<CronJob>>(it) }.getOrNull()
        } ?: emptyList()
    }

    val historyFlow: Flow<List<ScheduledJobRunRecord>> = context.cronJobsDataStore.data.map { prefs ->
        prefs[historyKey]?.let {
            runCatching { JsonInstant.decodeFromString<List<ScheduledJobRunRecord>>(it) }.getOrNull()
        } ?: emptyList()
    }

    suspend fun jobs(): List<CronJob> = jobsFlow.first()

    suspend fun history(): List<ScheduledJobRunRecord> = historyFlow.first()

    suspend fun upsert(job: CronJob) {
        context.cronJobsDataStore.edit { prefs ->
            val current = prefs[jobsKey]?.let {
                runCatching { JsonInstant.decodeFromString<List<CronJob>>(it) }.getOrNull()
            } ?: emptyList()
            val next = current.filterNot { it.id == job.id } + job
            prefs[jobsKey] = JsonInstant.encodeToString(next)
        }
    }

    suspend fun delete(jobId: String) {
        context.cronJobsDataStore.edit { prefs ->
            val current = prefs[jobsKey]?.let {
                runCatching { JsonInstant.decodeFromString<List<CronJob>>(it) }.getOrNull()
            } ?: emptyList()
            prefs[jobsKey] = JsonInstant.encodeToString(current.filterNot { it.id == jobId })
        }
    }

    suspend fun addHistory(record: ScheduledJobRunRecord) {
        context.cronJobsDataStore.edit { prefs ->
            val current = prefs[historyKey]?.let {
                runCatching { JsonInstant.decodeFromString<List<ScheduledJobRunRecord>>(it) }.getOrNull()
            } ?: emptyList()
            val next = (listOf(record) + current).take(100)
            prefs[historyKey] = JsonInstant.encodeToString(next)
        }
    }
}

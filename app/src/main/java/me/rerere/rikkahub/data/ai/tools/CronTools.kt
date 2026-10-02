package me.rerere.rikkahub.data.ai.tools

import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.Tool
import me.rerere.ai.ui.UIMessagePart
import me.rerere.rikkahub.data.cron.CronJobStore
import me.rerere.rikkahub.data.model.CronJob
import me.rerere.rikkahub.data.model.CronParser
import me.rerere.rikkahub.service.CronJobScheduler
import kotlin.uuid.Uuid

private fun errEnv(error: String, detail: String): List<UIMessagePart> {
    val obj = buildJsonObject {
        put("error", error)
        put("detail", detail)
    }
    return listOf(UIMessagePart.Text(obj.toString()))
}

private fun encodeJob(job: CronJob): kotlinx.serialization.json.JsonObject = buildJsonObject {
    put("id", job.id)
    put("name", job.name)
    put("cron", job.cronExpression)
    put("prompt", job.prompt)
    job.assistantId?.let { put("assistant_id", it) }
    job.conversationId?.let { put("conversation_id", it) }
    put("enabled", job.enabled)
    job.lastRunAt?.let { put("last_run_at_ms", it) }
    job.nextRunAt?.let { put("next_run_at_ms", it) }
    put("created_at_ms", job.createdAt)
}

private fun encodeRecord(record: me.rerere.rikkahub.data.cron.ScheduledJobRunRecord) =
    buildJsonObject {
        put("job_id", record.jobId)
        put("job_name", record.jobName)
        put("scheduled_at_ms", record.scheduledAtMs)
        put("started_at_ms", record.startedAtMs)
        record.finishedAtMs?.let { put("finished_at_ms", it) }
        put("outcome", record.outcome)
        record.error?.let { put("error", it) }
    }

/**
 * 定时任务工具（7 个）：schedule_job / list_jobs / delete_job / pause_job /
 * resume_job / trigger_job_now / job_history。
 *
 * schedule_job 默认把提示词发回创建任务的会话（callerConversationId），
 * 传 conversation_id 可指定其他会话；conversation_id="new" 或省略目标时
 * 用 null（每次触发新开对话）。
 */
fun createCronTools(
    store: CronJobStore,
    scheduler: CronJobScheduler,
    callerContext: ToolInvocationContext,
): List<Tool> = listOf(
    Tool(
        name = "schedule_job",
        description = """
            Schedule a recurring job with a 5-field cron expression (minute hour day-of-month month day-of-week).
            When the job fires, the prompt is sent to the target conversation as a new user message and the
            assistant generates a reply. By default the target is the current conversation; pass
            conversation_id="new" to create a fresh conversation on every fire. Every schedule needs approval.
        """.trimIndent(),
        parameters = {
            InputSchema.Obj(
                properties = buildJsonObject {
                    put("name", buildJsonObject {
                        put("type", "string")
                        put("description", "Short human-readable job name")
                    })
                    put("cron", buildJsonObject {
                        put("type", "string")
                        put("description", "5-field cron, e.g. '0 9 * * *' = daily 09:00, '*/30 * * * *' = every 30 min")
                    })
                    put("prompt", buildJsonObject {
                        put("type", "string")
                        put("description", "The message sent when the job fires")
                    })
                    put("conversation_id", buildJsonObject {
                        put("type", "string")
                        put("description", "Target conversation UUID, 'new' for a fresh conversation each fire, omit for current")
                    })
                    put("assistant_id", buildJsonObject {
                        put("type", "string")
                        put("description", "Assistant UUID for new conversations (omit for current)")
                    })
                },
                required = listOf("name", "cron", "prompt"),
            )
        },
        needsApproval = { true },
        execute = { args ->
            val params = args.jsonObject
            val name = params["name"]?.jsonPrimitive?.contentOrNull
                ?: return@Tool errEnv("invalid_name", "name is required")
            val cron = params["cron"]?.jsonPrimitive?.contentOrNull
                ?: return@Tool errEnv("invalid_cron", "cron is required")
            val prompt = params["prompt"]?.jsonPrimitive?.contentOrNull
                ?: return@Tool errEnv("invalid_prompt", "prompt is required")
            if (!CronParser.isValid(cron)) {
                return@Tool errEnv("invalid_cron", "not a valid 5-field cron expression: $cron")
            }
            val conversationIdArg = params["conversation_id"]?.jsonPrimitive?.contentOrNull
            val targetConversation = when {
                conversationIdArg == null -> callerContext.callerConversationId
                conversationIdArg == "new" -> null
                else -> conversationIdArg
            }
            val job = CronJob(
                id = Uuid.random().toString(),
                name = name,
                prompt = prompt,
                cronExpression = cron,
                assistantId = params["assistant_id"]?.jsonPrimitive?.contentOrNull,
                conversationId = targetConversation,
                enabled = true,
                createdAt = System.currentTimeMillis(),
            )
            store.upsert(job)
            scheduler.schedule(job)
            listOf(UIMessagePart.Text(encodeJob(job).toString()))
        },
    ),
    Tool(
        name = "list_jobs",
        description = "List all scheduled cron jobs with their next fire time. Read-only.".trimIndent(),
        parameters = {
            InputSchema.Obj(
                properties = buildJsonObject { },
                required = emptyList(),
            )
        },
        execute = { _ ->
            val jobs = store.jobs()
            val payload = buildJsonArray {
                jobs.forEach { add(encodeJob(it)) }
            }
            listOf(UIMessagePart.Text(payload.toString()))
        },
    ),
    Tool(
        name = "delete_job",
        description = "Permanently delete a scheduled job by id. Needs approval.".trimIndent(),
        parameters = {
            InputSchema.Obj(
                properties = buildJsonObject {
                    put("job_id", buildJsonObject { put("type", "string") })
                },
                required = listOf("job_id"),
            )
        },
        needsApproval = { true },
        execute = { args ->
            val jobId = args.jsonObject["job_id"]?.jsonPrimitive?.contentOrNull
                ?: return@Tool errEnv("invalid_job_id", "job_id is required")
            store.delete(jobId)
            scheduler.cancel(jobId)
            listOf(UIMessagePart.Text(buildJsonObject {
                put("deleted", jobId)
            }.toString()))
        },
    ),
    Tool(
        name = "pause_job",
        description = "Pause a scheduled job (keeps it, stops firing). Needs approval.".trimIndent(),
        parameters = {
            InputSchema.Obj(
                properties = buildJsonObject {
                    put("job_id", buildJsonObject { put("type", "string") })
                },
                required = listOf("job_id"),
            )
        },
        needsApproval = { true },
        execute = { args ->
            val jobId = args.jsonObject["job_id"]?.jsonPrimitive?.contentOrNull
                ?: return@Tool errEnv("invalid_job_id", "job_id is required")
            val job = store.jobs().firstOrNull { it.id == jobId }
                ?: return@Tool errEnv("unknown_job", "no such job: $jobId")
            store.upsert(job.copy(enabled = false))
            scheduler.cancel(jobId)
            listOf(UIMessagePart.Text(buildJsonObject {
                put("paused", jobId)
            }.toString()))
        },
    ),
    Tool(
        name = "resume_job",
        description = "Resume a paused scheduled job. Needs approval.".trimIndent(),
        parameters = {
            InputSchema.Obj(
                properties = buildJsonObject {
                    put("job_id", buildJsonObject { put("type", "string") })
                },
                required = listOf("job_id"),
            )
        },
        needsApproval = { true },
        execute = { args ->
            val jobId = args.jsonObject["job_id"]?.jsonPrimitive?.contentOrNull
                ?: return@Tool errEnv("invalid_job_id", "job_id is required")
            val job = store.jobs().firstOrNull { it.id == jobId }
                ?: return@Tool errEnv("unknown_job", "no such job: $jobId")
            val resumed = job.copy(enabled = true)
            store.upsert(resumed)
            scheduler.schedule(resumed)
            listOf(UIMessagePart.Text(encodeJob(resumed).toString()))
        },
    ),
    Tool(
        name = "trigger_job_now",
        description = "Fire a scheduled job immediately, without touching its regular schedule. Needs approval.".trimIndent(),
        parameters = {
            InputSchema.Obj(
                properties = buildJsonObject {
                    put("job_id", buildJsonObject { put("type", "string") })
                },
                required = listOf("job_id"),
            )
        },
        needsApproval = { true },
        execute = { args ->
            val jobId = args.jsonObject["job_id"]?.jsonPrimitive?.contentOrNull
                ?: return@Tool errEnv("invalid_job_id", "job_id is required")
            if (store.jobs().none { it.id == jobId }) {
                return@Tool errEnv("unknown_job", "no such job: $jobId")
            }
            scheduler.triggerNow(jobId)
            listOf(UIMessagePart.Text(buildJsonObject {
                put("triggered", jobId)
            }.toString()))
        },
    ),
    Tool(
        name = "job_history",
        description = "Recent fire history of scheduled jobs (newest first). Read-only.".trimIndent(),
        parameters = {
            InputSchema.Obj(
                properties = buildJsonObject {
                    put("job_id", buildJsonObject {
                        put("type", "string")
                        put("description", "Optional filter by job id")
                    })
                    put("limit", buildJsonObject {
                        put("type", "integer")
                        put("description", "Max records (default 20)")
                    })
                },
                required = emptyList(),
            )
        },
        execute = { args ->
            val jobId = args.jsonObject["job_id"]?.jsonPrimitive?.contentOrNull
            val limit = (args.jsonObject["limit"]?.jsonPrimitive?.contentOrNull?.toIntOrNull() ?: 20)
                .coerceIn(1, 100)
            val records = store.history()
                .filter { jobId == null || it.jobId == jobId }
                .take(limit)
            val payload = buildJsonArray {
                records.forEach { add(encodeRecord(it)) }
            }
            listOf(UIMessagePart.Text(payload.toString()))
        },
    ),
)

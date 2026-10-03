#!/usr/bin/env python3
'''batch47 v2: app-control 网关加定时任务六动作（修 v1 的 triggerNow 签名错误）

v1 错误（铁律1再犯，已读 CronTools.kt 实证）：scheduler.triggerNow(job) 传了
CronJob 对象；真实签名是 triggerNow(jobId: String)（trigger_job_now 工具里
scheduler.triggerNow(jobId)）。v2 一并核对全部 CronJobStore/CronJobScheduler
调用：upsert(job)/jobs()/delete(id)/cancel(id)/schedule(job) 均与 CronTools 一致。

用户反馈：AI 调不动定时任务 —— app-control 网关白名单只有切换助手/模型、
改助手参数、MCP 开关、Web 服务，没有 cron 动作。补六个动作：
schedule_cron_job / list_cron_jobs / delete_cron_job / pause_cron_job /
resume_cron_job / trigger_cron_job。

锚点（真实读取）：AppControlTools.kt 的 write_actions 数组 + applyChangeTool
description；AppControlService.kt 的 applyChange when 分支 + else 文案 +
switchAssistant 函数头。CronJob 字段/方法签名来自 CronTools.kt（8KB 全读）。
'''
from pathlib import Path

ROOT = Path.cwd()
ACT = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/appcontrol/AppControlTools.kt'
ACS = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/appcontrol/AppControlService.kt'
MARK = 'rhAppControlCron'

def fail(path, msg):
    print('::error file=' + path + '::batch47v2 ' + str(msg)[:1500])
    raise SystemExit(1)

# ============================================================
# 1. AppControlTools.kt — capabilities 白名单 + 描述 + version
# ============================================================
t = (ROOT / ACT).read_text(encoding='utf-8')
if MARK in t:
    print('batch47v2: already applied (marker in AppControlTools)')
else:
    CAP_ANCHOR = '''                            add(JsonPrimitive("set_web_server"))
                        })'''
    CAP_NEW = '''                            add(JsonPrimitive("set_web_server"))
                            add(JsonPrimitive("schedule_cron_job"))
                            add(JsonPrimitive("list_cron_jobs"))
                            add(JsonPrimitive("delete_cron_job"))
                            add(JsonPrimitive("pause_cron_job"))
                            add(JsonPrimitive("resume_cron_job"))
                            add(JsonPrimitive("trigger_cron_job"))
                        })'''
    if CAP_ANCHOR not in t:
        fail(ACT, 'capabilities write_actions anchor not found')
    t = t.replace(CAP_ANCHOR, CAP_NEW, 1)

    DESC_ANCHOR = '''            - set_web_server {enabled?, port?, jwt_enabled?, localhost_only?}
            All ids are UUIDs. Query first with rikkahub_query to get valid ids.'''
    DESC_NEW = '''            - set_web_server {enabled?, port?, jwt_enabled?, localhost_only?}
            - schedule_cron_job {name, cron, prompt, conversation_id?, assistant_id?}
            - list_cron_jobs {}
            - delete_cron_job {job_id}
            - pause_cron_job {job_id}
            - resume_cron_job {job_id}
            - trigger_cron_job {job_id}
            All ids are UUIDs. Query first with rikkahub_query to get valid ids.'''
    if DESC_ANCHOR not in t:
        fail(ACT, 'applyChange description anchor not found')
    t = t.replace(DESC_ANCHOR, DESC_NEW, 1)

    t = t.replace('put("version", 3)', 'put("version", 4)', 1)

    (ROOT / ACT).write_text(t, encoding='utf-8')
    print('batch47v2: AppControlTools updated')

# ============================================================
# 2. AppControlService.kt — when 分支 + 实现
# ============================================================
s = (ROOT / ACS).read_text(encoding='utf-8')
if 'rhAppControlCron' in s:
    print('batch47v2: AppControlService already applied')
else:
    WHEN_ANCHOR = '''        "set_web_server" -> setWebServer(args)
        else -> buildJsonObject {'''
    WHEN_NEW = '''        "set_web_server" -> setWebServer(args)
        // rhAppControlCron: 定时任务动作（2026-10-03 用户/AI 反馈补充）
        "schedule_cron_job" -> scheduleCronJob(args)
        "list_cron_jobs" -> listCronJobs()
        "delete_cron_job" -> deleteCronJob(args)
        "pause_cron_job" -> pauseCronJob(args)
        "resume_cron_job" -> resumeCronJob(args)
        "trigger_cron_job" -> triggerCronJob(args)
        else -> buildJsonObject {'''
    if WHEN_ANCHOR not in s:
        fail(ACS, 'applyChange when anchor not found')
    s = s.replace(WHEN_ANCHOR, WHEN_NEW, 1)

    ERR_OLD = '''                "action must be one of: switch_assistant, set_chat_model, set_fast_model, " +
                    "update_assistant, toggle_provider_enabled, rename_provider, " +
                    "toggle_mcp_server, set_web_server",'''
    ERR_NEW = '''                "action must be one of: switch_assistant, set_chat_model, set_fast_model, " +
                    "update_assistant, toggle_provider_enabled, rename_provider, " +
                    "toggle_mcp_server, set_web_server, schedule_cron_job, list_cron_jobs, " +
                    "delete_cron_job, pause_cron_job, resume_cron_job, trigger_cron_job",'''
    if ERR_OLD not in s:
        fail(ACS, 'else-branch message anchor not found')
    s = s.replace(ERR_OLD, ERR_NEW, 1)

    IMPL_ANCHOR = '    private suspend fun switchAssistant(args: JsonObject): JsonObject {'
    IMPL_BLOCK = '''    // ==== rhAppControlCron: 定时任务动作实现 ====

    private fun cronStore(): me.rerere.rikkahub.data.cron.CronJobStore =
        org.koin.core.context.GlobalContext.get().get()

    private fun cronScheduler(): me.rerere.rikkahub.service.CronJobScheduler =
        org.koin.core.context.GlobalContext.get().get()

    private fun cronJobToJson(job: me.rerere.rikkahub.data.model.CronJob): JsonObject =
        buildJsonObject {
            put("id", job.id)
            put("name", job.name)
            put("cron", job.cronExpression)
            put("prompt", job.prompt)
            job.assistantId?.let { put("assistant_id", it) }
            job.conversationId?.let { put("conversation_id", it) }
            put("enabled", job.enabled)
            put("created_at_ms", job.createdAt)
        }

    private suspend fun scheduleCronJob(args: JsonObject): JsonObject {
        val name = (args["name"] as? JsonPrimitive)?.contentOrNull
            ?: return errorJson("name required")
        val cron = (args["cron"] as? JsonPrimitive)?.contentOrNull
            ?: return errorJson("cron required")
        val prompt = (args["prompt"] as? JsonPrimitive)?.contentOrNull
            ?: return errorJson("prompt required")
        if (!me.rerere.rikkahub.data.model.CronParser.isValid(cron)) {
            return errorJson("not a valid 5-field cron expression: $cron")
        }
        val targetConversation = when (val v = (args["conversation_id"] as? JsonPrimitive)?.contentOrNull) {
            null -> null
            "new" -> null
            else -> v
        }
        val job = me.rerere.rikkahub.data.model.CronJob(
            id = kotlin.uuid.Uuid.random().toString(),
            name = name,
            prompt = prompt,
            cronExpression = cron,
            assistantId = (args["assistant_id"] as? JsonPrimitive)?.contentOrNull,
            conversationId = targetConversation,
            enabled = true,
            createdAt = System.currentTimeMillis(),
        )
        cronStore().upsert(job)
        cronScheduler().schedule(job)
        return successJson("scheduled cron job ${job.id} ($name)")
    }

    private fun listCronJobs(): JsonObject = buildJsonObject {
        put("jobs", kotlinx.serialization.json.buildJsonArray {
            cronStore().jobs().forEach { add(cronJobToJson(it)) }
        })
    }

    private suspend fun deleteCronJob(args: JsonObject): JsonObject {
        val jobId = (args["job_id"] as? JsonPrimitive)?.contentOrNull
            ?: return errorJson("job_id required")
        cronStore().delete(jobId)
        cronScheduler().cancel(jobId)
        return successJson("deleted job $jobId")
    }

    private suspend fun pauseCronJob(args: JsonObject): JsonObject {
        val jobId = (args["job_id"] as? JsonPrimitive)?.contentOrNull
            ?: return errorJson("job_id required")
        val job = cronStore().jobs().firstOrNull { it.id == jobId }
            ?: return errorJson("no such job: $jobId")
        cronStore().upsert(job.copy(enabled = false))
        cronScheduler().cancel(jobId)
        return successJson("paused job $jobId")
    }

    private suspend fun resumeCronJob(args: JsonObject): JsonObject {
        val jobId = (args["job_id"] as? JsonPrimitive)?.contentOrNull
            ?: return errorJson("job_id required")
        val job = cronStore().jobs().firstOrNull { it.id == jobId }
            ?: return errorJson("no such job: $jobId")
        val resumed = job.copy(enabled = true)
        cronStore().upsert(resumed)
        cronScheduler().schedule(resumed)
        return successJson("resumed job $jobId")
    }

    private suspend fun triggerCronJob(args: JsonObject): JsonObject {
        val jobId = (args["job_id"] as? JsonPrimitive)?.contentOrNull
            ?: return errorJson("job_id required")
        if (cronStore().jobs().none { it.id == jobId }) {
            return errorJson("no such job: $jobId")
        }
        // v2 修正：真实签名是 triggerNow(jobId: String)（CronTools.kt 实证）
        cronScheduler().triggerNow(jobId)
        return successJson("triggered job $jobId")
    }

    private suspend fun switchAssistant(args: JsonObject): JsonObject {'''
    if IMPL_ANCHOR not in s:
        fail(ACS, 'switchAssistant anchor not found')
    s = s.replace(IMPL_ANCHOR, IMPL_BLOCK, 1)

    if 'import kotlinx.serialization.json.JsonPrimitive' not in s:
        IMP_ANCHOR = 'import kotlinx.serialization.json.JsonObject\n'
        if IMP_ANCHOR not in s:
            fail(ACS, 'JsonObject import anchor not found')
        s = s.replace(IMP_ANCHOR, IMP_ANCHOR + 'import kotlinx.serialization.json.JsonPrimitive\n', 1)

    for need in [
        MARK,
        '"schedule_cron_job" -> scheduleCronJob(args)',
        'private suspend fun triggerCronJob',
        'cronScheduler().triggerNow(jobId)',
        'cronStore().upsert(job)',
    ]:
        if need not in s:
            fail(ACS, 'selfcheck missing: ' + need)

    (ROOT / ACS).write_text(s, encoding='utf-8')
    print('batch47v2: AppControlService updated')

print('batch47v2: OK')

#!/usr/bin/env python3
'''batch47 v3: 修 #146 编译错（三处 Kotlin 事实错误，全在我新加的 cron 代码）：

1. contentOrNull 是 kotlinx.serialization.json 的扩展函数，必须
   import kotlinx.serialization.json.contentOrNull —— v2 只补了 JsonPrimitive 类。
2. CronJobStore.jobs() 是 suspend fun —— listCronJobs/cronJobToJson 调用链
   必须全部 suspend（CronTools 里在 Tool.execute 协程里调用所以无感）。
3. put("assistant_id", it) 的 it 是 String?，连带 contentOrNull 未解析产生的
   Any? 报错会在 import 修复后消失。

v3 动作：仅修 patch_batch47.py 自身产物（每次 CI fresh checkout 重放全部脚本，
所以 v3 直接把 v2 脚本替换掉，产物=修正后的代码）。
'''
from pathlib import Path

ROOT = Path.cwd()
ACT = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/appcontrol/AppControlTools.kt'
ACS = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/appcontrol/AppControlService.kt'
MARK = 'rhAppControlCron'

def fail(path, msg):
    print('::error file=' + path + '::batch47v3 ' + str(msg)[:1500])
    raise SystemExit(1)

# ============================================================
# 1. AppControlTools.kt（与 v2 相同，此处 idempotent）
# ============================================================
t = (ROOT / ACT).read_text(encoding='utf-8')
if MARK not in t:
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
    print('batch47v3: AppControlTools ok')
else:
    print('batch47v3: AppControlTools already applied')

# ============================================================
# 2. AppControlService.kt（v3 修正版实现）
# ============================================================
s = (ROOT / ACS).read_text(encoding='utf-8')
if MARK in s:
    print('batch47v3: AppControlService already applied')
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
    # v3 修正：全部读函数标 suspend；contentOrNull 显式 import；
    # put("assistant_id", it) 的 it 为 String，直接传。
    IMPL_BLOCK = '''    // ==== rhAppControlCron: 定时任务动作实现（v3: 修 contentOrNull import + jobs() suspend）====

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
            if (job.assistantId != null) put("assistant_id", job.assistantId)
            if (job.conversationId != null) put("conversation_id", job.conversationId)
            put("enabled", job.enabled)
            put("created_at_ms", job.createdAt)
        }

    private fun strArg(args: JsonObject, key: String): String? =
        (args[key] as? JsonPrimitive)?.contentOrNull

    private suspend fun scheduleCronJob(args: JsonObject): JsonObject {
        val name = strArg(args, "name") ?: return errorJson("name required")
        val cron = strArg(args, "cron") ?: return errorJson("cron required")
        val prompt = strArg(args, "prompt") ?: return errorJson("prompt required")
        if (!me.rerere.rikkahub.data.model.CronParser.isValid(cron)) {
            return errorJson("not a valid 5-field cron expression: $cron")
        }
        val rawConversation = strArg(args, "conversation_id")
        val targetConversation = when {
            rawConversation == null -> null
            rawConversation == "new" -> null
            else -> rawConversation
        }
        val job = me.rerere.rikkahub.data.model.CronJob(
            id = kotlin.uuid.Uuid.random().toString(),
            name = name,
            prompt = prompt,
            cronExpression = cron,
            assistantId = strArg(args, "assistant_id"),
            conversationId = targetConversation,
            enabled = true,
            createdAt = System.currentTimeMillis(),
        )
        cronStore().upsert(job)
        cronScheduler().schedule(job)
        return successJson("scheduled cron job ${job.id} ($name)")
    }

    private suspend fun listCronJobs(): JsonObject = buildJsonObject {
        put("jobs", kotlinx.serialization.json.buildJsonArray {
            cronStore().jobs().forEach { add(cronJobToJson(it)) }
        })
    }

    private suspend fun deleteCronJob(args: JsonObject): JsonObject {
        val jobId = strArg(args, "job_id") ?: return errorJson("job_id required")
        cronStore().delete(jobId)
        cronScheduler().cancel(jobId)
        return successJson("deleted job $jobId")
    }

    private suspend fun pauseCronJob(args: JsonObject): JsonObject {
        val jobId = strArg(args, "job_id") ?: return errorJson("job_id required")
        val job = cronStore().jobs().firstOrNull { it.id == jobId }
            ?: return errorJson("no such job: $jobId")
        cronStore().upsert(job.copy(enabled = false))
        cronScheduler().cancel(jobId)
        return successJson("paused job $jobId")
    }

    private suspend fun resumeCronJob(args: JsonObject): JsonObject {
        val jobId = strArg(args, "job_id") ?: return errorJson("job_id required")
        val job = cronStore().jobs().firstOrNull { it.id == jobId }
            ?: return errorJson("no such job: $jobId")
        val resumed = job.copy(enabled = true)
        cronStore().upsert(resumed)
        cronScheduler().schedule(resumed)
        return successJson("resumed job $jobId")
    }

    private suspend fun triggerCronJob(args: JsonObject): JsonObject {
        val jobId = strArg(args, "job_id") ?: return errorJson("job_id required")
        if (cronStore().jobs().none { it.id == jobId }) {
            return errorJson("no such job: $jobId")
        }
        cronScheduler().triggerNow(jobId)
        return successJson("triggered job $jobId")
    }

    private suspend fun switchAssistant(args: JsonObject): JsonObject {'''
    if IMPL_ANCHOR not in s:
        fail(ACS, 'switchAssistant anchor not found')
    s = s.replace(IMPL_ANCHOR, IMPL_BLOCK, 1)

    # v3 核心：补齐全部三个 import（JsonPrimitive 类 + contentOrNull 扩展 + buildJsonArray）
    need_imports = [
        'import kotlinx.serialization.json.JsonPrimitive\n',
        'import kotlinx.serialization.json.contentOrNull\n',
        'import kotlinx.serialization.json.buildJsonArray\n',
    ]
    IMP_ANCHOR = 'import kotlinx.serialization.json.JsonObject\n'
    if IMP_ANCHOR not in s:
        fail(ACS, 'JsonObject import anchor not found')
    for imp in need_imports:
        if imp not in s:
            s = s.replace(IMP_ANCHOR, IMP_ANCHOR + imp, 1)

    for need in [
        MARK,
        '"schedule_cron_job" -> scheduleCronJob(args)',
        'private suspend fun triggerCronJob',
        'cronScheduler().triggerNow(jobId)',
        'import kotlinx.serialization.json.contentOrNull',
    ]:
        if need not in s:
            fail(ACS, 'selfcheck missing: ' + need)

    (ROOT / ACS).write_text(s, encoding='utf-8')
    print('batch47v3: AppControlService ok')

print('batch47v3: OK')

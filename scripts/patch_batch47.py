#!/usr/bin/env python3
'''batch46 part2: app-control 网关加定时任务六动作 + 子代理工具面修复

用户反馈（2026-10-03）：
1. AI 反馈 app-control 网关白名单没有定时任务动作（只有切换助手/模型、改助手参数、
   MCP 开关、Web 服务）→ 加 schedule_cron_job / list_cron_jobs / delete_cron_job /
   pause_cron_job / resume_cron_job / trigger_cron_job 六个动作（走 AppControlService）。
2. 子代理只能做「不用工具」的活 → SubAgentEngine.executeRun 创建子对话后，
   子对话的 assistantId 复用父助手，工具开关本应自然继承；但 ChatService
   generation 对子代理会话不注入工具（需要确认 ChatService 工具注入路径）。
   v1 方案：给 SubAgentRun 记录 effectiveToolNames（profile 已有），在
   executeRun 发送消息时通过 Conversation.customSystemPrompt 之外的方式……
   实际最小修：dispatch 时把父助手的 localTools 列表写进子对话专属 assistant。

   ⚠️ 修正（读过 SubAgentTools.kt 后）：fork 的 ToolInvocationContext 已有
   callerAssistantId/callerConversationId，cron 调用 localTools.getTools(
   assistant.localTools, context) —— 即工具注入完全由「会话的 assistantId →
   settings.assistants 里的 localTools 列表」驱动。子对话复用父 assistantId，
   理论上工具全继承。用户实测不行的最可能根因：**子代理会话走 FastPath 分支
   或 UI 路径时 localTools 为空**，或 maxTrips=1 提前终止工具环。

   v1 决定：先只做 app-control cron 动作（确定性高），子代理工具问题
   需要读 ChatService.generation 的工具组装代码后再修（下一批）。

锚点来源（全部真实读取）：
- AppControlTools.kt：createAppControlTools 的 write_actions 列表与 applyChangeTool
  description 中的 action 列表
- AppControlService.kt：applyChange when(action) 分支与 else 分支文案
- CronJobStore API（CronTools.kt）：upsert/jobs/delete；CronJob(id,name,prompt,
  cronExpression,assistantId,conversationId,enabled,createdAt)
'''
from pathlib import Path

ROOT = Path.cwd()
ACT = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/appcontrol/AppControlTools.kt'
ACS = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/appcontrol/AppControlService.kt'
MARK = 'rhAppControlCron'

def fail(path, msg):
    print('::error file=' + path + '::batch46p2 ' + str(msg)[:1500])
    raise SystemExit(1)

# ============================================================
# 1. AppControlTools.kt — 三处：capabilities 白名单 + applyChange 描述
# ============================================================
t = (ROOT / ACT).read_text(encoding='utf-8')
if MARK in t:
    print('batch46p2: already applied')
    raise SystemExit(0)

# 1a. capabilities write_actions 数组加 6 项
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

# 1b. applyChangeTool description 的 action 列表加 6 行
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

# 1c. version 3 → 4
t = t.replace('put("version", 3)', 'put("version", 4)', 1)

(ROOT / ACT).write_text(t, encoding='utf-8')
print('batch46p2: AppControlTools updated')

# ============================================================
# 2. AppControlService.kt — applyChange 加 6 分支 + 实现函数
# ============================================================
s = (ROOT / ACS).read_text(encoding='utf-8')

# 2a. when(action) 加分支
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

# 2b. else 分支文案补 6 个动作名
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

# 2c. 文件尾部追加 6 个实现函数（锚点：parseUuid/successJson 等已有 helper 依赖
#     的类体末尾——用 setWebServer 所在区域后的下一个 private fun 或类结束）。
#     稳妥做法：在 "    private suspend fun switchAssistant" 之前插入实现块。
IMPL_ANCHOR = '    private suspend fun switchAssistant(args: JsonObject): JsonObject {'
IMPL_BLOCK = '''    // ==== rhAppControlCron: 定时任务动作实现（依赖注入见文件头 import 区）====

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
        cronStore().upsert(job.copy(enabled = true))
        cronScheduler().schedule(job)
        return successJson("resumed job $jobId")
    }

    private suspend fun triggerCronJob(args: JsonObject): JsonObject {
        val jobId = (args["job_id"] as? JsonPrimitive)?.contentOrNull
            ?: return errorJson("job_id required")
        val job = cronStore().jobs().firstOrNull { it.id == jobId }
            ?: return errorJson("no such job: $jobId")
        val launched = runCatching { cronScheduler().triggerNow(job) }.isSuccess
        return if (launched) {
            successJson("triggered job $jobId")
        } else {
            errorJson("failed to trigger job $jobId (see logs)")
        }
    }

    private suspend fun switchAssistant(args: JsonObject): JsonObject {'''
if IMPL_ANCHOR not in s:
    fail(ACS, 'switchAssistant anchor not found')
s = s.replace(IMPL_ANCHOR, IMPL_BLOCK, 1)

# 2d. import 区补 JsonPrimitive（scheduleCronJob 用到）
if 'import kotlinx.serialization.json.JsonPrimitive' not in s:
    IMP_ANCHOR = 'import kotlinx.serialization.json.JsonObject\n'
    if IMP_ANCHOR not in s:
        fail(ACS, 'JsonObject import anchor not found')
    s = s.replace(IMP_ANCHOR, IMP_ANCHOR + 'import kotlinx.serialization.json.JsonPrimitive\n', 1)

# 自检
for need in [
    MARK,
    '"schedule_cron_job" -> scheduleCronJob(args)',
    'private suspend fun triggerCronJob',
    'cronStore().upsert(job)',
]:
    if need not in s:
        fail(ACS, 'selfcheck missing: ' + need)

(ROOT / ACS).write_text(s, encoding='utf-8')
print('batch46p2: OK')

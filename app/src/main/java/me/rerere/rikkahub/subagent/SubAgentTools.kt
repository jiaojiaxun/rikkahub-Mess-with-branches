package me.rerere.rikkahub.subagent

import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.Tool
import me.rerere.ai.ui.UIMessagePart

private fun errEnv(error: String, detail: String): List<UIMessagePart> {
    val obj = buildJsonObject {
        put("error", error)
        put("detail", detail)
    }
    return listOf(UIMessagePart.Text(obj.toString()))
}

private fun encodeRun(run: SubAgentRun): kotlinx.serialization.json.JsonObject = buildJsonObject {
    put("id", run.id)
    put("status", run.status.name)
    put("label", run.label)
    if (run.modelId != null) put("model_id", run.modelId)
    put("run_in_background", run.runInBackground)
    put("timeout_seconds", run.timeoutSeconds)
    put("max_trips", run.maxTrips)
    put("started_at_ms", run.startedAtMs)
    if (run.finishedAtMs != null) put("finished_at_ms", run.finishedAtMs)
    if (run.result != null) put("result", run.result)
    if (run.error != null) put("error", run.error)
    put("tokens_in", run.tokensIn)
    put("tokens_out", run.tokensOut)
    put("trip_count", run.tripCount)
}

/**
 * 子代理工具（移植自 AAAelina，fork 适配版）。
 * subagent_dispatch：分发一个子代理运行；前台阻塞到终态，后台返回 PENDING。
 * subagent_get：查询单个运行；subagent_list：列出本助手的运行；
 * subagent_cancel：取消运行。全部读注册表（内存）。
 */
fun subagentDispatchTool(engine: SubAgentEngine): Tool = Tool(
    name = "subagent_dispatch",
    description = """
        Dispatch a focused sub-agent — a clean-context LLM run that returns a concise
        summary. Use when the task is independent (research, lookup, multi-step work)
        and would otherwise pollute your context with intermediate output.

        Pass a clear, self-contained task — the sub-agent doesn't see your conversation,
        so restate any context it needs. Pass a short label so the user can recognise
        the running sub-agent. For long-running work, set run_in_background=true and
        poll with subagent_get; otherwise foreground (default) blocks until terminal.

        Approval-required: every dispatch needs explicit confirmation.
    """.trimIndent(),
    parameters = {
        InputSchema.Obj(
            properties = buildJsonObject {
                put("task", buildJsonObject { put("type", "string") })
                put("label", buildJsonObject { put("type", "string") })
                put("model_id", buildJsonObject { put("type", "string") })
                put("system_prompt", buildJsonObject { put("type", "string") })
                put("run_in_background", buildJsonObject { put("type", "boolean") })
                put("timeout_seconds", buildJsonObject { put("type", "integer") })
                put("max_trips", buildJsonObject { put("type", "integer") })
            },
            required = listOf("task"),
        )
    },
    needsApproval = { true },
    execute = { args ->
        val params = args.jsonObject
        val task = params["task"]?.jsonPrimitive?.contentOrNull
            ?: return@Tool errEnv("invalid_task", "task is required")
        val request = SubAgentRequest(
            task = task,
            modelId = params["model_id"]?.jsonPrimitive?.contentOrNull,
            systemPrompt = params["system_prompt"]?.jsonPrimitive?.contentOrNull,
            tools = null, // fork v1: 工具面继承父助手，不接受请求级覆盖
            runInBackground = params["run_in_background"]?.jsonPrimitive?.booleanOrNull ?: false,
            timeoutSeconds = params["timeout_seconds"]?.jsonPrimitive?.intOrNull
                ?: SubAgentDefaults.DEFAULT_TIMEOUT_SECONDS,
            maxTrips = params["max_trips"]?.jsonPrimitive?.intOrNull
                ?: SubAgentDefaults.DEFAULT_MAX_TRIPS,
            label = params["label"]?.jsonPrimitive?.contentOrNull,
        )
        val callerAssistantId = callerAssistantIdFromContext()
        when (val res = engine.dispatch(
            parentAssistantId = callerAssistantId.first,
            parentConversationId = callerAssistantId.second,
            request = request,
        )) {
            is SubAgentEngine.DispatchResult.Reject ->
                return@Tool errEnv(res.error, res.detail)
            is SubAgentEngine.DispatchResult.Ok ->
                listOf(UIMessagePart.Text(encodeRun(res.run).toString()))
        }
    },
)

/**
 * fork 适配：fork 的 Tool.execute 无 ToolInvocationContext 传播（该上下文在
 * LocalTools 构建层），子代理工具拿不到调用方身份。近似：工具执行时从
 * Koin 拿 SettingsStore 读「当前选中助手」——分发者即当前助手。
 */
private fun callerAssistantIdFromContext(): Pair<kotlin.uuid.Uuid, kotlin.uuid.Uuid?> {
    val koin = org.koin.java.KoinJavaComponent.getKoin()
    val settings = kotlinx.coroutines.runBlocking {
        koin.get<me.rerere.rikkahub.data.datastore.SettingsStore>().settingsFlow
            .first { !it.init }
    }
    val assistant = settings.assistants.firstOrNull { it.id == settings.assistantId }
        ?: settings.assistants.firstOrNull()
        ?: error("no assistant available")
    val conversationId = kotlinx.coroutines.runBlocking {
        runCatching {
            koin.get<me.rerere.rikkahub.service.ChatService>()
                .let { null } // ChatService 无「当前对话」概念，留空
        }.getOrNull()
    }
    return assistant.id to null
}

fun subagentGetTool(registry: SubAgentRegistry, callerAssistantId: String): Tool = Tool(
    name = "subagent_get",
    description = """
        Get a sub-agent run by id: status, result or error, token accounting.
    """.trimIndent().replace("\n", " "),
    parameters = {
        InputSchema.Obj(
            properties = buildJsonObject {
                put("run_id", buildJsonObject { put("type", "string") })
            },
            required = listOf("run_id"),
        )
    },
    execute = { args ->
        val runId = args.jsonObject["run_id"]?.jsonPrimitive?.contentOrNull
            ?: return@Tool errEnv("invalid_run_id", "run_id is required")
        val run = registry.getForAssistant(runId, callerAssistantId)
            ?: return@Tool errEnv("unknown_run", "no such run for this assistant")
        listOf(UIMessagePart.Text(encodeRun(run).toString()))
    },
)

fun subagentListTool(registry: SubAgentRegistry, callerAssistantId: String): Tool = Tool(
    name = "subagent_list",
    description = """
        List sub-agent runs visible to this assistant. Set active_only=true to omit
        terminal runs. Read-only.
    """.trimIndent().replace("\n", " "),
    parameters = {
        InputSchema.Obj(
            properties = buildJsonObject {
                put("active_only", buildJsonObject { put("type", "boolean") })
            },
            required = emptyList(),
        )
    },
    execute = { args ->
        val activeOnly = args.jsonObject["active_only"]?.jsonPrimitive?.booleanOrNull ?: false
        val runs = registry.listForAssistant(callerAssistantId, activeOnly)
        val payload = kotlinx.serialization.json.buildJsonArray {
            runs.forEach { run ->
                add(encodeRun(run))
            }
        }
        listOf(UIMessagePart.Text(payload.toString()))
    },
)

fun subagentCancelTool(registry: SubAgentRegistry, callerAssistantId: String): Tool = Tool(
    name = "subagent_cancel",
    description = """
        Cancel an active sub-agent run by id. Returns cancelled=true when a cancel was
        requested.
    """.trimIndent().replace("\n", " "),
    parameters = {
        InputSchema.Obj(
            properties = buildJsonObject {
                put("run_id", buildJsonObject { put("type", "string") })
            },
            required = listOf("run_id"),
        )
    },
    execute = { args ->
        val runId = args.jsonObject["run_id"]?.jsonPrimitive?.contentOrNull
            ?: return@Tool errEnv("invalid_run_id", "run_id is required")
        val cancelled = registry.requestCancelForAssistant(runId, callerAssistantId)
        listOf(UIMessagePart.Text(buildJsonObject {
            put("run_id", runId)
            put("cancelled", cancelled)
        }.toString()))
    },
)

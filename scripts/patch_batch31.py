from pathlib import Path
import re

ROOT = Path.cwd()


def fail(path, msg):
    print(f"::error file={path}::batch31 {msg[:1400]}")
    raise SystemExit(1)


# ============================================================
# 子代理接线 v2（#95 修复）
# #95 失败根因（annotations 实证）：v1 的 archive 选项行锚点是「列对齐空格」
# 逐字匹配——手工对齐的空格数与源码不一致（count=0）。
# v2 修复：①封闭类锚点改正则（容忍任意空格）；②插入行改单空格格式，
# batch33 的后续锚点同步用单空格版（自己写的，格式确定）。
# ============================================================

# ---------- 1) LocalTools.kt ----------
P1 = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt"
t1 = (ROOT / P1).read_text(encoding="utf-8")

if "LocalToolOption.SubAgents" not in t1:
    # 1a. 封闭类加 SubAgents 选项（正则锚，容忍任意列对齐空格）
    ARCHIVE_RE = re.compile(
        r'(?P<line>[ \t]*@Serializable[ \t]+@SerialName\("archive"\)[^\n]*\n)'
        r'(?P<close>[ \t]*\}[ \t]*\n)'
    )
    m = ARCHIVE_RE.search(t1)
    if not m:
        fail(P1, "archive option line (regex) not found")
    subagents_block = (
        "    // Sub-agents (batch31): subagent_dispatch / get / list / cancel\n"
        '    @Serializable @SerialName("sub_agents") data object SubAgents : LocalToolOption()\n'
    )
    t1 = t1[: m.end("line")] + subagents_block + t1[m.end("line"):]

    # 1b. 构造器加 engine/registry 参数（注释行锚点，无对齐空格风险）
    A = (
        "    // Shared OkHttp singleton (NetworkChangeMonitor-registered) — backs the web_fetch tool.\n"
        "    private val okHttpClient: okhttp3.OkHttpClient,\n"
        ") {\n"
    )
    B = (
        "    // Shared OkHttp singleton (NetworkChangeMonitor-registered) — backs the web_fetch tool.\n"
        "    private val okHttpClient: okhttp3.OkHttpClient,\n"
        "    // Sub-agents (batch31): engine + registry injected; the engine resolves ChatService lazily.\n"
        "    private val subAgentEngine: me.rerere.rikkahub.subagent.SubAgentEngine,\n"
        "    private val subAgentRegistry: me.rerere.rikkahub.subagent.SubAgentRegistry,\n"
        ") {\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"ctor anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 1c. getTools 挂四个工具（CostGuards 块锚点，逐字实测无对齐风险）
    A = (
        "        if (options.contains(LocalToolOption.CostGuards)) {\n"
        "            tools.add(me.rerere.rikkahub.costguards.checkTokenUsageTool(settingsStore, conversationRepo))\n"
        "        }\n"
    )
    B = (
        "        if (options.contains(LocalToolOption.CostGuards)) {\n"
        "            tools.add(me.rerere.rikkahub.costguards.checkTokenUsageTool(settingsStore, conversationRepo))\n"
        "        }\n"
        "        if (options.contains(LocalToolOption.SubAgents)) {\n"
        "            // Sub-agents (batch31). callerAssistantId is only present for interactive\n"
        "            // chats — sub-agent conversations get no context, so recursion is\n"
        "            // naturally blocked here and re-checked by conversation id in the engine.\n"
        "            val subAgentCallerId = invocationContext.callerAssistantId\n"
        "            if (subAgentCallerId != null) {\n"
        "                tools.add(me.rerere.rikkahub.subagent.subagentDispatchTool(subAgentEngine, invocationContext))\n"
        "                tools.add(me.rerere.rikkahub.subagent.subagentGetTool(subAgentRegistry, subAgentCallerId))\n"
        "                tools.add(me.rerere.rikkahub.subagent.subagentListTool(subAgentRegistry, subAgentCallerId))\n"
        "                tools.add(me.rerere.rikkahub.subagent.subagentCancelTool(subAgentRegistry, subAgentCallerId))\n"
        "            }\n"
        "        }\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"CostGuards anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    (ROOT / P1).write_text(t1, encoding="utf-8")
    print("batch31 v2: LocalTools option + ctor + getTools wired (regex anchor)")
else:
    print("batch31 v2: LocalTools already patched")

# ---------- 2) AppModule.kt 构造参数 ----------
P2 = "app/src/main/java/me/rerere/rikkahub/di/AppModule.kt"
t2 = (ROOT / P2).read_text(encoding="utf-8")

if "subAgentEngine = get()" in t2:
    print("batch31 v2: AppModule ctor already patched")
else:
    A = (
        "            storageVolumeGrantStore = get(),\n"
        "            okHttpClient = get(),\n"
        "        )\n"
        "    }\n"
    )
    B = (
        "            storageVolumeGrantStore = get(),\n"
        "            okHttpClient = get(),\n"
        "            subAgentEngine = get(),\n"
        "            subAgentRegistry = get(),\n"
        "        )\n"
        "    }\n"
    )
    if t2.count(A) != 1:
        fail(P2, f"LocalTools single tail anchor count={t2.count(A)}")
    t2 = t2.replace(A, B, 1)

    (ROOT / P2).write_text(t2, encoding="utf-8")
    print("batch31 v2: AppModule LocalTools ctor args added")

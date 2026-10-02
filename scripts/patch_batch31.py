from pathlib import Path

ROOT = Path.cwd()


def fail(path, msg):
    print(f"::error file={path}::batch31 {msg[:1400]}")
    raise SystemExit(1)


# ============================================================
# 子代理接线（LocalTools + AppModule 构造参数）
# 锚点全部来自 fix/batch1 实测源码：
# - LocalToolOption 封闭类结尾：archive 行 + '}'
# - LocalTools 构造器：okHttpClient 参数 + ') {'
# - getTools CostGuards 块（逐字实测）
# - AppModule LocalTools single 的 okHttpClient = get() 尾部
# 引擎/注册表通过构造器注入（不用运行时 Koin 查找），惰性 ChatService 已在引擎内处理环。
# ============================================================

# ---------- 1) LocalTools.kt ----------
P1 = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt"
t1 = (ROOT / P1).read_text(encoding="utf-8")

if "LocalToolOption.SubAgents" not in t1:
    # 1a. 封闭类加 SubAgents 选项
    A = (
        '    @Serializable @SerialName("archive")              data object Archive              : LocalToolOption()\n'
        "}\n"
    )
    B = (
        '    @Serializable @SerialName("archive")              data object Archive              : LocalToolOption()\n'
        "    // Sub-agents (batch31): subagent_dispatch / get / list / cancel\n"
        '    @Serializable @SerialName("sub_agents")           data object SubAgents            : LocalToolOption()\n'
        "}\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"option-class anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 1b. 构造器加 engine/registry 参数
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

    # 1c. getTools 挂四个工具（CostGuards 块后）
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
    print("batch31: LocalTools option + ctor + getTools wired")
else:
    print("batch31: LocalTools already patched")

# ---------- 2) AppModule.kt 构造参数 ----------
P2 = "app/src/main/java/me/rerere/rikkahub/di/AppModule.kt"
t2 = (ROOT / P2).read_text(encoding="utf-8")

if "subAgentEngine = get()" in t2:
    print("batch31: AppModule ctor already patched")
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
    print("batch31: AppModule LocalTools ctor args added")

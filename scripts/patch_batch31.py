from pathlib import Path
import re

ROOT = Path.cwd()


def fail(path, msg):
    print(f"::error file={path}::batch31 {msg[:1400]}")
    raise SystemExit(1)


# ============================================================
# 子代理接线 v3（#96 修复）
# #96 失败根因：patch_chat_ui_tools.py（先于 batch* 运行）已在 archive 行尾
# 插入 ChatUi/AppControl——archive 行后不再是闭括号，v2 的「archive+}」正则断了。
# v3 修复：完全照抄 patch_chat_ui_tools.py 已验证可行的模式——匹配行本身
# （不含后续行），插入点在行尾 m.end()。插入顺序无要求（sealed class 内序无关）。
# ============================================================

# ---------- 1) LocalTools.kt ----------
P1 = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt"
t1 = (ROOT / P1).read_text(encoding="utf-8")

if "LocalToolOption.SubAgents" not in t1:
    # 1a. 封闭类加 SubAgents 选项（照抄 patch_chat_ui_tools.py 的 ENUM_RE 模式）
    ARCHIVE_RE = re.compile(
        r'(?P<indent>[ \t]*)@Serializable[ \t]+@SerialName\("archive"\)[ \t]+'
        r'data object Archive[ \t]*:[ \t]*LocalToolOption\(\)'
    )
    m = ARCHIVE_RE.search(t1)
    if not m:
        fail(P1, "archive option line (ENUM_RE) not found")
    ind = m.group("indent")
    subagents_line = (
        '\n{ind}// Sub-agents (batch31): subagent_dispatch / get / list / cancel'
        '\n{ind}@Serializable @SerialName("sub_agents") data object SubAgents : LocalToolOption()'
    ).format(ind=ind)
    t1 = t1[: m.end()] + subagents_line + t1[m.end():]

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
    print("batch31 v3: LocalTools option + ctor + getTools wired (ENUM_RE pattern)")
else:
    print("batch31 v3: LocalTools already patched")

# ---------- 2) AppModule.kt 构造参数 ----------
P2 = "app/src/main/java/me/rerere/rikkahub/di/AppModule.kt"
t2 = (ROOT / P2).read_text(encoding="utf-8")

if "subAgentEngine = get()" in t2:
    print("batch31 v3: AppModule ctor already patched")
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
    print("batch31 v3: AppModule LocalTools ctor args added")

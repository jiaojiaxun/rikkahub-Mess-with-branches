from pathlib import Path
import re

ROOT = Path.cwd()


def fail(path, msg):
    print(f"::error file={path}::batch31 {msg[:1400]}")
    raise SystemExit(1)


# ============================================================
# 子代理接线（收敛版）
# ============================================================

P1 = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt"
t1 = (ROOT / P1).read_text(encoding="utf-8")

if "LocalToolOption.SubAgents" not in t1:
    # 1a. 封闭类插入
    ARCHIVE_RE = re.compile(
        r"(?P<indent>[ \t]*)@Serializable[ \t]+@SerialName\(\"archive\"\)[ \t]+"
        r"data[ \t]+object[ \t]+Archive[ \t]*:[ \t]*LocalToolOption\(\)"
    )
    m = ARCHIVE_RE.search(t1)
    if not m:
        fail(P1, "archive option line not found")
    ind = m.group("indent")
    ins = (
        f"\n{ind}@Serializable @SerialName(\"sub_agents\") data object SubAgents : LocalToolOption()"
    )
    t1 = t1[: m.end()] + ins + t1[m.end():]

    # 1b. 构造器注入
    CTOR_RE = re.compile(
        r"(?P<line>[ \t]*private[ \t]+val[ \t]+okHttpClient: okhttp3\.OkHttpClient,[ \t]*\n)"
    )
    m = CTOR_RE.search(t1)
    if not m:
        fail(P1, "okHttpClient ctor line not found")
    ins = (
        "    private val subAgentEngine: me.rerere.rikkahub.subagent.SubAgentEngine,\n"
        "    private val subAgentRegistry: me.rerere.rikkahub.subagent.SubAgentRegistry,\n"
    )
    t1 = t1[: m.end()] + ins + t1[m.end():]

    # 1c. getTools 注册
    COST_RE = re.compile(
        r"(?P<line>[ \t]*if[ \t]+\(options\.contains\(LocalToolOption\.CostGuards\)\)[ \t]*\{[ \t]*\n"
        r"[ \t]*tools\.add\(me\.rerere\.rikkahub\.costguards\.checkTokenUsageTool\(settingsStore, conversationRepo\)\)[ \t]*\n"
        r"[ \t]*\}[ \t]*\n)"
    )
    m = COST_RE.search(t1)
    if not m:
        fail(P1, "CostGuards block not found")
    ins = (
        "        if (options.contains(LocalToolOption.SubAgents)) {\n"
        "            val subAgentCallerId = invocationContext.callerAssistantId\n"
        "            if (subAgentCallerId != null) {\n"
        "                tools.add(me.rerere.rikkahub.subagent.subagentDispatchTool(subAgentEngine, invocationContext))\n"
        "                tools.add(me.rerere.rikkahub.subagent.subagentGetTool(subAgentRegistry, subAgentCallerId))\n"
        "                tools.add(me.rerere.rikkahub.subagent.subagentListTool(subAgentRegistry, subAgentCallerId))\n"
        "                tools.add(me.rerere.rikkahub.subagent.subagentCancelTool(subAgentRegistry, subAgentCallerId))\n"
        "            }\n"
        "        }\n"
    )
    t1 = t1[: m.end()] + ins + t1[m.end():]

    (ROOT / P1).write_text(t1, encoding="utf-8")
    print("batch31: LocalTools wired")
else:
    print("batch31: already patched")

# 2) AppModule
P2 = "app/src/main/java/me/rerere/rikkahub/di/AppModule.kt"
t2 = (ROOT / P2).read_text(encoding="utf-8")

if "subAgentEngine = get()" in t2:
    print("batch31: AppModule ctor already patched")
else:
    CTOR_RE = re.compile(
        r"(?P<line>[ \t]*okHttpClient = get\(\),[ \t]*\n)"
    )
    m = CTOR_RE.search(t2)
    if not m:
        fail(P2, "okHttpClient ctor call not found")
    ins = (
        "            subAgentEngine = get(),\n"
        "            subAgentRegistry = get(),\n"
    )
    t2 = t2[: m.end()] + ins + t2[m.end():]
    (ROOT / P2).write_text(t2, encoding="utf-8")
    print("batch31: AppModule ctor args added")

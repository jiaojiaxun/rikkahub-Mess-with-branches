#!/usr/bin/env python3
"""batch39: 修子代理死代码 —— 把 subagent/ 真正接进工具面

问题（对抗性检查发现，已存入记忆 #48）：
  subagent/ 三个文件（SubAgentEngine / SubAgentRegistry / SubAgentTools）
  全部未被引用：无 DI 注册、LocalTools 构造无此参数、getTools() 无分支、
  LocalToolOption 枚举无 SubAgent 项。→ AI 永远调不到 subagent_dispatch。

四处改动：
1. LocalToolOption 枚举加 SubAgent 项（锚点：Archive 行）
2. LocalTools 构造加 subAgentEngine 参数（由 DI 提供）
3. LocalTools.getTools() 尾部加 subagent 分支（锚点：Archive 分支末尾 + return）
4. AppModule 注册 SubAgentRegistry / SubAgentEngine，并给 LocalTools 传参

铁律：不用 f-string；含 Kotlin 双引号块用 Python 单引号；幂等标记 rhSubAgent
"""
from pathlib import Path

ROOT = Path.cwd()
MARK = "rhSubAgent"


def fail(path, msg):
    print('::error file=' + path + '::batch39 ' + msg[:1400])
    raise SystemExit(1)


# --- 1. LocalToolOption 枚举 ---
P_TOOLS = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt"
t = (ROOT / P_TOOLS).read_text(encoding="utf-8")

if MARK in t:
    print("batch39: LocalTools already wired")
else:
    ANCHOR_ENUM = (
        '    @Serializable @SerialName("archive")              data object Archive             : LocalToolOption()\n'
        '}\n'
    )
    idx = t.find(ANCHOR_ENUM)
    if idx < 0:
        fail(P_TOOLS, "LocalToolOption.Archive anchor not found")
    new_enum = (
        '    @Serializable @SerialName("archive")              data object Archive             : LocalToolOption()\n'
        '    /* rhSubAgent: 子代理工具组（原先漏接，导致 AI 调不到） */\n'
        '    @Serializable @SerialName("subagent")             data object SubAgent            : LocalToolOption()\n'
        '}\n'
    )
    t = t[:idx] + new_enum + t[idx + len(ANCHOR_ENUM):]

    # --- 2. 构造参数（锚点：已知的构造参数区 storageVolumeGrantStore / okHttpClient）---
    ANCHOR_CTOR = (
        '    private val storageVolumeGrantStore: me.rerere.rikkahub.data.storage.StorageVolumeGrantStore,\n'
    )
    cidx = t.find(ANCHOR_CTOR)
    if cidx < 0:
        fail(P_TOOLS, "LocalTools ctor storageVolumeGrantStore anchor not found")
    new_ctor = ANCHOR_CTOR + (
        '    private val subAgentEngine: me.rerere.rikkahub.subagent.SubAgentEngine? = null, // rhSubAgent\n'
        '    private val subAgentRegistry: me.rerere.rikkahub.subagent.SubAgentRegistry? = null, // rhSubAgent\n'
    )
    t = t[:cidx] + new_ctor + t[cidx + len(ANCHOR_CTOR):]

    # --- 3. getTools() 分支（锚点：Archive 分支 + 随后的 return tools.map）---
    ANCHOR_BRANCH = (
        '        if (options.contains(LocalToolOption.Archive)) {\n'
        '            tools.add(me.rerere.rikkahub.data.ai.tools.local.zipFilesTool(context))\n'
        '            tools.add(me.rerere.rikkahub.data.ai.tools.local.unzipFileTool(context))\n'
        '            tools.add(me.rerere.rikkahub.data.ai.tools.local.listZipContentsTool(context))\n'
        '        }\n'
    )
    bidx = t.find(ANCHOR_BRANCH)
    if bidx < 0:
        fail(P_TOOLS, "getTools Archive branch anchor not found")
    new_branch = ANCHOR_BRANCH + (
        '        // rhSubAgent: engine/registry 可空（DI 未就绪时优雅退化，不崩）\n'
        '        if (options.contains(LocalToolOption.SubAgent)) {\n'
        '            val engine = subAgentEngine\n'
        '            val registry = subAgentRegistry\n'
        '            val callerId = invocationContext.callerAssistantId\n'
        '            if (engine != null && registry != null && callerId != null) {\n'
        '                tools.add(\n'
        '                    me.rerere.rikkahub.subagent.subagentDispatchTool(\n'
        '                        engine = engine,\n'
        '                        callerContext = invocationContext,\n'
        '                    )\n'
        '                )\n'
        '                tools.add(me.rerere.rikkahub.subagent.subagentGetTool(registry, callerId))\n'
        '                tools.add(me.rerere.rikkahub.subagent.subagentListTool(registry, callerId))\n'
        '                tools.add(me.rerere.rikkahub.subagent.subagentCancelTool(registry, callerId))\n'
        '            }\n'
        '        }\n'
    )
    t = t[:bidx] + new_branch + t[bidx + len(ANCHOR_BRANCH):]

    (ROOT / P_TOOLS).write_text(t, encoding="utf-8")
    print("batch39: LocalTools wired (enum + ctor + getTools branch)")

# --- 4. AppModule：注册 + 给 LocalTools 传参 ---
P_APP = "app/src/main/java/me/rerere/rikkahub/di/AppModule.kt"
ta = (ROOT / P_APP).read_text(encoding="utf-8")

if MARK in ta:
    print("batch39: AppModule already wired")
else:
    # 4a. 给 LocalTools(...) 传参
    ANCHOR_APP_TOOLS = (
        '            okHttpClient = get(),\n'
        '        )\n'
        '    }\n'
    )
    aidx = ta.find(ANCHOR_APP_TOOLS)
    if aidx < 0:
        fail(P_APP, "LocalTools okHttpClient anchor not found")
    new_app_tools = (
        '            okHttpClient = get(),\n'
        '            subAgentEngine = getOrNull(), // rhSubAgent\n'
        '            subAgentRegistry = getOrNull(), // rhSubAgent\n'
        '        )\n'
        '    }\n'
    )
    ta = ta[:aidx] + new_app_tools + ta[aidx + len(ANCHOR_APP_TOOLS):]

    # 4b. 注册两个 subagent single（放在 CronJob 注册之后，保持分组）
    ANCHOR_CRON = (
        '    single {\n'
        '        me.rerere.rikkahub.service.CronJobScheduler(get(), get())\n'
        '    }\n'
    )
    cidx2 = ta.find(ANCHOR_CRON)
    if cidx2 < 0:
        fail(P_APP, "CronJobScheduler single anchor not found")
    new_reg = ANCHOR_CRON + (
        '\n'
        '    /* rhSubAgent: 子代理引擎原先未注册 → 工具面拿不到实例。\n'
        '       SubAgentEngine 内部用惰性解析断 DI 环（ChatService↔LocalTools），\n'
        '       所以这里直接构造不会形成初始化环。 */\n'
        '    single {\n'
        '        me.rerere.rikkahub.subagent.SubAgentRegistry()\n'
        '    }\n'
        '\n'
        '    single {\n'
        '        me.rerere.rikkahub.subagent.SubAgentEngine(\n'
        '            registry = get(),\n'
        '            conversationRepo = get(),\n'
        '            settingsStore = get(),\n'
        '            appScope = get(),\n'
        '        )\n'
        '    }\n'
    )
    ta = ta[:cidx2] + new_reg + ta[cidx2 + len(ANCHOR_CRON):]

    (ROOT / P_APP).write_text(ta, encoding="utf-8")
    print("batch39: AppModule wired (registry + engine + LocalTools args)")

print("batch39: OK")

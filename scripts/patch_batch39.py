#!/usr/bin/env python3
"""batch39 v2: 修子代理死代码（修 #124 锚点错误）

#124 失败根因：LocalToolOption.Archive 行是手工对齐的，
空格数量数错 → 逐字锚点找不到（铁律 12/13 的坑）。

v2 修正：枚举锚点改用行级正则，不依赖具体空格数。
其余三处锚点经核实无误（构造参数区、getTools 分支、AppModule）保持不变。

铁律：不用 f-string；含 Kotlin 双引号块用 Python 单引号；幂等标记 rhSubAgent
"""
from pathlib import Path
import re

ROOT = Path.cwd()
MARK = "rhSubAgent"


def fail(path, msg):
    print('::error file=' + path + '::batch39v2 ' + msg[:1400])
    raise SystemExit(1)


# --- 1~3. LocalTools.kt ---
P_TOOLS = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt"
t = (ROOT / P_TOOLS).read_text(encoding="utf-8")

if MARK in t:
    print("batch39v2: LocalTools already wired")
else:
    # 1. 枚举项：正则容错（对齐空格不定）
    ENUM_RE = re.compile(
        r'(@SerialName\("archive"\)\s*data object Archive\s*:\s*LocalToolOption\(\)\s*\n'
        r'\s*\}\s*\n)'
    )
    m = ENUM_RE.search(t)
    if not m:
        fail(P_TOOLS, "LocalToolOption.Archive anchor not found (v2 regex)")
    block = m.group(1)
    close_idx = block.rstrip().rfind('}')
    new_block = (
        block[:close_idx]
        + '    /* rhSubAgent: 子代理工具组（原先漏接，导致 AI 调不到） */\n'
        + '    @Serializable @SerialName("subagent") data object SubAgent : LocalToolOption()\n'
        + block[close_idx:]
    )
    t = t[:m.start()] + new_block + t[m.end():]

    # 2. 构造参数（锚点：storageVolumeGrantStore；该行无手工对齐，逐字安全）
    ANCHOR_CTOR = (
        '    private val storageVolumeGrantStore: me.rerere.rikkahub.data.storage.StorageVolumeGrantStore,\n'
    )
    cidx = t.find(ANCHOR_CTOR)
    if cidx < 0:
        fail(P_TOOLS, "LocalTools ctor storageVolumeGrantStore anchor not found")
    new_ctor = ANCHOR_CTOR + (
        '    // rhSubAgent: 可空 + 默认 null —— DI 未就绪时优雅退化，绝不崩\n'
        '    private val subAgentEngine: me.rerere.rikkahub.subagent.SubAgentEngine? = null,\n'
        '    private val subAgentRegistry: me.rerere.rikkahub.subagent.SubAgentRegistry? = null,\n'
    )
    t = t[:cidx] + new_ctor + t[cidx + len(ANCHOR_CTOR):]

    # 3. getTools 分支（锚点：Archive 分支；每行都短，逐字安全）
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
        '        // rhSubAgent: engine/registry/callerId 三者齐备才注册，否则静默跳过\n'
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
    print("batch39v2: LocalTools wired (enum regex + ctor + getTools branch)")

# --- 4. AppModule ---
P_APP = "app/src/main/java/me/rerere/rikkahub/di/AppModule.kt"
ta = (ROOT / P_APP).read_text(encoding="utf-8")

if MARK in ta:
    print("batch39v2: AppModule already wired")
else:
    # 4a. LocalTools(...) 传参
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

    # 4b. 注册（放在 CronJob 之后）
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
    print("batch39v2: AppModule wired (registry + engine + LocalTools args)")

print("batch39v2: OK")
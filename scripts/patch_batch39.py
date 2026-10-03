#!/usr/bin/env python3
"""batch39 v3: 修子代理死代码（修 #124/#125 锚点连续失败）

#124 逐字锚点失败、#125 正则锚点也失败 → 说明我对该行的格式假设有误
（可能空格不是 U+0020，或行尾有不可见字符）。

v3 策略：**彻底放弃格式假设**，用纯子串定位：
    1. 找 'data object Archive'（不含任何空格/引号假设）
    2. 从该位置往后找第一个行首的 '}'（枚举闭合）
    3. 在它之前插入新枚举项

其余三处锚点（构造参数、getTools 分支、AppModule）在 #124/#125 都**没报错**
（报错总是卡在第 1 步），说明它们是安全的，保持不变。

铁律：不用 f-string；含 Kotlin 双引号块用 Python 单引号；幂等标记 rhSubAgent
"""
from pathlib import Path

ROOT = Path.cwd()
MARK = "rhSubAgent"


def fail(path, msg):
    print('::error file=' + path + '::batch39v3 ' + msg[:1400])
    raise SystemExit(1)


# --- 1~3. LocalTools.kt ---
P_TOOLS = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt"
t = (ROOT / P_TOOLS).read_text(encoding="utf-8")

if MARK in t:
    print("batch39v3: LocalTools already wired")
else:
    # 1. 子串定位（零格式假设）
    KEY = 'data object Archive'
    i = t.find(KEY)
    if i < 0:
        fail(P_TOOLS, "substring 'data object Archive' not found")
    # 2. 从 Archive 之后找第一个行首 '}'
    j = t.find('\n}', i)
    if j < 0:
        fail(P_TOOLS, "enum closing brace not found after Archive")
    insert_pos = j + 1  # 指向 '}' 本身，插在它前面
    new_enum_line = (
        '    /* rhSubAgent: 子代理工具组（原先漏接，导致 AI 调不到） */\n'
        '    @Serializable @SerialName("subagent") data object SubAgent : LocalToolOption()\n'
    )
    t = t[:insert_pos] + new_enum_line + t[insert_pos:]

    # 3. 构造参数
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

    # 4. getTools 分支
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
    print("batch39v3: LocalTools wired (substring enum + ctor + getTools branch)")

# --- 5. AppModule ---
P_APP = "app/src/main/java/me/rerere/rikkahub/di/AppModule.kt"
ta = (ROOT / P_APP).read_text(encoding="utf-8")

if MARK in ta:
    print("batch39v3: AppModule already wired")
else:
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
    print("batch39v3: AppModule wired (registry + engine + LocalTools args)")

print("batch39v3: OK")

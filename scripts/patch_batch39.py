#!/usr/bin/env python3
"""batch39 v4: 修 subagent 死代码（修 #124/#125/#126 连续失败）

演进：
  v1 (#124) 逐字锚点失败（Archive 行空格数错）
  v2 (#125) 正则锚点也失败（格式假设还是错）
  v3 (#126) LocalTools 三步全过（子串定位成功），但 AppModule 的
            `okHttpClient = get(),\\n        )\\n    }\\n` 锚点失败
            ——因为 batch38 已经改过 AppModule.kt（加了 CronJob 注册），
            文件结构变了，旧锚点不再匹配

v4 策略：**全部用子串定位**，不依赖任何精确格式：
  LocalTools.kt 三处：已在 v3 验证通过，保持不变
  AppModule.kt 两处：
    a) 找 'okHttpClient = get(),' → 在它后面插入两行参数
    b) 找 'CronJobScheduler(get(), get())' → 找它之后的 '}' → 在后面插入注册

铁律强化：**改过的文件不能用旧锚点**（铁律 11 的扩展）
"""
from pathlib import Path

ROOT = Path.cwd()
MARK = "rhSubAgent"


def fail(path, msg):
    print('::error file=' + path + '::batch39v4 ' + msg[:1400])
    raise SystemExit(1)


# --- 1~3. LocalTools.kt（v3 已验证通过，保持不变）---
P_TOOLS = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt"
t = (ROOT / P_TOOLS).read_text(encoding="utf-8")

if MARK in t:
    print("batch39v4: LocalTools already wired")
else:
    # 1. 枚举：子串定位
    KEY = 'data object Archive'
    i = t.find(KEY)
    if i < 0:
        fail(P_TOOLS, "substring 'data object Archive' not found")
    j = t.find('\n}', i)
    if j < 0:
        fail(P_TOOLS, "enum closing brace not found after Archive")
    insert_pos = j + 1
    new_enum_line = (
        '    /* rhSubAgent: 子代理工具组（原先漏接，导致 AI 调不到） */\n'
        '    @Serializable @SerialName("subagent") data object SubAgent : LocalToolOption()\n'
    )
    t = t[:insert_pos] + new_enum_line + t[insert_pos:]

    # 2. 构造参数
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

    # 3. getTools 分支
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
    print("batch39v4: LocalTools wired (substring enum + ctor + getTools branch)")

# --- 4. AppModule（v4：全子串定位）---
P_APP = "app/src/main/java/me/rerere/rikkahub/di/AppModule.kt"
ta = (ROOT / P_APP).read_text(encoding="utf-8")

if MARK in ta:
    print("batch39v4: AppModule already wired")
else:
    # 4a. LocalTools(...) 传参：找 'okHttpClient = get(),' 在它后面插入
    KEY_OK = 'okHttpClient = get(),\n'
    aidx = ta.find(KEY_OK)
    if aidx < 0:
        fail(P_APP, "substring 'okHttpClient = get(),' not found")
    insert_a = aidx + len(KEY_OK)
    new_args = (
        '            subAgentEngine = getOrNull(), // rhSubAgent\n'
        '            subAgentRegistry = getOrNull(), // rhSubAgent\n'
    )
    ta = ta[:insert_a] + new_args + ta[insert_a:]

    # 4b. 注册：找 'CronJobScheduler(get(), get())' → 找它之后的 '}' → 在后面插入
    KEY_CRON = 'CronJobScheduler(get(), get())'
    cidx2 = ta.find(KEY_CRON)
    if cidx2 < 0:
        fail(P_APP, "substring 'CronJobScheduler(get(), get())' not found")
    # 从 KEY_CRON 之后找第一个 '}\n'
    brace = ta.find('}\n', cidx2 + len(KEY_CRON))
    if brace < 0:
        fail(P_APP, "closing brace after CronJobScheduler not found")
    insert_b = brace + 2  # 跳过 '}\n'
    new_reg = (
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
    ta = ta[:insert_b] + new_reg + ta[insert_b:]

    (ROOT / P_APP).write_text(ta, encoding="utf-8")
    print("batch39v4: AppModule wired (substring okHttpClient + substring CronJob)")

print("batch39v4: OK")

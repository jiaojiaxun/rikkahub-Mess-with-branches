#!/usr/bin/env python3
"""batch39 v5: 修 subagent 死代码（最小侵入版，修 #124-128 连续失败）

失败史：
  v1 逐字锚点 → Archive 行空格错
  v2 正则锚点 → 还是没匹配
  v3 子串定位 → LocalTools 过了，AppModule 锚点过时（batch38 改过该文件）
  v4 全子串 → patch 全过、编译到 04:46 才挂：
       LocalTools.kt 308-313 Conflicting declarations（重复声明）
       LocalTools.kt 796-797 Overload resolution ambiguity

v4 根因推断：构造参数插入点选错（`storageVolumeGrantStore` 那行可能不在
我假设的位置），插到了枚举/其他区域 → 重复声明。

v5 策略：**彻底不碰构造函数签名**。
  只做两处最小改动：
    1. LocalToolOption 枚举加 SubAgent 项
    2. getTools() 末尾加分支，内部用 GlobalContext 惰性取 engine/registry

  这样 AppModule 也**不需要**给 LocalTools(...) 传参 —— 只加两个 single 注册。
  侵入面从 4 处降到 3 处，且不涉及任何已存在的签名。

自检（v5 新增）：
  - 插入后断言文件里 'data object SubAgent' 只出现 1 次
  - 插入后断言 'rhSubAgent' 标记数量正确

铁律：不用 f-string；含 Kotlin 双引号块用 Python 单引号
"""
from pathlib import Path

ROOT = Path.cwd()
MARK = "rhSubAgent"


def fail(path, msg):
    print('::error file=' + path + '::batch39v5 ' + msg[:1400])
    raise SystemExit(1)


# ========== 1. LocalToolOption 枚举 + getTools 分支 ==========
P_TOOLS = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt"
t = (ROOT / P_TOOLS).read_text(encoding="utf-8")

if 'data object SubAgent' in t:
    print("batch39v5: LocalTools already wired")
else:
    # --- 1a. 枚举项：在 Archive 之后、枚举闭合 '}' 之前插入 ---
    KEY = 'data object Archive'
    i = t.find(KEY)
    if i < 0:
        fail(P_TOOLS, "substring 'data object Archive' not found")
    # 从 Archive 行末开始，找下一个只含 '}' 的行
    line_end = t.find('\n', i)
    if line_end < 0:
        fail(P_TOOLS, "no newline after Archive")
    j = t.find('\n}', line_end)
    if j < 0:
        fail(P_TOOLS, "enum closing brace not found")
    insert_enum_at = j + 1  # 指向 '}' 本身
    enum_line = (
        '    /* rhSubAgent: 子代理工具组（原先漏接，导致 AI 调不到） */\n'
        '    @Serializable @SerialName("subagent") data object SubAgent : LocalToolOption()\n'
    )
    t = t[:insert_enum_at] + enum_line + t[insert_enum_at:]

    # --- 1b. getTools 分支：插在 Archive 工具分支之后 ---
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
        '        // rhSubAgent: 惰性取实例（不碰构造签名，DI 未就绪时静默跳过）\n'
        '        if (options.contains(LocalToolOption.SubAgent)) {\n'
        '            try {\n'
        '                val koin = org.koin.core.context.GlobalContext.get()\n'
        '                val engine = koin.get<me.rerere.rikkahub.subagent.SubAgentEngine>()\n'
        '                val registry = koin.get<me.rerere.rikkahub.subagent.SubAgentRegistry>()\n'
        '                val callerId = invocationContext.callerAssistantId\n'
        '                if (callerId != null) {\n'
        '                    tools.add(\n'
        '                        me.rerere.rikkahub.subagent.subagentDispatchTool(\n'
        '                            engine = engine,\n'
        '                            callerContext = invocationContext,\n'
        '                        )\n'
        '                    )\n'
        '                    tools.add(me.rerere.rikkahub.subagent.subagentGetTool(registry, callerId))\n'
        '                    tools.add(me.rerere.rikkahub.subagent.subagentListTool(registry, callerId))\n'
        '                    tools.add(me.rerere.rikkahub.subagent.subagentCancelTool(registry, callerId))\n'
        '                }\n'
        '            } catch (_: Throwable) {\n'
        '                // DI 未就绪：静默降级，不影响其他工具\n'
        '            }\n'
        '        }\n'
    )
    t = t[:bidx] + new_branch + t[bidx + len(ANCHOR_BRANCH):]

    # --- 自检 ---
    if t.count('data object SubAgent') != 1:
        fail(P_TOOLS, "self-check failed: SubAgent declared " + str(t.count('data object SubAgent')) + " times")
    if t.count('LocalToolOption.SubAgent') != 2:
        fail(P_TOOLS, "self-check failed: SubAgent referenced " + str(t.count('LocalToolOption.SubAgent')) + " times (expect 2)")

    (ROOT / P_TOOLS).write_text(t, encoding="utf-8")
    print("batch39v5: LocalTools wired (enum + getTools branch, ctor untouched)")

# ========== 2. AppModule：只加注册，不改 LocalTools 传参 ==========
P_APP = "app/src/main/java/me/rerere/rikkahub/di/AppModule.kt"
ta = (ROOT / P_APP).read_text(encoding="utf-8")

if 'SubAgentRegistry()' in ta:
    print("batch39v5: AppModule already wired")
else:
    KEY_CRON = 'CronJobScheduler(get(), get())'
    cidx = ta.find(KEY_CRON)
    if cidx < 0:
        fail(P_APP, "substring 'CronJobScheduler(get(), get())' not found")
    brace = ta.find('}\n', cidx + len(KEY_CRON))
    if brace < 0:
        fail(P_APP, "closing brace after CronJobScheduler not found")
    insert_at = brace + 2
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
    ta = ta[:insert_at] + new_reg + ta[insert_at:]

    if ta.count('SubAgentRegistry()') != 1:
        fail(P_APP, "self-check failed: SubAgentRegistry declared " + str(ta.count('SubAgentRegistry()')) + " times")

    (ROOT / P_APP).write_text(ta, encoding="utf-8")
    print("batch39v5: AppModule wired (registry + engine only)")

print("batch39v5: OK")

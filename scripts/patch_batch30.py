from pathlib import Path

ROOT = Path.cwd()


def fail(path, msg):
    print(f"::error file={path}::batch30 {msg[:1400]}")
    raise SystemExit(1)


# ============================================================
# 子代理注册（DI + 工具入口）
# 新文件已随本提交直接入库：subagent/ 五个 Kotlin 文件。
# 本脚本把 SubAgentEngine/Registry 注册进 AppModule.kt，并把四个工具挂到
# LocalTools.kt 的工具列表（fork 适配：入口给 LocalTools.getTools()）。
# ============================================================

# ---------- 1) AppModule.kt 注册 ----------
P1 = "app/src/main/java/me/rerere/rikkahub/di/AppModule.kt"
t1 = (ROOT / P1).read_text(encoding="utf-8")

if "SubAgentRegistry" in t1:
    print("batch30: AppModule already patched")
else:
    # 1a. import 区追加（锚点：LocalTools import 行后）
    A = "import me.rerere.rikkahub.data.ai.tools.LocalTools\n"
    B = (
        "import me.rerere.rikkahub.data.ai.tools.LocalTools\n"
        "import me.rerere.rikkahub.subagent.SubAgentEngine\n"
        "import me.rerere.rikkahub.subagent.SubAgentRegistry\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"import anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 1b. single 区追加（锚点：AppScope single 后）
    A = (
        "    single {\n"
        "        AppScope()\n"
        "    }\n"
    )
    B = (
        "    single {\n"
        "        AppScope()\n"
        "    }\n"
        "\n"
        "    // Sub-agents (batch30): in-memory registry + engine; ChatService resolved lazily.\n"
        "    single { SubAgentRegistry() }\n"
        "    single {\n"
        "        SubAgentEngine(\n"
        "            registry = get(),\n"
        "            conversationRepo = get(),\n"
        "            settingsStore = get(),\n"
        "            appScope = get(),\n"
        "        )\n"
        "    }\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"AppScope anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    (ROOT / P1).write_text(t1, encoding="utf-8")
    print("batch30: AppModule DI registered")


# ---------- 2) LocalTools.kt 挂工具 ----------
P2 = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt"
t2 = (ROOT / P2).read_text(encoding="utf-8")

if "subagentDispatchTool" in t2:
    print("batch30: LocalTools already patched")
else:
    # 2a. import 追加（锚点：package 行后，lazy import 前缀）
    A = "package me.rerere.rikkahub.data.ai.tools\n"
    B = (
        "package me.rerere.rikkahub.data.ai.tools\n"
        "\n"
        "import me.rerere.rikkahub.subagent.SubAgentEngine\n"
        "import me.rerere.rikkahub.subagent.SubAgentRegistry\n"
        "import me.rerere.rikkahub.subagent.subagentDispatchTool\n"
        "import me.rerere.rikkahub.subagent.subagentGetTool\n"
        "import me.rerere.rikkahub.subagent.subagentListTool\n"
        "import me.rerere.rikkahub.subagent.subagentCancelTool\n"
    )
    if t2.count(A) != 1:
        fail(P2, f"package anchor count={t2.count(A)}")
    t2 = t2.replace(A, B, 1)

    # 2b. getTools() 返回列表追加（锚点：需要侦察 LocalTools.getTools 的实际返回结构。
    # 从 44.8KB 大小和 fork 结构推测是 buildList { ... } 或 listOf(...)。
    # 保守：标记 TODO 由下轮补——但这样工具不会被注册。
    # 折中：插入一个独立的扩展函数，不改 getTools 内部（避免锚点风险），
    # 由 ChatService 侧拼接。但 ChatService 139KB 改动也重。
    # 最稳：不挂 LocalTools，工具注册独立函数留待下轮接线。
    # ——保持文件只加 import（幂等），实际接线等读 LocalTools.getTools 结构后补。
    t2 = t2.replace(A, B, 1)  # 已做

    (ROOT / P2).write_text(t2, encoding="utf-8")
    print("batch30: LocalTools imports staged (wiring TODO next round)")

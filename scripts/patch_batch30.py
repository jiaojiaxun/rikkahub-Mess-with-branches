from pathlib import Path

ROOT = Path.cwd()


def fail(path, msg):
    print(f"::error file={path}::batch30 {msg[:1400]}")
    raise SystemExit(1)


# ============================================================
# 子代理 DI 注册（v2 修正版）
# v1 的错误：对 LocalTools.kt 做了两次 replace 导致 import 重复插入。
# v2 只负责 AppModule 的 DI 注册；LocalTools 的接线全部移到 batch31。
# ============================================================

P1 = "app/src/main/java/me/rerere/rikkahub/di/AppModule.kt"
t1 = (ROOT / P1).read_text(encoding="utf-8")

if "SubAgentRegistry" in t1:
    print("batch30: AppModule already patched")
else:
    A = "import me.rerere.rikkahub.data.ai.tools.LocalTools\n"
    B = (
        "import me.rerere.rikkahub.data.ai.tools.LocalTools\n"
        "import me.rerere.rikkahub.subagent.SubAgentEngine\n"
        "import me.rerere.rikkahub.subagent.SubAgentRegistry\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"import anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

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
        "    // Sub-agents (batch30): in-memory registry + engine. ChatService is resolved\n"
        "    // lazily inside the engine (GlobalContext) to break the DI cycle.\n"
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
    print("batch30 v2: AppModule DI registered")

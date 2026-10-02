from pathlib import Path
import re

ROOT = Path.cwd()


def fail(path, msg):
    print(f"::error file={path}::batch30 {msg[:1400]}")
    raise SystemExit(1)


# ============================================================
# 子代理 DI 注册（收敛版）
# ============================================================

P1 = "app/src/main/java/me/rerere/rikkahub/di/AppModule.kt"
t1 = (ROOT / P1).read_text(encoding="utf-8")

if "SubAgentRegistry" in t1:
    print("batch30: AppModule already patched")
else:
    # 插入点：import 块之后
    IMPORT_RE = re.compile(r"(?P<line>import[ \t]+me\.rerere\.rikkahub\.data\.ai\.tools\.LocalTools\n)")
    m = IMPORT_RE.search(t1)
    if not m:
        fail(P1, "LocalTools import line not found")
    ins = (
        "import me.rerere.rikkahub.subagent.SubAgentEngine\n"
        "import me.rerere.rikkahub.subagent.SubAgentRegistry\n"
    )
    t1 = t1[: m.end()] + ins + t1[m.end():]

    # 插入点：AppScope single 块之后
    SCOPE_RE = re.compile(
        r"(?P<line>[ \t]*single[ \t]*\{[ \t]*\n"
        r"[ \t]*AppScope\(\)[ \t]*\n"
        r"[ \t]*\}[ \t]*\n)"
    )
    m = SCOPE_RE.search(t1)
    if not m:
        fail(P1, "AppScope single block not found")
    ins = (
        "\n"
        "    // Sub-agents: in-memory registry + engine\n"
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
    t1 = t1[: m.end()] + ins + t1[m.end():]

    (ROOT / P1).write_text(t1, encoding="utf-8")
    print("batch30: AppModule DI registered")

from pathlib import Path
import re

ROOT = Path.cwd()

def fail(path, msg):
    print(f"::error file={path}::batch32 {msg[:1400]}")
    raise SystemExit(1)

P = "app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/detail/AssistantLocalToolPage.kt"
t = (ROOT / P).read_text(encoding="utf-8")

if "LocalToolOption.SubAgents" in t:
    print("batch32: already patched")
else:
    ANCHOR_RE = re.compile(
        r"(?P<indent>[ \t]*)item\(\s*headlineContent = \{\s*"
        r"Text\(stringResource\(R\.string\.assistant_page_local_tools_javascript_engine_title\)\)"
    )
    m = ANCHOR_RE.search(t)
    if not m:
        fail(P, "javascript_engine item not found")
    ind = m.group("indent")
    block = (
        f"{ind}item(\n"
        f"{ind}    headlineContent = {{ Text(\"子代理（Sub-agents）\") }},\n"
        f"{ind}    supportingContent = {{ Text(\"分发 AI 任务并获得摘要\") }},\n"
        f"{ind}    trailingContent = {{\n"
        f"{ind}        Switch(\n"
        f"{ind}            checked = assistant.localTools.contains(LocalToolOption.SubAgents),\n"
        f"{ind}            onCheckedChange = {{ toggleLocalTool(LocalToolOption.SubAgents, it) }}\n"
        f"{ind}        )\n"
        f"{ind}    }}\n"
        f"{ind}})\n"
    )
    t = t[: m.start()] + block + t[m.start():]
    (ROOT / P).write_text(t, encoding="utf-8")
    print("batch32: SubAgents switch added")

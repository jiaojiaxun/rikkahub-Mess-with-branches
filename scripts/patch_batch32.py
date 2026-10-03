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
        r"(?P<indent>[ \t]*)item\(\s*"
        r"headlineContent = \{\s*"
        r"Text\(stringResource\(R\.string\.assistant_page_local_tools_javascript_engine_title\)\)"
    )
    m = ANCHOR_RE.search(t)
    if not m:
        fail(P, "javascript_engine item not found")
    ind = m.group("indent")
    # 注意：用普通字符串拼接，避免 f-string 里 Kotlin 花括号转义陷阱
    # （历史 bug：f"{ind}})\n" 触发 SyntaxError，导致 #96-#108 全部构建在 patch 步骤失败）
    block = (
        ind + 'item(\n'
        + ind + '    headlineContent = { Text("子代理（Sub-agents）") },\n'
        + ind + '    supportingContent = { Text("分发 AI 任务并获得摘要") },\n'
        + ind + '    trailingContent = {\n'
        + ind + '        Switch(\n'
        + ind + '            checked = assistant.localTools.contains(LocalToolOption.SubAgents),\n'
        + ind + '            onCheckedChange = { toggleLocalTool(LocalToolOption.SubAgents, it) }\n'
        + ind + '        )\n'
        + ind + '    }\n'
        + ind + ')\n'
    )
    t = t[: m.start()] + block + t[m.start():]
    (ROOT / P).write_text(t, encoding="utf-8")
    print("batch32: SubAgents switch added")

#!/usr/bin/env python3
"""Add the Sub-agents switch to AssistantLocalToolPage.kt (batch32).

Follows the same insertion pattern as patch_local_tool_page.py: a new item()
row directly above the first built-in row (JavaScript engine). Idempotent via
the LocalToolOption.SubAgents marker.
"""
import re
import sys
from pathlib import Path

TARGET = Path("app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/detail/AssistantLocalToolPage.kt")

ANCHOR_RE = re.compile(
    r"(?P<indent>[ \t]*)item\(\s*headlineContent = \{\s*"
    r"Text\(stringResource\(R\.string\.assistant_page_local_tools_javascript_engine_title\)\)"
)

BLOCK = """{ind}item(
{ind}    headlineContent = {{ Text("子代理（Sub-agents）") }},
{ind}    supportingContent = {{ Text("允许 AI 分发独立上下文的子代理去完成调研等任务，完成后返回摘要；每次分发都需要你批准") }},
{ind}    trailingContent = {{
{ind}        Switch(
{ind}            checked = assistant.localTools.contains(LocalToolOption.SubAgents),
{ind}            onCheckedChange = {{ toggleLocalTool(LocalToolOption.SubAgents, it) }}
{ind}        )
{ind}    }}
{ind})
"""


def main() -> int:
    if not TARGET.exists():
        print(f"missing target: {TARGET}", file=sys.stderr)
        return 1
    src = TARGET.read_text(encoding="utf-8")
    if "LocalToolOption.SubAgents" in src:
        print("already patched, skipping", flush=True)
        return 0
    m = ANCHOR_RE.search(src)
    if not m:
        print("anchor (javascript_engine item) not found", file=sys.stderr)
        return 1
    block = BLOCK.format(ind=m.group("indent"))
    src = src[: m.start()] + block + src[m.start():]
    TARGET.write_text(src, encoding="utf-8")
    print("patched AssistantLocalToolPage.kt (Sub-agents switch)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Add ChatUi / AppControl / html-mode switches to AssistantLocalToolPage.kt.

The page hardcodes one Switch per LocalToolOption, so new enum entries are invisible
until a row is added here. Without this, the dual-mode feature has no entry point.
Strict (exit 1 when the anchor is missing) and idempotent.
"""
import re
import sys
from pathlib import Path

TARGET = Path("app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/detail/AssistantLocalToolPage.kt")

# First built-in row (JavaScript engine). New rows are inserted directly above it.
ANCHOR_RE = re.compile(
    r"(?P<indent>[ \t]*)item\(\s*headlineContent = \{\s*"
    r"Text\(stringResource\(R\.string\.assistant_page_local_tools_javascript_engine_title\)\)"
)

BLOCK = """{ind}item(
{ind}    headlineContent = {{ Text("聊天界面皮肤（HTML 模式）") }},
{ind}    supportingContent = {{ Text("允许 AI 编写 HTML 皮肤，改变聊天背景、气泡和悬浮元素") }},
{ind}    trailingContent = {{
{ind}        Switch(
{ind}            checked = assistant.localTools.contains(LocalToolOption.ChatUi),
{ind}            onCheckedChange = {{ toggleLocalTool(LocalToolOption.ChatUi, it) }}
{ind}        )
{ind}    }}
{ind})
{ind}item(
{ind}    headlineContent = {{ Text("当前使用 HTML 模式") }},
{ind}    supportingContent = {{ Text("关闭即恢复原生聊天界面；需要先有 AI 写好的皮肤") }},
{ind}    trailingContent = {{
{ind}        if (me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.isReady) {{
{ind}            val skinStore = me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.store
{ind}            val skinState by skinStore.stateFlow.collectAsStateWithLifecycle()
{ind}            Switch(
{ind}                checked = skinState.htmlModeEnabled,
{ind}                onCheckedChange = {{ skinStore.setMode(it) }}
{ind}            )
{ind}        }}
{ind}    }}
{ind})
{ind}item(
{ind}    headlineContent = {{ Text("应用控制（App Control）") }},
{ind}    supportingContent = {{ Text("允许 AI 读取并修改助手、模型、供应商等设置；每次修改都需要你批准") }},
{ind}    trailingContent = {{
{ind}        Switch(
{ind}            checked = assistant.localTools.contains(LocalToolOption.AppControl),
{ind}            onCheckedChange = {{ toggleLocalTool(LocalToolOption.AppControl, it) }}
{ind}        )
{ind}    }}
{ind})
"""


def main() -> int:
    if not TARGET.exists():
        print(f"missing target: {TARGET}", file=sys.stderr)
        return 1
    src = TARGET.read_text(encoding="utf-8")
    if "LocalToolOption.ChatUi" in src:
        print("already patched, skipping", flush=True)
        return 0
    m = ANCHOR_RE.search(src)
    if not m:
        print("anchor (javascript_engine item) not found", file=sys.stderr)
        return 1
    block = BLOCK.format(ind=m.group("indent"))
    src = src[: m.start()] + block + src[m.start():]
    TARGET.write_text(src, encoding="utf-8")
    print("patched AssistantLocalToolPage.kt (3 switches)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

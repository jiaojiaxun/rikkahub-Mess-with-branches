#!/usr/bin/env python3
"""Embed ChatHtmlLayer into ChatPage.kt (build-time patch).

Regex anchor on the AssistantBackground(...) call, so the layer is inserted directly
above the native background and below the Scaffold that owns the message list and the
input bar. The injected code uses only fully-qualified references plus android.util.Log,
so no imports need to be patched in. Idempotent.
"""
import re
import sys
from pathlib import Path

TARGET = Path("app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt")

AB_RE = re.compile(r"(?P<indent>[ \t]*)AssistantBackground\([^)]*\)", re.DOTALL)

LAYER_BLOCK = """
{ind}// Dual-mode chat: AI-authored html skin layer. Sits above the native background
{ind}// and below the Scaffold, so the native message list and input bar keep working.
{ind}// No-op unless html mode is enabled. Fully-qualified refs only: no new imports.
{ind}if (me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.isReady) {{
{ind}    me.rerere.rikkahub.ui.pages.chat.ChatHtmlLayer(
{ind}        skinStore = me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.store,
{ind}        onBridgeEvent = {{ type, payload ->
{ind}            when (type) {{
{ind}                "send_message" -> {{
{ind}                    val el = payload["text"]
{ind}                    val text = if (el is kotlinx.serialization.json.JsonPrimitive &&
{ind}                        el !is kotlinx.serialization.json.JsonNull
{ind}                    ) el.content else null
{ind}                    if (!text.isNullOrBlank()) {{
{ind}                        vm.handleMessageSend(content = listOf(UIMessagePart.Text(text)))
{ind}                    }}
{ind}                }}
{ind}                "request_exit" -> {{
{ind}                    me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.store.setMode(false)
{ind}                }}
{ind}                else -> android.util.Log.d("ChatHtmlLayer", "skin event: " + type)
{ind}            }}
{ind}        }},
{ind}    )
{ind}}}
"""


def main() -> int:
    if not TARGET.exists():
        print(f"missing target: {TARGET}", file=sys.stderr)
        return 1
    src = TARGET.read_text(encoding="utf-8")
    if "ChatHtmlLayer" in src:
        print("already patched, skipping", flush=True)
        return 0
    m = AB_RE.search(src)
    if not m:
        print("anchor (AssistantBackground) not found", file=sys.stderr)
        return 1
    block = LAYER_BLOCK.format(ind=m.group("indent"))
    src = src[: m.end()] + block + src[m.end():]
    TARGET.write_text(src, encoding="utf-8")
    print("patched ChatPage.kt (html layer embedded)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

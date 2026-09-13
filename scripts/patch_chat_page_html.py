#!/usr/bin/env python3
"""Embed ChatHtmlLayer into ChatPage.kt (build-time patch).

Inserts the html skin layer between AssistantBackground and Scaffold so it sits
above the native background but below the native message list / input bar.
Anchored, idempotent: exits 0 when the marker is already present.
"""
from pathlib import Path

TARGET = Path("app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt")

ANCHOR = (
    "                AssistantBackground(\n"
    "                    setting = setting,\n"
    "                    modifier = Modifier\n"
    "                )\n"
)
ADD = (
    "                AssistantBackground(\n"
    "                    setting = setting,\n"
    "                    modifier = Modifier\n"
    "                )\n"
    "                // Dual-mode chat: AI-authored html skin layer. Rendered only when\n"
    "                // html mode is on (ChatHtmlLayer no-ops otherwise); sits above the\n"
    "                // background and below the native list/input, so chat features keep\n"
    "                // working while the skin styles the visible chrome.\n"
    "                if (me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.isReady) {\n"
    "                    me.rerere.rikkahub.ui.pages.chat.ChatHtmlLayer(\n"
    "                        skinStore = me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.store,\n"
    "                        onBridgeEvent = { type, payload ->\n"
    "                            when (type) {\n"
    "                                \"send_message\" -> {\n"
    "                                    val text = (payload[\"text\"] as? kotlinx.serialization.json.JsonPrimitive)?.content\n"
    "                                    if (!text.isNullOrBlank()) {\n"
    "                                        vm.handleMessageSend(content = listOf(UIMessagePart.Text(text)))\n"
    "                                    }\n"
    "                                }\n"
    "                                \"request_exit\" -> {\n"
    "                                    me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.store.setMode(false)\n"
    "                                }\n"
    "                                \"button_action\" -> {\n"
    "                                    // Widget taps are informational for now: surfaced via\n"
    "                                    // toast so the user sees the bridge works end to end.\n"
    "                                    val action = (payload[\"action\"] as? kotlinx.serialization.json.JsonPrimitive)?.content ?: \"unknown\"\n"
    "                                    toaster.show(\"HTML skin action: $action\")\n"
    "                                }\n"
    "                            }\n"
    "                        },\n"
    "                    )\n"
    "                }\n"
)


def main() -> int:
    if not TARGET.exists():
        print(f"missing target: {TARGET}", flush=True)
        return 1
    src = TARGET.read_text(encoding="utf-8")
    if "ChatHtmlLayer" in src:
        print("already patched, skipping", flush=True)
        return 0
    if ANCHOR not in src:
        print("anchor (AssistantBackground) not found", flush=True)
        return 1
    src = src.replace(ANCHOR, ADD, 1)
    TARGET.write_text(src, encoding="utf-8")
    print("patched ChatPage.kt (html layer embedded)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

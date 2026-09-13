#!/usr/bin/env python3
"""Inject ChatHtmlSkinGlobal.init into RikkaHubApp.onCreate (build-time patch).

Anchored, idempotent: exits 0 without touching the file when the marker is
already present. Runs before assembleRelease in CI.
"""
from pathlib import Path

TARGET = Path("app/src/main/java/me/rerere/rikkahub/RikkaHubApp.kt")

ANCHOR = "        me.rerere.rikkahub.data.ai.tools.local.AgentWorkspace.init(this)\n"
ADD = (
    "        me.rerere.rikkahub.data.ai.tools.local.AgentWorkspace.init(this)\n"
    "\n"
    "        // Dual-mode chat: initialise the global HTML skin store before any UI or\n"
    "        // tool reads it (same early-init pattern as AgentWorkspace above).\n"
    "        me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.init(\n"
    "            context = this,\n"
    "            scope = get(),\n"
    "        )\n"
)


def main() -> int:
    if not TARGET.exists():
        print(f"missing target: {TARGET}", flush=True)
        return 1
    src = TARGET.read_text(encoding="utf-8")
    if "ChatHtmlSkinGlobal" in src:
        print("already patched, skipping", flush=True)
        return 0
    if ANCHOR not in src:
        print("anchor (AgentWorkspace.init) not found", flush=True)
        return 1
    src = src.replace(ANCHOR, ADD, 1)
    TARGET.write_text(src, encoding="utf-8")
    print("patched RikkaHubApp.kt (skin store init)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

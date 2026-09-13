#!/usr/bin/env python3
"""Initialise the dual-mode chat skin store in RikkaHubApp.onCreate (build-time patch).

Regex anchor on the existing AgentWorkspace.init call, which is the very same
early-init pattern, so this stays whitespace-tolerant. Idempotent: exits 0 without
touching the file when the marker is already present.

Note: RikkaHubApp lives in the me.rerere.rikkahub package, so AppScope resolves
without an import, and org.koin.android.ext.android.get is already imported.
"""
import re
import sys
from pathlib import Path

TARGET = Path("app/src/main/java/me/rerere/rikkahub/RikkaHubApp.kt")

INIT_RE = re.compile(
    r"(?P<indent>[ \t]*)me\.rerere\.rikkahub\.data\.ai\.tools\.local\.AgentWorkspace\.init\(this\)"
)

INIT_BLOCK = (
    "\n\n"
    "{ind}// Dual-mode chat: initialise the global HTML skin store before any UI or tool\n"
    "{ind}// reads it. Same early-init pattern as AgentWorkspace above.\n"
    "{ind}me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.init(\n"
    "{ind}    context = this,\n"
    "{ind}    scope = get<AppScope>(),\n"
    "{ind})"
)


def main() -> int:
    if not TARGET.exists():
        print(f"missing target: {TARGET}", file=sys.stderr)
        return 1
    src = TARGET.read_text(encoding="utf-8")
    if "ChatHtmlSkinGlobal" in src:
        print("already patched, skipping", flush=True)
        return 0
    m = INIT_RE.search(src)
    if not m:
        print("anchor (AgentWorkspace.init) not found", file=sys.stderr)
        return 1
    block = INIT_BLOCK.format(ind=m.group("indent"))
    src = src[: m.end()] + block + src[m.end():]
    TARGET.write_text(src, encoding="utf-8")
    print("patched RikkaHubApp.kt (skin store init)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

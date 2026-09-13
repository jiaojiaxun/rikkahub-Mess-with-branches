#!/usr/bin/env python3
"""Inject ChatUi + AppControl tool groups into LocalTools.kt (build-time patch).

Anchored, idempotent replacements: each block exits 0 without touching the file
when its marker is already present. Run before assembleRelease in CI.
"""
from pathlib import Path

TARGET = Path("app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt")

ENUM_ANCHOR = '    @Serializable @SerialName("archive")              data object Archive             : LocalToolOption()\n}'
ENUM_ADD = (
    '    @Serializable @SerialName("archive")              data object Archive             : LocalToolOption()\n'
    '    @Serializable @SerialName("chat_ui")              data object ChatUi               : LocalToolOption()\n'
    '    @Serializable @SerialName("app_control")          data object AppControl            : LocalToolOption()\n}'
)

TOOLS_ANCHOR = "        // Centralised opt-in to needsApproval. Tool factories themselves don't have to know"
TOOLS_ADD = (
    "        if (options.contains(LocalToolOption.ChatUi)) {\n"
    "            tools.addAll(\n"
    "                me.rerere.rikkahub.data.ai.tools.local.createChatUiTools()\n"
    "            )\n"
    "        }\n"
    "        if (options.contains(LocalToolOption.AppControl)) {\n"
    "            tools.addAll(\n"
    "                me.rerere.rikkahub.data.ai.tools.appcontrol.createAppControlTools(\n"
    "                    settingsStore = settingsStore,\n"
    "                )\n"
    "            )\n"
    "        }\n"
    "        // Centralised opt-in to needsApproval. Tool factories themselves don't have to know"
)


def main() -> int:
    if not TARGET.exists():
        print(f"missing target: {TARGET}", flush=True)
        return 1
    src = TARGET.read_text(encoding="utf-8")
    changed = False

    if "chat_ui" not in src:
        if ENUM_ANCHOR not in src:
            print("enum anchor not found", flush=True)
            return 1
        src = src.replace(ENUM_ANCHOR, ENUM_ADD, 1)
        changed = True

    if "LocalToolOption.ChatUi" not in src:
        if TOOLS_ANCHOR not in src:
            print("tools anchor not found", flush=True)
            return 1
        src = src.replace(TOOLS_ANCHOR, TOOLS_ADD, 1)
        changed = True

    if changed:
        TARGET.write_text(src, encoding="utf-8")
        print("patched LocalTools.kt (chat_ui + app_control)", flush=True)
    else:
        print("already patched, skipping", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

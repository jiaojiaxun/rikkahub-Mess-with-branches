#!/usr/bin/env python3
"""Inject the ChatUi (+ AppControl) tool groups into LocalTools.kt (build-time patch).

Anchored, idempotent and whitespace-tolerant: anchors are regexes, so upstream
re-indentation or spacing changes cannot silently break the injection. Each block is
skipped independently when its marker is already present. Run before assembleRelease.
"""
import re
import sys
from pathlib import Path

TARGET = Path("app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt")

ENUM_RE = re.compile(
    r'(?P<indent>[ \t]*)@Serializable[ \t]+@SerialName\("archive"\)[ \t]+'
    r'data object Archive[ \t]*:[ \t]*LocalToolOption\(\)'
)
TOOLS_RE = re.compile(r"(?P<indent>[ \t]*)//[ \t]*Centralised opt-in to needsApproval\.")

ENUM_EXTRA = (
    '\n{ind}@Serializable @SerialName("chat_ui")            data object ChatUi               : LocalToolOption()'
    '\n{ind}@Serializable @SerialName("app_control")        data object AppControl            : LocalToolOption()'
)

TOOLS_BLOCK = (
    "{ind}if (options.contains(LocalToolOption.ChatUi)) {{\n"
    "{ind}    tools.addAll(me.rerere.rikkahub.data.ai.tools.local.createChatUiTools())\n"
    "{ind}}}\n"
    "{ind}if (options.contains(LocalToolOption.AppControl)) {{\n"
    "{ind}    tools.addAll(\n"
    "{ind}        me.rerere.rikkahub.data.ai.tools.appcontrol.createAppControlTools(\n"
    "{ind}            settingsStore = settingsStore,\n"
    "{ind}        )\n"
    "{ind}    )\n"
    "{ind}}}\n"
)


def main() -> int:
    if not TARGET.exists():
        print(f"missing target: {TARGET}", file=sys.stderr)
        return 1
    src = TARGET.read_text(encoding="utf-8")
    changed = False

    if "LocalToolOption.ChatUi" not in src:
        m = ENUM_RE.search(src)
        if not m:
            print("enum anchor (Archive) not found", file=sys.stderr)
            return 1
        extra = ENUM_EXTRA.format(ind=m.group("indent"))
        src = src[: m.end()] + extra + src[m.end():]
        changed = True

    if "createChatUiTools" not in src:
        m = TOOLS_RE.search(src)
        if not m:
            print("tools anchor (needsApproval comment) not found", file=sys.stderr)
            return 1
        block = TOOLS_BLOCK.format(ind=m.group("indent"))
        src = src[: m.start()] + block + src[m.start():]
        changed = True

    if changed:
        TARGET.write_text(src, encoding="utf-8")
        print("patched LocalTools.kt (chat_ui + app_control)", flush=True)
    else:
        print("already patched, skipping", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

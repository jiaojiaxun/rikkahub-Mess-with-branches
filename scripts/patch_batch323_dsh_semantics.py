"""batch323 — three semantic fixes found by adversarial re-reading.

1) The new footnote rendered for every message. The old stats line was silent on
   user messages (no usage -> nothing drawn), but "N 步 · M 轮" has no such gate,
   so user bubbles would grow a "0 步 · 1 轮" line. Gate on ASSISTANT.
2) When the context window is unknown the ring printed "0%", which reads as a
   measured value. Print an em dash instead.
3) The usage sheet printed "used / 0" in the same situation. Print an em dash.
"""

import os

ROOT = os.getcwd()
APP = os.path.join(ROOT, "app/src/main/java/me/rerere/rikkahub")
NERD = os.path.join(APP, "ui/components/message/ChatMessageNerdLine.kt")
CHROME = os.path.join(APP, "ui/components/ai/RhDshChrome.kt")
DIAG = os.path.join(ROOT, "ci_diag_batch323_semantics.txt")

log = []


def note(m):
    print(m)
    log.append(str(m))


def bal(t):
    return (t.count('{') - t.count('}'), t.count('(') - t.count(')'))


def fix_nerd():
    src = open(NERD, "r", encoding="utf-8").read()
    before = bal(src)
    old = (
        "    val rhSteps = message.parts.count { it is UIMessagePart.Tool } // rhDshFootnote320\n"
        "    val rhRounds = rhSteps + 1\n"
        "    Text(\n"
        "        text = rhSteps.toString() + \" 步 · \" + rhRounds.toString() + \" 轮\",\n"
        "        style = MaterialTheme.typography.labelSmall.copy(color = color),\n"
        "        modifier = modifier.padding(horizontal = 4.dp),\n"
        "    )\n"
    )
    new = (
        "    if (message.role == me.rerere.ai.core.MessageRole.ASSISTANT) { // rhDshFootnote323\n"
        "        val rhSteps = message.parts.count { it is UIMessagePart.Tool }\n"
        "        val rhRounds = rhSteps + 1\n"
        "        Text(\n"
        "            text = rhSteps.toString() + \" 步 · \" + rhRounds.toString() + \" 轮\",\n"
        "            style = MaterialTheme.typography.labelSmall.copy(color = color),\n"
        "            modifier = modifier.padding(horizontal = 4.dp),\n"
        "        )\n"
        "    }\n"
    )
    if src.count(old) != 1:
        raise ValueError("nerd anchor count=" + str(src.count(old)))
    src = src.replace(old, new)
    after = bal(src)
    if after != before:
        raise ValueError("nerd balance " + str(before) + " -> " + str(after))
    open(NERD, "w", encoding="utf-8").write(src)
    note("nerd: assistant-only footnote OK")


def fix_chrome():
    src = open(CHROME, "r", encoding="utf-8").read()
    before = bal(src)

    ring_old = "            text = rhDshPercent(fraction),\n            fontSize = 11.sp,"
    ring_new = "            text = if (usage.contextLimit == null) \"—\" else rhDshPercent(fraction),\n            fontSize = 11.sp,"
    if src.count(ring_old) != 1:
        raise ValueError("ring anchor count=" + str(src.count(ring_old)))
    src = src.replace(ring_old, ring_new)

    sheet_old = "                            text = rhDshFormatTokens(usage.contextUsed) + \" / \" + rhDshFormatTokens(usage.contextLimit ?: 0),"
    sheet_new = "                            text = if (usage.contextLimit == null) \"—\" else rhDshFormatTokens(usage.contextUsed) + \" / \" + rhDshFormatTokens(usage.contextLimit),"
    if src.count(sheet_old) != 1:
        raise ValueError("sheet anchor count=" + str(src.count(sheet_old)))
    src = src.replace(sheet_old, sheet_new)

    after = bal(src)
    if after != before:
        raise ValueError("chrome balance " + str(before) + " -> " + str(after))
    open(CHROME, "w", encoding="utf-8").write(src)
    note("chrome: unknown-limit placeholders OK")


def main():
    errors = []
    for name, fn in (("nerd", fix_nerd), ("chrome", fix_chrome)):
        try:
            fn()
        except Exception as exc:
            errors.append(name + " FAILED: " + str(exc))
            note(name + " FAILED: " + str(exc))
    open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
    if errors:
        print("::error title=rhDsh323::" + " | ".join(errors))
    else:
        print("::error title=rhDsh323::OK footnote role gate + unknown-limit dash")


main()
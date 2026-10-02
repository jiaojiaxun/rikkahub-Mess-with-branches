#!/usr/bin/env python3
"""Batch-11: "导出对话时可以选择不包含思考过程".

ui/pages/chat/Export.kt already had a per-export option for the IMAGE exporter
(ImageExportOptions.expandReasoning, surfaced as a Switch inside the image card). The
Markdown exporter had no such control, and it writes thinking into the file in two places:

  * a message-level `UIMessagePart.Reasoning`                 -> "> ..." block
  * a `UIMessagePart.Reasoning` nested in a tool call output  -> "> ..." block

So an exported .md always leaked the model's chain of thought, which is often exactly what
you do NOT want when handing a transcript to someone.

Fix: one Switch in the export sheet, applied to the Markdown export only.

  * `exportToMarkdown(..., includeReasoning: Boolean = true)` - default true keeps every
    other caller byte-for-byte identical.
  * both Reasoning branches are wrapped in `if (includeReasoning)`.
  * the option is deliberately NOT nested inside the clickable Markdown card: a Switch
    inside a card whose onClick performs the export would fire both handlers on a tap. It
    sits as its own row above the format list instead.

Anchored, idempotent, loud (::error + exit 1).
"""
import sys
from pathlib import Path

FAILURES = []
TARGET = Path("app/src/main/java/me/rerere/rikkahub/ui/pages/chat/Export.kt")
MARKER = "rh-batch11"


def fail(msg):
    print(f"::error file={TARGET}::batch11 patch failed: {msg}", flush=True)
    FAILURES.append(msg)


def flatten(text):
    kept = []
    indexes = []
    for index, char in enumerate(text):
        if not char.isspace():
            kept.append(char)
            indexes.append(index)
    return "".join(kept), indexes


def match_flat(src, pattern):
    flat_src, indexes = flatten(src)
    flat_pattern, _ = flatten(pattern)
    if not flat_pattern:
        return None
    positions = flat_src.count(flat_pattern)
    if positions != 1:
        return ("count", positions)
    start_flat = flat_src.find(flat_pattern)
    end_flat = start_flat + len(flat_pattern) - 1
    return (indexes[start_flat], indexes[end_flat] + 1)


def replace_once(src, pattern, replacement, label):
    found = match_flat(src, pattern)
    if found is None:
        fail(f"{label}: empty anchor")
        return None
    if isinstance(found[0], str):
        fail(f"{label}: expected 1 match, found {found[1]}")
        return None
    start, end = found
    return src[:start] + replacement + src[end:]


SIGNATURE_OLD = """private fun exportToMarkdown(
    context: Context,
    conversation: Conversation,
    messages: List<UIMessage>
) {"""

SIGNATURE_NEW = """private fun exportToMarkdown(
    context: Context,
    conversation: Conversation,
    messages: List<UIMessage>,
    // rh-batch11: markdown-without-thinking - when false the exported Markdown omits every
    // reasoning block, both the message-level ones and those nested in tool call outputs.
    // Defaults to true so any other caller keeps the previous behaviour.
    includeReasoning: Boolean = true,
) {"""

MESSAGE_REASONING_OLD = """                    is UIMessagePart.Reasoning -> {
                        part.reasoning.lines()
                            .filter { it.isNotBlank() }
                            .map { "> $it" }
                            .forEach {
                                append(it)
                            }
                        appendLine()
                        appendLine()
                    }"""

MESSAGE_REASONING_NEW = """                    is UIMessagePart.Reasoning -> {
                        // rh-batch11: markdown-without-thinking
                        if (includeReasoning) {
                            part.reasoning.lines()
                                .filter { it.isNotBlank() }
                                .map { "> $it" }
                                .forEach {
                                    append(it)
                                }
                            appendLine()
                            appendLine()
                        }
                    }"""

TOOL_REASONING_OLD = """                                    is UIMessagePart.Reasoning -> {
                                        outputPart.reasoning.lines()
                                            .filter { it.isNotBlank() }
                                            .forEach {
                                                append("> $it")
                                                appendLine()
                                            }
                                    }"""

TOOL_REASONING_NEW = """                                    is UIMessagePart.Reasoning -> {
                                        // rh-batch11: markdown-without-thinking - tool outputs can
                                        // carry reasoning too (e.g. a summariser's trace).
                                        if (includeReasoning) {
                                            outputPart.reasoning.lines()
                                                .filter { it.isNotBlank() }
                                                .forEach {
                                                    append("> $it")
                                                    appendLine()
                                                }
                                        }
                                    }"""

STATE_OLD = "    var imageExportOptions by remember { mutableStateOf(ImageExportOptions()) }"

STATE_NEW = """    var imageExportOptions by remember { mutableStateOf(ImageExportOptions()) }
    // rh-batch11: markdown-without-thinking - applies to the Markdown export only.
    var includeReasoning by remember { mutableStateOf(true) }"""

SHEET_HEAD_OLD = "                Text(text = stringResource(id = R.string.chat_page_export_format))"

SHEET_HEAD_NEW = """                Text(text = stringResource(id = R.string.chat_page_export_format))

                // rh-batch11: markdown-without-thinking - its own row rather than a row inside
                // the Markdown card, whose onClick performs the export (a Switch in there would
                // trigger both handlers).
                ListItem(
                    headlineContent = { Text("包含思考过程（Markdown 导出）") },
                    supportingContent = {
                        Text("关闭后导出的 .md 不含模型的思考过程")
                    },
                    trailingContent = {
                        Switch(
                            checked = includeReasoning,
                            onCheckedChange = { includeReasoning = it }
                        )
                    }
                )"""

CALL_OLD = "exportToMarkdown(context, conversation, selectedMessages)"

CALL_NEW = "exportToMarkdown(context, conversation, selectedMessages, includeReasoning)"


def main():
    if not TARGET.exists():
        fail("file not found")
        print("batch11 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1
    src = TARGET.read_text(encoding="utf-8")
    if MARKER in src:
        print("already patched: " + str(TARGET), flush=True)
        return 0
    original = src

    for old, new, label in (
        (SIGNATURE_OLD, SIGNATURE_NEW, "exportToMarkdown signature"),
        (MESSAGE_REASONING_OLD, MESSAGE_REASONING_NEW, "message reasoning"),
        (TOOL_REASONING_OLD, TOOL_REASONING_NEW, "tool reasoning"),
        (STATE_OLD, STATE_NEW, "state"),
        (SHEET_HEAD_OLD, SHEET_HEAD_NEW, "sheet switch row"),
        (CALL_OLD, CALL_NEW, "call site"),
    ):
        src = replace_once(src, old, new, label)
        if src is None:
            print("batch11 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
            return 1

    if src == original or MARKER not in src:
        fail("nothing changed")
        print("batch11 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1

    TARGET.write_text(src, encoding="utf-8")
    print("patched: " + str(TARGET), flush=True)
    print("batch11 patches applied", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Batch-13: make the batch10 title hint actionable.

While locating an unrelated function in ChatService.kt I found that the fork ALREADY defines

    enum class ChatErrorSolution {
        CheckTitleModelSettings,
    }

i.e. the error stream has a mechanism for attaching a one-tap remedy to an error (the error card
renders the matching action). Batch-10 added the missing-model hint but sent it as a plain
message, so it told the user what was wrong without offering the way to fix it.

This wires the existing enum constant into that call, matching how upstream surfaces the same
condition.

Ordering note: this patches TEXT INSERTED BY patch_batch10.py, so it must run after it. The
workflow applies scripts/patch_batch*.py in `sort -V` order, and batch10 < batch13 numerically,
so the anchor is guaranteed to exist. The anchor is intentionally the exact inserted call
(including the message literal) so it can only ever match batch10's block.

Anchored, idempotent, loud (::error + exit 1).
"""
import sys
from pathlib import Path

FAILURES = []
TARGET = Path("app/src/main/java/me/rerere/rikkahub/service/ChatService.kt")
MARKER = "rh-batch13"


def fail(msg):
    print(f"::error file={TARGET}::batch13 patch failed: {msg}", flush=True)
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


HINT_OLD = '''        addError(
            IllegalStateException(
                "没有可用的标题生成模型。请在 设置 → 模型 中指定标题模型，或至少启用一个提供商。"
            ),
            conversationId = conversationId,
            title = "无法生成标题",
        )'''

HINT_NEW = '''        addError(
            IllegalStateException(
                "没有可用的标题生成模型。请在 设置 → 模型 中指定标题模型，或至少启用一个提供商。"
            ),
            conversationId = conversationId,
            title = "无法生成标题",
            // rh-batch13: attach the remedy the error stream already models
            // (ChatErrorSolution.CheckTitleModelSettings) so the error card can offer a direct
            // jump to the title-model setting instead of only describing the problem.
            solution = ChatErrorSolution.CheckTitleModelSettings,
        )'''


def main():
    if not TARGET.exists():
        fail("file not found")
        print("batch13 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1
    src = TARGET.read_text(encoding="utf-8")
    if MARKER in src:
        print("already patched: " + str(TARGET), flush=True)
        return 0
    if HINT_OLD.split("\n")[1].strip() not in src:
        fail(
            "batch10's hint block is missing - patch_batch13 depends on patch_batch10 "
            "having run first (workflow applies patch_batch*.py in sort -V order)"
        )
        print("batch13 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1

    src = replace_once(src, HINT_OLD, HINT_NEW, "title hint solution")
    if src is None:
        print("batch13 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1

    if MARKER not in src:
        fail("nothing changed")
        print("batch13 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1

    TARGET.write_text(src, encoding="utf-8")
    print("patched: " + str(TARGET), flush=True)
    print("batch13 patches applied", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

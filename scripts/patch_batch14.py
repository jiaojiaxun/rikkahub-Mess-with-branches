#!/usr/bin/env python3
"""Batch-14: "修复分叉对话标题序号重复叠加".

Root cause found in ChatService.forkConversationAtMessage: the forked Conversation is built as

    Conversation(
        id = Uuid.random(),
        assistantId = ...,
        messageNodes = copiedNodes,
        customSystemPrompt = ..., modeInjectionIds = ..., lorebookIds = ...,
    )

with NO title - so `title` falls back to its default "" and the fork is created untitled. Because
generateTitle's gate is `force || title.isBlank()`, the fork then gets an unrelated
AI-generated title and the branch loses all visible lineage with its parent.

Upstream's fix for this is a numbered fork title that is made stack-proof by stripping any
existing trailing "(n)" before appending a new one. That is what this does:

  * nextForkTitle(parent) lives in data/model/Conversation.kt - a pure function next to the
    Conversation type it describes, and in a package the CI test step already runs.
  * The strip loop removes EVERY trailing "(n)", not just one, so an already-corrupted title
    from an older build ("标题 (1) (1)") collapses back to "标题" instead of gaining a third
    suffix. A single replace() would leave "标题 (1)" and turn it into "标题 (1) (2)".
  * Numbering is monotonic off the parent's OWN number: "X" -> "X (2)", "X (2)" -> "X (3)",
    "X (1) (1)" -> "X (2)". Two forks of the same parent therefore never collide, which plain
    "always append (1)" would.
  * A blank/whitespace parent title stays blank on purpose: a brand-new conversation has no
    title yet, and blank is exactly what lets generateTitle name the fork normally. A title
    that is nothing but a suffix ("(1)") is also returned unchanged rather than becoming "(2)".

Behaviour change worth noting: a fork of a titled conversation now keeps the lineage name
instead of receiving a fresh AI title.

Anchored, idempotent, loud (::error + exit 1).
"""
import sys
from pathlib import Path

FAILURES = []
CONVERSATION = Path("app/src/main/java/me/rerere/rikkahub/data/model/Conversation.kt")
CHAT_SERVICE = Path("app/src/main/java/me/rerere/rikkahub/service/ChatService.kt")
TEST_FILE = Path("app/src/test/java/me/rerere/rikkahub/data/model/ForkTitleTest.kt")
MARKER = "rh-batch14"


def fail(msg, target=None):
    where = f" file={target}" if target else ""
    print(f"::error{where}::batch14 patch failed: {msg}", flush=True)
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


def replace_once(src, pattern, replacement, label, target):
    found = match_flat(src, pattern)
    if found is None:
        fail(f"{label}: empty anchor", target)
        return None
    if isinstance(found[0], str):
        fail(f"{label}: expected 1 match, found {found[1]}", target)
        return None
    start, end = found
    return src[:start] + replacement + src[end:]


CONVERSATION_ANCHOR_OLD = """@Serializable
data class MessageNode(
    val id: Uuid = Uuid.random(),"""

CONVERSATION_ANCHOR_NEW = '''/** rh-batch14: a trailing fork-sequence suffix, e.g. "标题 (2)". */
private val FORK_TITLE_SUFFIX_REGEX = Regex("""\\s*\\((\\d+)\\)\\s*$""")

/**
 * rh-batch14: title for a conversation forked from [parentTitle].
 *
 * Every trailing "(n)" is stripped before a new number is appended, so forking a fork can never
 * accumulate suffixes ("标题 (1) (1) (1)"). The number is taken from the parent's own suffix and
 * incremented, so sibling forks of the same parent get distinct names.
 *
 * Returns "" for a blank parent title: a conversation that has no title yet should let
 * generateTitle name the fork normally rather than inheriting an empty numbered name.
 */
fun nextForkTitle(parentTitle: String): String {
    val parent = parentTitle.trim()
    if (parent.isEmpty()) return ""

    var base = parent
    var parentNumber: Int? = null
    while (true) {
        // $ -anchored, so each pass removes exactly one trailing suffix.
        val match = FORK_TITLE_SUFFIX_REGEX.find(base) ?: break
        if (parentNumber == null) {
            parentNumber = match.groupValues[1].toIntOrNull()
        }
        base = base.substring(0, match.range.first).trimEnd()
    }
    // The title was nothing but a suffix ("(1)"); leave it alone instead of inventing "(2)".
    if (base.isEmpty()) return parent

    return "$base (${(parentNumber ?: 1) + 1})"
}

@Serializable
data class MessageNode(
    val id: Uuid = Uuid.random(),'''

IMPORT_OLD = "import me.rerere.rikkahub.data.model.Conversation"

IMPORT_NEW = """import me.rerere.rikkahub.data.model.Conversation
import me.rerere.rikkahub.data.model.nextForkTitle"""

FORK_OLD = """        val forkConversation = Conversation(
            id = Uuid.random(),
            assistantId = currentConversation.assistantId,
            messageNodes = copiedNodes,"""

FORK_NEW = """        val forkConversation = Conversation(
            id = Uuid.random(),
            assistantId = currentConversation.assistantId,
            // rh-batch14: carry the parent's title over instead of leaving the fork untitled.
            // A blank title here made generateTitle treat the branch as a brand-new chat and
            // name it after its own first messages, erasing the lineage. nextForkTitle()
            // numbers it and strips any pre-existing suffix, so repeated forking cannot stack.
            title = nextForkTitle(currentConversation.title),
            messageNodes = copiedNodes,"""

TEST_BODY = '''package me.rerere.rikkahub.data.model

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * rh-batch14: "修复分叉对话标题序号重复叠加".
 *
 * The stacking case is the point of these assertions: forking a fork used to append another
 * suffix on top of the previous one. nextForkTitle strips every existing trailing "(n)" before
 * appending, so the suffix count never grows and the number keeps moving forward.
 */
class ForkTitleTest {
    @Test
    fun `blank parent title stays blank`() {
        assertEquals("", nextForkTitle(""))
        assertEquals("", nextForkTitle("   "))
    }

    @Test
    fun `first fork of an unnumbered title is the second copy`() {
        assertEquals("标题 (2)", nextForkTitle("标题"))
    }

    @Test
    fun `forking a fork advances the number instead of stacking`() {
        assertEquals("标题 (3)", nextForkTitle("标题 (2)"))
        assertEquals("标题 (4)", nextForkTitle("标题 (3)"))
    }

    @Test
    fun `already stacked suffixes collapse to a single number`() {
        // The regression itself: a title corrupted by an older build must not gain a third
        // suffix, and must not keep the stale one either.
        assertEquals("标题 (2)", nextForkTitle("标题 (1) (1)"))
        assertEquals("标题 (3)", nextForkTitle("标题 (1) (2)"))
    }

    @Test
    fun `suffix without a preceding space is recognised`() {
        assertEquals("标题 (8)", nextForkTitle("标题(7)"))
    }

    @Test
    fun `surrounding whitespace is trimmed`() {
        assertEquals("标题 (2)", nextForkTitle("  标题  "))
        assertEquals("标题 (3)", nextForkTitle(" 标题 (2) "))
    }

    @Test
    fun `non numeric parentheses are left intact`() {
        assertEquals("标题 (草稿) (2)", nextForkTitle("标题 (草稿)"))
    }

    @Test
    fun `a title that is only a suffix is returned unchanged`() {
        assertEquals("(1)", nextForkTitle("(1)"))
    }
}
'''


def main():
    # ---- data/model/Conversation.kt : the pure helper -------------------------------
    if not CONVERSATION.exists():
        fail("Conversation.kt not found", str(CONVERSATION))
    else:
        src = CONVERSATION.read_text(encoding="utf-8")
        if MARKER in src:
            print("already patched: " + str(CONVERSATION), flush=True)
        else:
            new = replace_once(
                src, CONVERSATION_ANCHOR_OLD, CONVERSATION_ANCHOR_NEW, "nextForkTitle", str(CONVERSATION)
            )
            if new is not None:
                CONVERSATION.write_text(new, encoding="utf-8")
                print("patched: " + str(CONVERSATION), flush=True)

    # ---- ChatService.kt : use it when building the fork -------------------------------
    if not CHAT_SERVICE.exists():
        fail("ChatService.kt not found", str(CHAT_SERVICE))
    else:
        src = CHAT_SERVICE.read_text(encoding="utf-8")
        if MARKER in src:
            print("already patched: " + str(CHAT_SERVICE), flush=True)
        else:
            original = src
            for old, new, label in (
                (IMPORT_OLD, IMPORT_NEW, "nextForkTitle import"),
                (FORK_OLD, FORK_NEW, "fork title"),
            ):
                src = replace_once(src, old, new, label, str(CHAT_SERVICE))
                if src is None:
                    break
            if src is not None and src != original:
                CHAT_SERVICE.write_text(src, encoding="utf-8")
                print("patched: " + str(CHAT_SERVICE), flush=True)

    # ---- the test ---------------------------------------------------------------------
    # The CI test step already filters on me.rerere.rikkahub.data.model.*, so a new test in that
    # package runs without any workflow change.
    if TEST_FILE.exists():
        print("already present: " + str(TEST_FILE), flush=True)
    else:
        TEST_FILE.parent.mkdir(parents=True, exist_ok=True)
        TEST_FILE.write_text(TEST_BODY, encoding="utf-8")
        print("created: " + str(TEST_FILE), flush=True)

    if FAILURES:
        print("batch14 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1
    print("batch14 patches applied", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

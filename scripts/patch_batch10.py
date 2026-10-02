#!/usr/bin/env python3
"""Batch-10: new model support (Claude Opus/Sonnet 5.5, Gemini 4) + a title-model hint.

Two of the requested upstream features, both small and self-contained:

1. "新增 Claude Opus 5.5 / Sonnet 5.5 和 Gemini 4 模型支持"
   The fork resolves context length from a local rule table instead of the model DSL, so a
   brand-new family needs an explicit rule or it silently falls back to the catalog / null.
   The 5.5 Claude pair is matched before the generic "claude" rule, and Gemini 4 before the
   generic "gemini" rule. Matching is on the normalised key, so claude-opus-5.5, claude-opus-5-5
   and Claude Opus 5.5 all hit the same rule.

   Chosen context lengths are the conservative documented defaults for these families
   (200K for Anthropic, 1M for Gemini). Under-reporting only makes compaction run earlier;
   over-reporting would overflow the provider, so the safe direction is deliberate.

2. "生成标题找不到可用模型时会给出提示"
   generateTitle used to `return@runCatching` silently when neither the configured title
   model nor the fast model could be resolved, so titles stayed blank with no explanation.
   A one-hour cooldown keeps the hint from becoming one popup per message.

Anchored, idempotent, loud (::error + exit 1).
"""
import sys
from pathlib import Path

FAILURES = []
RESOLVER = Path("app/src/main/java/me/rerere/rikkahub/data/model/ModelContextLengthResolver.kt")
RESOLVER_TEST = Path("app/src/test/java/me/rerere/rikkahub/data/model/ModelContextLengthResolverTest.kt")
CHAT_SERVICE = Path("app/src/main/java/me/rerere/rikkahub/service/ChatService.kt")
MARKER = "rh-batch10"


def fail(msg, target=None):
    where = f" file={target}" if target else ""
    print(f"::error{where}::batch10 patch failed: {msg}", flush=True)
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


def patch_file(path, label, edits, marker=None):
    if not path.exists():
        fail(f"{label}: file not found ({path})", str(path))
        return
    src = path.read_text(encoding="utf-8")
    if marker is not None and marker in src:
        print(f"already patched: {path}", flush=True)
        return
    original = src
    for old, new, edit_label in edits:
        src = replace_once(src, old, new, f"{label}/{edit_label}", str(path))
        if src is None:
            return
    if src == original:
        fail(f"{label}: nothing changed", str(path))
        return
    path.write_text(src, encoding="utf-8")
    print(f"patched: {path}", flush=True)


# --------------------------------------------------------------------------------------
# Context-length rules for the new families
# --------------------------------------------------------------------------------------

CLAUDE_RULE_OLD = 'ContextRule(listOf("claude"), 200_000),'

CLAUDE_RULE_NEW = '''// rh-batch10: Claude Opus 5.5 / Sonnet 5.5. Matched before the generic "claude" rule;
        // the normalised key folds dots and dashes, so opus-5.5 / opus-5-5 / opus5.5 all match.
        ContextRule(listOf("opus5"), 200_000),
        ContextRule(listOf("sonnet5"), 200_000),
        ContextRule(listOf("claude"), 200_000),'''

GEMINI_RULE_OLD = 'ContextRule(listOf("gemini"), 1_048_576),'

GEMINI_RULE_NEW = '''// rh-batch10: Gemini 4 family (before the generic "gemini" rule).
        ContextRule(listOf("gemini4"), 1_048_576),
        ContextRule(listOf("gemini"), 1_048_576),'''

TEST_ANCHOR = '''        assertEquals(200_000, resolver.knownContextLengthForTesting("claude-3.7-sonnet"))'''

TEST_NEW = '''        assertEquals(200_000, resolver.knownContextLengthForTesting("claude-3.7-sonnet"))
        // rh-batch10: newly supported families.
        assertEquals(200_000, resolver.knownContextLengthForTesting("claude-opus-5.5"))
        assertEquals(200_000, resolver.knownContextLengthForTesting("claude-sonnet-5-5"))
        assertEquals(1_048_576, resolver.knownContextLengthForTesting("gemini-4-pro"))'''


# --------------------------------------------------------------------------------------
# Title-model hint
# --------------------------------------------------------------------------------------

CONST_OLD = "private const val MAX_FULL_CONTEXT_MAP_GROUPS = 8"

CONST_NEW = """/**
 * rh-batch10:title-model-hint - at most one "no title model" hint per hour. A blank title is
 * retried on every message, so an uncooled hint would pop up per message (the exact spam the
 * surrounding code avoids for 429s).
 */
private const val TITLE_MODEL_HINT_COOLDOWN_MS = 60 * 60 * 1000L

private const val MAX_FULL_CONTEXT_MAP_GROUPS = 8"""

FIELD_OLD = "private val streamingPersistenceSequence = AtomicLong(0L)"

FIELD_NEW = """/** rh-batch10:title-model-hint - elapsed-realtime of the last hint shown. */
private val titleModelMissingNotifiedAt = AtomicLong(0L)

private val streamingPersistenceSequence = AtomicLong(0L)"""

TITLE_OLD = """            val model = settings.findModelById(settings.titleModelId, fallback = settings.fastModelId)
                ?: return@runCatching"""

TITLE_NEW = """            val model = settings.findModelById(settings.titleModelId, fallback = settings.fastModelId)
                ?: run {
                    // rh-batch10:title-model-hint - previously silent, so the conversation just
                    // stayed untitled with nothing to explain why.
                    notifyTitleModelUnavailable(conversationId, settings.titleModelId)
                    return@runCatching
                }"""

HELPER_ANCHOR = """    // ---- 生成建议 ----"""

HELPER_NEW = '''    /**
     * rh-batch10:title-model-hint - surfaces a configuration problem (no usable title model and
     * no usable fast model) through the normal error stream, rate-limited so it cannot become a
     * popup per message. Transient failures (429s, network) stay logged only - see the
     * onFailure branch below.
     */
    private fun notifyTitleModelUnavailable(conversationId: Uuid, titleModelId: Uuid?) {
        val now = SystemClock.elapsedRealtime()
        val last = titleModelMissingNotifiedAt.get()
        if (last != 0L && now - last < TITLE_MODEL_HINT_COOLDOWN_MS) return
        if (!titleModelMissingNotifiedAt.compareAndSet(last, now)) return
        Log.w(TAG, "generateTitle: no usable model (titleModelId=$titleModelId)")
        addError(
            IllegalStateException(
                "没有可用的标题生成模型。请在 设置 → 模型 中指定标题模型，或至少启用一个提供商。"
            ),
            conversationId = conversationId,
            title = "无法生成标题",
        )
    }

    // ---- 生成建议 ----'''


def main():
    patch_file(
        RESOLVER,
        "resolver",
        [
            (CLAUDE_RULE_OLD, CLAUDE_RULE_NEW, "claude 5.5 rules"),
            (GEMINI_RULE_OLD, GEMINI_RULE_NEW, "gemini 4 rule"),
        ],
        marker=MARKER,
    )

    patch_file(
        RESOLVER_TEST,
        "resolver test",
        [(TEST_ANCHOR, TEST_NEW, "new family assertions")],
        marker=MARKER,
    )

    patch_file(
        CHAT_SERVICE,
        "ChatService",
        [
            (CONST_OLD, CONST_NEW, "hint cooldown constant"),
            (FIELD_OLD, FIELD_NEW, "hint cooldown field"),
            (TITLE_OLD, TITLE_NEW, "generateTitle hint"),
            (HELPER_ANCHOR, HELPER_NEW, "helper"),
        ],
        marker=MARKER,
    )

    if FAILURES:
        print("batch10 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1
    print("batch10 patches applied", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

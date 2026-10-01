#!/usr/bin/env python3
"""Batch-2 build-time patches. Same convention as patch_batch1.py: anchored, idempotent,
loud (::error + exit 1 on a missing anchor), whitespace-tolerant.

1. UIMessage.generationMillis + StreamChunkHandler timing (real TPS).
2. ChatList: latched stream-follow that follows the END of the list; top padding
   includes the skin header reservation; loading row readable over a skin.
3. chat_ui_write description: mandatory skin layout rules.
"""
import re
import sys
from pathlib import Path

FAILURES = []

MESSAGE = "ai/src/main/java/me/rerere/ai/ui/Message.kt"
HANDLER = "ai/src/main/java/me/rerere/ai/ui/StreamChunkHandler.kt"
CHAT_LIST = "app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt"
CHAT_UI_TOOLS = "app/src/main/java/me/rerere/rikkahub/data/ai/tools/local/ChatUiTools.kt"


def fail(path, msg):
    print(f"::error file={path}::batch2 patch failed: {msg}", flush=True)
    FAILURES.append(f"{path}: {msg}")


def patch(path, marker, transform):
    p = Path(path)
    if not p.exists():
        fail(path, "file not found")
        return
    src = p.read_text(encoding="utf-8")
    if marker in src:
        print(f"already patched: {path}", flush=True)
        return
    try:
        out = transform(src)
    except Exception as e:  # report instead of a bare traceback
        fail(path, f"transform error: {e}")
        return
    if not out or out == src or marker not in out:
        fail(path, "anchor not found")
        return
    p.write_text(out, encoding="utf-8")
    print(f"patched: {path}", flush=True)


def block_end(src, open_brace_index):
    depth = 0
    for j in range(open_brace_index, len(src)):
        if src[j] == "{":
            depth += 1
        elif src[j] == "}":
            depth -= 1
            if depth == 0:
                return j + 1
    return -1


# ------------------------------------------------------------- 1. TPS timing

def t_message(src):
    pat = re.compile(r"(val translation: String\? = null)(\s*\)\s*\{)")
    ms = list(pat.finditer(src))
    if len(ms) != 1:
        return None
    m = ms[0]
    ins = (
        m.group(1) + ",\n"
        "    // rh-batch2:tps - time the final request spent streaming output (first -> last\n"
        "    // chunk), excluding time-to-first-token and tool waits. Null when not measured.\n"
        "    val generationMillis: Long? = null" + m.group(2)
    )
    return src[:m.start()] + ins + src[m.end():]


HANDLER_FIELDS = """    // rh-batch2:tps - wall-clock of the first / latest output chunk of this stream.
    private var firstOutputAt = 0L
    private var lastOutputAt = 0L

"""

HANDLER_TRACK = """        if (chunk.isModelOutput()) {
            val now = System.currentTimeMillis()
            if (firstOutputAt == 0L) firstOutputAt = now
            lastOutputAt = now
        }
"""

HANDLER_FN = """

/** Chunks that carry generated output (used for the TPS window). */
private fun StreamChunk.isModelOutput(): Boolean = when (this) {
    is StreamChunk.TextDelta,
    is StreamChunk.ReasoningDelta,
    is StreamChunk.ToolCallStart,
    is StreamChunk.ToolCallDelta,
    is StreamChunk.ImageDelta,
    is StreamChunk.ImageSnapshot,
    is StreamChunk.ServerToolInputDelta -> true
    else -> false
}
"""


def t_handler(src):
    # fields
    anchor = "    private val textPartIndexes = mutableMapOf<String, Int>()\n"
    if src.count(anchor) != 1:
        return None
    src = src.replace(anchor, HANDLER_FIELDS + anchor, 1)
    # tracking in handle()
    m = re.compile(r"(\n[ \t]*)val updatedMessage = append\(targetMessages\.last\(\), chunk\)").search(src)
    if not m:
        return None
    src = src[:m.start()] + "\n" + HANDLER_TRACK.rstrip("\n") + src[m.start():]
    # Finish: store the window and reset
    m = re.compile(
        r"is StreamChunk\.Finish -> copy\(\s*"
        r"finishedAt = Clock\.System\.now\(\)\.toLocalDateTime\(TimeZone\.currentSystemDefault\(\)\)\s*\)"
    ).search(src)
    if not m:
        return None
    repl = (
        "is StreamChunk.Finish -> copy(\n"
        "                finishedAt = Clock.System.now().toLocalDateTime(TimeZone.currentSystemDefault()),\n"
        "                // Replaced (not summed) per step, matching TokenUsage.merge which keeps the\n"
        "                // last step's completion tokens. Windows under 50ms (single-chunk streams)\n"
        "                // are not a meaningful speed sample.\n"
        "                generationMillis = (lastOutputAt - firstOutputAt)\n"
        "                    .takeIf { firstOutputAt > 0L && it >= 50L },\n"
        "            ).also { firstOutputAt = 0L; lastOutputAt = 0L }"
    )
    src = src[:m.start()] + repl + src[m.end():]
    # non-streaming results cannot be timed: clear any stale value
    old_a = "        usage = result.usage,\n        finishedAt = Clock.System.now().toLocalDateTime(TimeZone.currentSystemDefault()),\n    ).finishReasoning()"
    if src.count(old_a) != 1:
        return None
    src = src.replace(old_a, old_a.replace("    ).finishReasoning()", "        generationMillis = null,\n    ).finishReasoning()"), 1)
    old_b = "            finishedAt = incoming.finishedAt,\n        ).finishReasoning()"
    if src.count(old_b) != 1:
        return None
    src = src.replace(old_b, "            finishedAt = incoming.finishedAt,\n            generationMillis = null,\n        ).finishReasoning()", 1)
    return src.rstrip() + HANDLER_FN


# ------------------------------------------------------------- 2. ChatList

FOLLOW_BLOCK = """// rh-batch2:scroll - latched stream-follow. The old code called
            // requestScrollToItem(lastGroupIndex), i.e. the TOP of the streaming reply: as soon
            // as the reply grew taller than the screen every update yanked the view back to
            // the start of the reply. Now: follow the END of the list, and only stop following
            // when the user scrolls away (re-latch by scrolling back to the bottom).
            var rhFollowStream by remember { mutableStateOf(true) }
            LaunchedEffect(state) {
                snapshotFlow { state.isScrollInProgress }.collect { scrolling ->
                    if (!scrolling) {
                        val info = state.layoutInfo
                        val last = info.visibleItemsInfo.lastOrNull()
                        rhFollowStream = last == null || last.index >= info.totalItemsCount - 1
                    }
                }
            }
            if (settings.displaySetting.enableAutoScroll) {
                LaunchedEffect(state, loadingState) {
                    if (!loadingState) return@LaunchedEffect
                    snapshotFlow {
                        val info = state.layoutInfo
                        info.totalItemsCount to (info.visibleItemsInfo.lastOrNull()?.let { it.offset + it.size } ?: 0)
                    }.collect { (count, _) ->
                        if (rhFollowStream && !state.isScrollInProgress && count > 0) {
                            state.requestScrollToItem(count - 1)
                        }
                    }
                }
            }"""


def t_chat_list(src):
    m = re.compile(r"if \(settings\.displaySetting\.enableAutoScroll\) \{").search(src)
    if not m:
        return None
    end = block_end(src, m.end() - 1)
    if end < 0:
        return None
    block = src[m.start():end]
    if "requestScrollToItem(latestGroupIndex)" not in block:
        return None
    src = src[:m.start()] + FOLLOW_BLOCK + src[end:]
    # top padding: start below the skin header band too
    pat = re.compile(r"\.padding\(top = innerPadding\.calculateTopPadding\(\)\)")
    if not pat.search(src):
        return None
    src = pat.sub(".padding(top = innerPadding.calculateTopPadding() + ChatHtmlLayout.reservedTopDp.value.dp)", src)
    # loading row readable over a skin
    pat = re.compile(
        r"Row\(\s*modifier = Modifier\.padding\(8\.dp\),"
        r"(?=\s*verticalAlignment = Alignment\.CenterVertically,\s*"
        r"horizontalArrangement = Arrangement\.spacedBy\(8\.dp\),\s*\)\s*\{\s*RabbitLoadingIndicator)"
    )
    if len(pat.findall(src)) != 1:
        return None
    src = pat.sub("Row(\n                        modifier = Modifier.padding(8.dp).rhReadableOnSkin(),", src)
    return src


# ------------------------------------------------------------- 3. layout rules

LAYOUT_RULES = (
    "LAYOUT RULES (mandatory, read before writing a skin): the native message list scrolls "
    "through the middle of the screen and covers anything placed there, and the native input "
    "bar covers the bottom var(--rh-safe-bottom). Put skin content ONLY in: (1) one header "
    "band at the top of the page - declare its height with <meta name='rh-header-height' "
    "content='N'> (N in px = dp, keep it under 200) and keep every header element inside it; "
    "the native list starts below the band; (2) small fixed widgets (at most 56px wide) on "
    "the left or right edge, between var(--rh-safe-top) and the input bar; (3) purely "
    "decorative backgrounds. Never place buttons, cards or text in normal flow below the "
    "header band. Use content='0' when the skin has no header. "
)


def t_chat_ui_tools(src):
    anchor = "Writes need user approval; explain the design in `reason`."
    if src.count(anchor) != 1:
        return None
    return src.replace(anchor, LAYOUT_RULES + anchor, 1)


def main():
    patch(MESSAGE, "rh-batch2:tps", t_message)
    patch(HANDLER, "rh-batch2:tps", t_handler)
    patch(CHAT_LIST, "rh-batch2:scroll", t_chat_list)
    patch(CHAT_UI_TOOLS, "rh-header-height", t_chat_ui_tools)
    if FAILURES:
        print("batch2 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1
    print("batch2 patches applied", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

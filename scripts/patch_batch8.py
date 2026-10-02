#!/usr/bin/env python3
"""Batch-8: truncate-only compaction + automatic-compaction cooldown.

Two problems were reported together:

1. "压缩上下文的时候，能不能选择不总结直接进行删除消息只保留多少多少条消息？"
   Summarisation is a multi-request map/reduce pass: it can fail, time out, overflow the
   compression model, or (for a provider that misreports context) fan out into dozens of
   requests. The compress dialog now offers a second mode that drops the older messages
   locally with no model request at all.

2. "压缩功能总是用不了，重复请求很多次"
   Automatic compaction is forced after every tool round whose next request is still over
   the threshold (handleMessageComplete's onAfterToolExecution). One long agentic turn can
   therefore start an unbounded series of full map/reduce passes. A per-conversation
   cooldown floors that. The context-limit recovery pass (compactEntireContext) bypasses
   the cooldown on purpose - it is the path that has to work even when an earlier pass did
   not shrink the context enough.

The compress dialog is hosted by ui/components/ai/FilesPicker.kt (it owns
showCompressDialog / onCompressContext). That file takes no view model - it injects its
dependencies with Koin - so the truncate action is wired through koinInject() there.

Anchors are matched with ALL whitespace removed (see match_flat), so reflowing the source
must not break this patch. Anchored, idempotent, loud (::error + exit 1).
"""
import sys
from pathlib import Path

FAILURES = []
CHAT_SERVICE = Path("app/src/main/java/me/rerere/rikkahub/service/ChatService.kt")
CHAT_VM = Path("app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatVM.kt")
DIALOG = Path("app/src/main/java/me/rerere/rikkahub/ui/components/ai/CompressContextDialog.kt")
FILES_PICKER = Path("app/src/main/java/me/rerere/rikkahub/ui/components/ai/FilesPicker.kt")
MARKER = "rh-batch8"


def fail(msg, target=None):
    where = f" file={target}" if target else ""
    print(f"::error{where}::batch8 patch failed: {msg}", flush=True)
    FAILURES.append(msg)


def flatten(text):
    """Return (text_without_whitespace, original_index_of_each_kept_char)."""
    kept = []
    indexes = []
    for index, char in enumerate(text):
        if not char.isspace():
            kept.append(char)
            indexes.append(index)
    return "".join(kept), indexes


def match_flat(src, pattern):
    """Locate `pattern` in `src`, ignoring all whitespace. Returns (start, end) or None."""
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


def load(path, label):
    if not path.exists():
        fail(f"{label}: file not found ({path})", str(path))
        return None
    return path.read_text(encoding="utf-8")


def patch_file(path, label, edits, marker=None):
    src = load(path, label)
    if src is None:
        return
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
# ChatService.kt
# --------------------------------------------------------------------------------------

COOLDOWN_CONST_OLD = "private const val MAX_FULL_CONTEXT_MAP_GROUPS = 8"

COOLDOWN_CONST_NEW = """private const val MAX_FULL_CONTEXT_MAP_GROUPS = 8

/**
 * rh-batch8:auto-compaction-cooldown - minimum gap between two automatic compaction passes of
 * the same conversation. Automatic compaction is forced after every tool round whose next
 * request still exceeds the threshold, so without a floor a single long agentic turn becomes
 * an unbounded series of summarisation requests (what the user sees as "重复请求很多次").
 * Manual compression and the context-limit recovery pass ignore this cooldown.
 */
private const val AUTO_COMPACTION_COOLDOWN_MS = 120_000L"""

COOLDOWN_FIELD_OLD = "private val streamingPersistenceSequence = AtomicLong(0L)"

COOLDOWN_FIELD_NEW = """/**
 * rh-batch8:auto-compaction-cooldown - elapsed-realtime of the last automatic compaction pass
 * per conversation (see AUTO_COMPACTION_COOLDOWN_MS).
 */
private val lastAutoCompactionAt = ConcurrentHashMap<Uuid, Long>()

private val streamingPersistenceSequence = AtomicLong(0L)"""

CLEANUP_OLD = """sessions.values.forEach { it.cleanup() }
        sessions.clear()
        sessionMutexes.clear()"""

CLEANUP_NEW = """sessions.values.forEach { it.cleanup() }
        sessions.clear()
        lastAutoCompactionAt.clear()
        sessionMutexes.clear()"""

REMOVE_SESSION_OLD = """            // Evict the per-conversation mutex so it doesn't accumulate forever.
            // dropSession() already removes it; removeSession() (idle eviction path)
            // was previously missing this cleanup, causing a slow leak on heavy-use
            // sessions where many conversations cycle in and out of memory.
            sessionMutexes.remove(conversationId)"""

REMOVE_SESSION_NEW = """            // Evict the per-conversation mutex so it doesn't accumulate forever.
            // dropSession() already removes it; removeSession() (idle eviction path)
            // was previously missing this cleanup, causing a slow leak on heavy-use
            // sessions where many conversations cycle in and out of memory.
            sessionMutexes.remove(conversationId)
            // rh-batch8:auto-compaction-cooldown - same leak guard for the cooldown map.
            lastAutoCompactionAt.remove(conversationId)"""

DROPSESSION_OLD = """        sessions.remove(conversationId) ?: return
        session.cleanup()
        sessionMutexes.remove(conversationId)"""

DROPSESSION_NEW = """        sessions.remove(conversationId) ?: return
        session.cleanup()
        sessionMutexes.remove(conversationId)
        lastAutoCompactionAt.remove(conversationId)"""

COOLDOWN_GATE_OLD = """        // Automatic compaction is deliberately driven by provider-reported usage after a
        // tool result, or by an actual context-limit error. Do not estimate the history here
        // and compact before the model has had a chance to execute its tools.
        if (!force) return view"""

COOLDOWN_GATE_NEW = """        // Automatic compaction is deliberately driven by provider-reported usage after a
        // tool result, or by an actual context-limit error. Do not estimate the history here
        // and compact before the model has had a chance to execute its tools.
        if (!force) return view

        // rh-batch8:auto-compaction-cooldown - one agentic turn executes many tool rounds, and
        // every round that still reports an over-threshold prompt used to start another full
        // map/reduce pass. The cooldown collapses those into at most one pass per window. A
        // context-limit recovery pass (compactEntireContext) always runs: it is the escape
        // hatch for the case where the previous pass genuinely did not shrink enough.
        if (!compactEntireContext) {
            val lastAt = lastAutoCompactionAt[conversation.id]
            val nowElapsed = SystemClock.elapsedRealtime()
            if (lastAt != null && nowElapsed - lastAt < AUTO_COMPACTION_COOLDOWN_MS) {
                Log.i(
                    TAG,
                    "Auto compaction skipped: last pass ran " +
                        "${nowElapsed - lastAt}ms ago (< ${AUTO_COMPACTION_COOLDOWN_MS}ms)",
                )
                return view
            }
        }"""

COOLDOWN_STAMP_OLD = """            val latestConversation = getConversationFlow(conversation.id).value
            return ContextCompactionView.build(latestConversation, compaction).copy(
                newlyCreatedAutoCompaction = newlyCreatedAutoCompaction,
            )"""

COOLDOWN_STAMP_NEW = """            // rh-batch8:auto-compaction-cooldown - stamp the pass even when it was skipped for
            // lack of new source material, so a long tool loop cannot re-enter immediately.
            lastAutoCompactionAt[conversation.id] = SystemClock.elapsedRealtime()
            val latestConversation = getConversationFlow(conversation.id).value
            return ContextCompactionView.build(latestConversation, compaction).copy(
                newlyCreatedAutoCompaction = newlyCreatedAutoCompaction,
            )"""

TRUNCATE_ANCHOR = """    private suspend fun awaitForegroundWorkReady() {
        // Reassert the service for every model round. This is cheap when it is already running,
        // and recovers when an OEM reclaimed it between a tool result and the next request."""

TRUNCATE_FUNCS = '''    /**
     * rh-batch8:truncate-only - drop every message before the retained tail WITHOUT calling a
     * model. This is the "不总结，只保留最近 N 条" option of the compress dialog: it cannot fail,
     * cannot time out, and costs no tokens, which is what a user wants when the summarisation
     * pass keeps re-requesting the same payload or comes back unusable.
     *
     * The stored compaction (if any) describes messages that no longer exist, so it is cleared
     * in the same critical section, before the truncated snapshot is saved.
     *
     * Returns the number of dropped message nodes. Throws when there is nothing to drop, so the
     * caller never silently "succeeds" without doing anything.
     */
    suspend fun truncateConversationToRecent(
        conversationId: Uuid,
        keepRecentMessages: Int,
    ): Result<Int> {
        val releaseForegroundWork = foregroundWorkTracker.acquire()
        return runCatching {
            awaitForegroundWorkReady()
            ensureHydrated(conversationId)
            compactionMutexFor(conversationId).withLock {
                val conversation = getConversationFlow(conversationId).value
                val keep = keepRecentMessages.coerceAtLeast(1)
                val total = conversation.messageNodes.size
                if (total <= keep) {
                    throw IllegalStateException(
                        context.getString(R.string.chat_page_compress_not_enough_messages)
                    )
                }
                val boundary = total - keep
                val truncated = conversation.copy(
                    messageNodes = conversation.messageNodes.subList(boundary, total).toList()
                )
                conversationRepo.clearCompaction(conversationId)
                saveConversation(conversationId, truncated)
                Log.i(
                    TAG,
                    "rh-batch8:truncate-only dropped $boundary node(s) from $conversationId, " +
                        "kept the last $keep"
                )
                boundary
            }
        }.also {
            releaseForegroundWork()
        }
    }

    /**
     * Keeps the manual truncation off the chat screen's coroutine, mirroring
     * [compressConversationAsync]: deleting a long history rewrites every surviving message node
     * and must not be cancelled by the user navigating away.
     */
    fun truncateConversationToRecentAsync(
        conversationId: Uuid,
        keepRecentMessages: Int,
    ): Job = appScope.launch {
        truncateConversationToRecent(conversationId, keepRecentMessages)
            .onFailure { error ->
                addError(
                    error,
                    conversationId = conversationId,
                    title = "精简对话失败",
                )
            }
    }

''' + TRUNCATE_ANCHOR


# --------------------------------------------------------------------------------------
# ChatVM.kt
# --------------------------------------------------------------------------------------

VM_OLD = """    fun handleCompressContext(additionalPrompt: String, targetTokens: Int, keepRecentMessages: Int): Job {
        return chatService.compressConversationAsync(
            conversationId = _conversationId,
            conversation = conversation.value,
            additionalPrompt = additionalPrompt,
            targetTokens = targetTokens,
            keepRecentMessages = keepRecentMessages,
        )
    }"""

VM_NEW = VM_OLD + """

    /**
     * rh-batch8:truncate-only - delete the older messages instead of summarising them.
     * No compression model is contacted, so this cannot hang or produce repeated requests.
     */
    fun handleTruncateContext(keepRecentMessages: Int): Job {
        return chatService.truncateConversationToRecentAsync(
            conversationId = _conversationId,
            keepRecentMessages = keepRecentMessages,
        )
    }"""


# --------------------------------------------------------------------------------------
# CompressContextDialog.kt
# --------------------------------------------------------------------------------------

DIALOG_IMPORT_OLD = "import androidx.compose.material3.TextButton"

DIALOG_IMPORT_NEW = """import androidx.compose.material3.Switch
import androidx.compose.material3.TextButton"""

DIALOG_SIG_OLD = """fun CompressContextDialog(
    defaultTargetTokens: Int,
    onDismiss: () -> Unit,
    onConfirm: (additionalPrompt: String, targetTokens: Int, keepRecentMessages: Int) -> Job,
    // Conversation being compressed; used to show the compression model's live reply.
    conversationId: Uuid? = null,
)"""

DIALOG_SIG_NEW = """fun CompressContextDialog(
    defaultTargetTokens: Int,
    onDismiss: () -> Unit,
    onConfirm: (additionalPrompt: String, targetTokens: Int, keepRecentMessages: Int) -> Job,
    // Conversation being compressed; used to show the compression model's live reply.
    conversationId: Uuid? = null,
    // rh-batch8:truncate-only - optional "delete instead of summarise" action. Left null the
    // toggle is hidden, so an existing call site keeps compiling unchanged.
    onTruncate: ((keepRecentMessages: Int) -> Job)? = null,
)"""

DIALOG_STATE_OLD = """    var keepRecentMessages by remember { mutableStateOf(32) }
    var currentJob by remember { mutableStateOf<Job?>(null) }"""

DIALOG_STATE_NEW = """    var keepRecentMessages by remember { mutableStateOf(32) }
    // rh-batch8:truncate-only - when on, the confirm button deletes instead of summarising.
    var truncateOnly by remember { mutableStateOf(false) }
    var currentJob by remember { mutableStateOf<Job?>(null) }"""

DIALOG_BODY_OLD = """                } else {
                    Text(stringResource(R.string.chat_page_compress_context_desc))

                    // Token size selector"""

DIALOG_BODY_NEW = """                } else {
                    // rh-batch8:truncate-only - choose between the original model-backed summary
                    // and a purely local "keep only the last N messages" cleanup.
                    if (onTruncate != null) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "只保留最近 N 条（不总结，直接删除旧消息）",
                                style = MaterialTheme.typography.bodyMedium,
                                modifier = Modifier.weight(1f)
                            )
                            Switch(
                                checked = truncateOnly,
                                onCheckedChange = { truncateOnly = it }
                            )
                        }
                    }

                    if (truncateOnly) {
                        OutlinedNumberInput(
                            value = keepRecentMessages,
                            onValueChange = { keepRecentMessages = it },
                            label = "保留最近多少条消息",
                            modifier = Modifier.fillMaxWidth(),
                        )
                        Text(
                            text = "将直接删除更早的消息，不调用任何模型、不产生费用，且无法撤销。",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.error
                        )
                    } else {
                    Text(stringResource(R.string.chat_page_compress_context_desc))

                    // Token size selector"""

DIALOG_TAIL_OLD = """                    // Warning text
                    Text(
                        text = stringResource(R.string.chat_page_compress_warning),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                }
            }
        },"""

DIALOG_TAIL_NEW = """                    // Warning text
                    Text(
                        text = stringResource(R.string.chat_page_compress_warning),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error
                    )
                    }
                }
            }
        },"""

DIALOG_CONFIRM_OLD = "currentJob = onConfirm(additionalPrompt, targetTokens, keepRecentMessages)"

DIALOG_CONFIRM_NEW = """currentJob = if (truncateOnly) {
                        // rh-batch8:truncate-only - no compression model is contacted here.
                        onTruncate?.invoke(keepRecentMessages)
                    } else {
                        onConfirm(additionalPrompt, targetTokens, keepRecentMessages)
                    }"""


# --------------------------------------------------------------------------------------
# FilesPicker.kt - the real host of CompressContextDialog
# --------------------------------------------------------------------------------------

PICKER_IMPORT_OLD = "import me.rerere.rikkahub.data.repository.WorkspaceRepository"

PICKER_IMPORT_NEW = """import me.rerere.rikkahub.data.repository.WorkspaceRepository
import me.rerere.rikkahub.service.ChatService"""

PICKER_INJECT_OLD = "val workspaceRepository: WorkspaceRepository = koinInject()"

PICKER_INJECT_NEW = """val workspaceRepository: WorkspaceRepository = koinInject()
    // rh-batch8:truncate-only - FilesPicker has no view model, so the "delete instead of
    // summarise" action is resolved straight from Koin (same container ChatVM uses).
    val chatService: ChatService = koinInject()"""

PICKER_CALL = "CompressContextDialog("

PICKER_ARG = """{newline}{indent}// rh-batch8:truncate-only - no model request, just drop the older messages.
{indent}onTruncate = {{ keepRecentMessages ->
{indent}    chatService.truncateConversationToRecentAsync(
{indent}        conversationId = conversation.id,
{indent}        keepRecentMessages = keepRecentMessages,
{indent}    )
{indent}}},
"""


def patch_picker_call_site():
    src = load(FILES_PICKER, "FilesPicker")
    if src is None:
        return
    if "onTruncate" in src:
        print(f"already patched: {FILES_PICKER}", flush=True)
        return
    if PICKER_CALL not in src:
        fail(f"{PICKER_CALL} call site not found", str(FILES_PICKER))
        return

    start = src.find(PICKER_CALL)
    depth = 0
    end = -1
    for i in range(start + len(PICKER_CALL) - 1, len(src)):
        char = src[i]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end < 0:
        fail("unbalanced CompressContextDialog( call", str(FILES_PICKER))
        return

    line_start = src.rfind("\n", 0, start) + 1
    indent = src[line_start:start]
    # First argument sits one level deeper than the call keyword.
    arg_indent = indent + " " * 4
    insertion = start + len(PICKER_CALL)
    arg = PICKER_ARG.format(newline="\n", indent=arg_indent)
    src = src[:insertion] + arg + src[insertion:]

    if "onTruncate" not in src:
        fail("onTruncate argument was not inserted", str(FILES_PICKER))
        return
    FILES_PICKER.write_text(src, encoding="utf-8")
    print(f"patched dialog call site: {FILES_PICKER}", flush=True)


def main():
    patch_file(
        CHAT_SERVICE,
        "ChatService",
        [
            (COOLDOWN_CONST_OLD, COOLDOWN_CONST_NEW, "cooldown constant"),
            (COOLDOWN_FIELD_OLD, COOLDOWN_FIELD_NEW, "cooldown field"),
            (CLEANUP_OLD, CLEANUP_NEW, "cleanup()"),
            (REMOVE_SESSION_OLD, REMOVE_SESSION_NEW, "removeSession()"),
            (DROPSESSION_OLD, DROPSESSION_NEW, "dropSession()"),
            (COOLDOWN_GATE_OLD, COOLDOWN_GATE_NEW, "cooldown gate"),
            (COOLDOWN_STAMP_OLD, COOLDOWN_STAMP_NEW, "cooldown stamp"),
            (TRUNCATE_ANCHOR, TRUNCATE_FUNCS, "truncate-only functions"),
        ],
        marker=MARKER,
    )

    patch_file(
        CHAT_VM,
        "ChatVM",
        [(VM_OLD, VM_NEW, "handleTruncateContext")],
        marker="handleTruncateContext",
    )

    patch_file(
        DIALOG,
        "CompressContextDialog",
        [
            (DIALOG_IMPORT_OLD, DIALOG_IMPORT_NEW, "Switch import"),
            (DIALOG_SIG_OLD, DIALOG_SIG_NEW, "signature"),
            (DIALOG_STATE_OLD, DIALOG_STATE_NEW, "state"),
            (DIALOG_BODY_OLD, DIALOG_BODY_NEW, "body head"),
            (DIALOG_TAIL_OLD, DIALOG_TAIL_NEW, "body tail"),
            (DIALOG_CONFIRM_OLD, DIALOG_CONFIRM_NEW, "confirm button"),
        ],
        marker="truncateOnly",
    )

    patch_file(
        FILES_PICKER,
        "FilesPicker",
        [
            (PICKER_IMPORT_OLD, PICKER_IMPORT_NEW, "ChatService import"),
            (PICKER_INJECT_OLD, PICKER_INJECT_NEW, "ChatService injection"),
        ],
        marker="chatService",
    )

    patch_picker_call_site()

    if FAILURES:
        print("batch8 patch failures:\n  " + "\n  ".join(FAILURES), flush=True)
        return 1
    print("batch8 patches applied", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

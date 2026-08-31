package me.rerere.rikkahub.browser

import android.graphics.Bitmap
import android.graphics.Canvas
import android.webkit.WebView
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import java.io.File
import java.io.FileOutputStream
import java.lang.ref.WeakReference

/**
 * Kind of AI-driven browser action recorded in the trail. Each value has a paired
 * localized template (`browser_ai_action_<kind lowercase>`) that `BrowserAiStripe`
 * resolves at render time from [BrowserAiAction.kind] + [BrowserAiAction.detail] — the
 * human-readable sentence is built only in the UI layer so it localizes, and (for
 * [BrowserAiActionOutcome.FAILED] entries) can be wrapped in the `browser_ai_action_failed`
 * prefix template.
 */
enum class BrowserAiActionKind {
    OPEN, CLICK, TYPE, SCROLL, SUBMIT, SELECT, KEY, JS, SCREENSHOT, READ, BACK, FORWARD, DONE, STOPPED
}

/** Lifecycle state of a [BrowserAiAction]. */
enum class BrowserAiActionOutcome { RUNNING, OK, FAILED }

/**
 * One entry in the AI action trail (newest first in [BrowserController.recentActionsFlow]).
 * [detail] carries only what's safe to render verbatim — a URL or CSS selector, never typed
 * text or select values (see the call sites in `BrowserTools.kt` for the per-kind rule); the
 * localized sentence is composed at render time from [kind] + [detail].
 */
data class BrowserAiAction(
    val id: Long,
    val kind: BrowserAiActionKind,
    val detail: String?,
    val outcome: BrowserAiActionOutcome,
    val atMs: Long,
    val step: Int,
)

/**
 * Singleton bridge between the LLM browser tools and the visible BrowserActivity WebView.
 * It owns the foreground binding, the recent action trail, the task timeout and the
 * main-thread dispatch bridge used by browser tools.
 */
object BrowserController {

    private const val MAX_RECENT_ACTIONS = 20

    /**
     * Hard cap on a single AI-driven task to bound runaway loops. User-configurable via
     * Settings → Browser (GitHub issue #4) — [BrowserPreferences] writes the persisted value
     * here at app start and on every edit. Defaults to 5 min until the first read settles.
     * Always holds a value clamped into [BrowserToolDefaults]'s supported range.
     */
    @Volatile
    var singleTaskTimeoutMs: Long = BrowserToolDefaults.DEFAULT_SINGLE_TASK_TIMEOUT_MS

    /**
     * Per-tool timeout — the `withTimeoutOrNull` budget every browser tool wraps its dispatch
     * in. User-configurable via Settings → Browser (GitHub issue #4); kept in sync by
     * [BrowserPreferences]. Defaults to 30 s until the first read settles. Always clamped.
     */
    @Volatile
    var perToolTimeoutMs: Long = BrowserToolDefaults.DEFAULT_PER_TOOL_TIMEOUT_MS
    private const val TAG = "BrowserController"

    /**
     * Execution mode for the controller. Exactly one is active at a time; the [Mode.Idle]
     * case lets `isBound()` return false uniformly without a null check.
     */
    sealed class Mode {
        data object Idle : Mode()

        /** A visible [BrowserActivity] hosts the WebView. */
        data class Foreground(val activityRef: WeakReference<WebView>) : Mode()

    }

    @Volatile
    private var mode: Mode = Mode.Idle

    /** Serializes bind/unbind state changes so a late Activity callback cannot clear a newer view. */
    private val bindLock = Any()

    /**
     * Pass 2 publishes a fresh deferred each time the binding is cleared, so a tool that
     * fires `browser_open` can `awaitBind` after starting the Activity. The Volatile lets
     * the awaiting coroutine see the new instance the moment unbind() swaps it in.
     */
    @Volatile
    private var bindDeferred: CompletableDeferred<Unit> = CompletableDeferred()

    /** Set on the first browser_open of a task. null = no task in flight. */
    @Volatile
    var currentTaskStartedAt: Long? = null

    /**
     * Pass 2: the in-flight tool dispatch coroutine, stored so the user-facing "Stop AI"
     * UI button can cancel a run mid-action (the visible Activity calls [stopCurrentTask]
     * which cancels this Job). Tool factories register their dispatch into here on entry
     * and clear on completion.
     */
    @Volatile
    var pendingTaskJob: Job? = null

    private val _recentActions = MutableStateFlow<List<BrowserAiAction>>(emptyList())

    /** Compose-friendly observable of the last [MAX_RECENT_ACTIONS] AI actions, newest first. */
    fun recentActionsFlow(): StateFlow<List<BrowserAiAction>> = _recentActions.asStateFlow()

    /**
     * True while an AI-driven task is in flight (from [startTaskWindow] to [clearTaskWindow]
     * / [stopCurrentTask]). UI-only signal for [BrowserAiStripe]'s spinner + Stop button —
     * [currentTaskStartedAt] stays the authoritative source for the timeout check itself.
     */
    private val _taskActive = MutableStateFlow(false)
    fun taskActiveFlow(): StateFlow<Boolean> = _taskActive.asStateFlow()

    /** Guards [nextActionId] / [nextActionStep] and the read-modify-write of [_recentActions]. */
    private val actionLock = Any()
    private var nextActionId = 0L
    private var nextActionStep = 0

    /**
     * Append a RUNNING [BrowserAiAction] to the trail and return its id. Pair with
     * [completeAction] — ideally in a `try/finally` — so a thrown exception or a
     * `withTimeoutOrNull` cancellation can't leave the entry RUNNING forever.
     */
    fun beginAction(kind: BrowserAiActionKind, detail: String? = null): Long {
        val trimmedDetail = detail?.trim()?.takeIf { it.isNotEmpty() }
        synchronized(actionLock) {
            val id = ++nextActionId
            val step = ++nextActionStep
            val action = BrowserAiAction(
                id = id,
                kind = kind,
                detail = trimmedDetail,
                outcome = BrowserAiActionOutcome.RUNNING,
                atMs = System.currentTimeMillis(),
                step = step,
            )
            _recentActions.value = (listOf(action) + _recentActions.value).take(MAX_RECENT_ACTIONS)
            return id
        }
    }

    /** Flip the [id] entry to OK/FAILED. A no-op if [id] isn't in the current trail (e.g. it aged out). */
    fun completeAction(id: Long, ok: Boolean) {
        synchronized(actionLock) {
            val current = _recentActions.value
            val idx = current.indexOfFirst { it.id == id }
            if (idx < 0) return
            val outcome = if (ok) BrowserAiActionOutcome.OK else BrowserAiActionOutcome.FAILED
            _recentActions.value = current.toMutableList().also { it[idx] = it[idx].copy(outcome = outcome) }
        }
    }

    /** One-shot convenience for actions that don't have a meaningful RUNNING phase (DONE, STOPPED). */
    fun recordAction(kind: BrowserAiActionKind, detail: String? = null, ok: Boolean = true) {
        completeAction(beginAction(kind, detail), ok)
    }

    /** Clears the action trail and resets the per-task step counter (NOT the monotonic id counter). */
    private fun resetActionTrail() {
        synchronized(actionLock) {
            _recentActions.value = emptyList()
            nextActionStep = 0
        }
    }

    /** Returns the current execution mode. */
    fun currentMode(): Mode = mode

    // --- Foreground bindings ----------------------------------------------------------

    /** Activity calls this in onCreate to publish the visible WebView. */
    fun bindForeground(webView: WebView) {
        synchronized(bindLock) {
            mode = Mode.Foreground(WeakReference(webView))
        }
        if (!bindDeferred.isCompleted) {
            bindDeferred.complete(Unit)
        }
        // Trim stale browser screenshots from an earlier foreground session.
        runCatching { BrowserCacheSweeper.sweep(webView.context.applicationContext) }
    }

    /**
     * Activity calls this in onDestroy. Only clears if [mode] is still [Mode.Foreground] AND
     * the live ref still points at the same WebView (or has already been GC'd).
     *
     * **Bug fix.** The previous check was `(mode as? Mode.Foreground)?.activityRef?.get()`
     * then `current === webView || current == null`. That collapses two very different
     * cases into the same `current == null` branch: a genuinely GC'd Foreground ref, AND
     * `mode` not being [Mode.Foreground] at all (e.g. an already-[Mode.Idle] controller). A
     * stray or late `onDestroy` call after recreation must not reset an unrelated binding.
     * Guard
     * on `mode is Mode.Foreground` explicitly so this can only ever clear a foreground
     * binding it actually owns (or one that's already gone).
     */
    fun unbindForeground(webView: WebView) {
        synchronized(bindLock) {
            val m = mode
            if (m !is Mode.Foreground) return
            val current = m.activityRef.get()
            if (current === webView || current == null) {
                mode = Mode.Idle
                // Reset task timer and action log when the visible Activity is torn down.
                currentTaskStartedAt = null
                _taskActive.value = false
                resetActionTrail()
                // Swap in a fresh deferred so the NEXT browser_open's awaitBind blocks correctly
                // until the next bind() — without this, a stale "completed" deferred from the
                // prior session would let awaitBind return immediately on a dead WebView.
                bindDeferred = CompletableDeferred()
            }
        }
    }

    /** Pass 1/2 API surface — kept as a thin wrapper over [bindForeground] so call sites compile. */
    fun bind(webView: WebView) = bindForeground(webView)

    /** Pass 1/2 API surface — kept as a thin wrapper over [unbindForeground]. */
    fun unbind(webView: WebView) = unbindForeground(webView)

    // --- Status reads -----------------------------------------------------------------

    /** True iff a live foreground WebView is currently bound. */
    fun isBound(): Boolean = activeWebView() != null

    /** Cheap read for tools / UI status — null when no WebView is bound. */
    fun currentUrl(): String? = activeWebView()?.url

    /** Cheap read for tools / UI status — null when no WebView is bound. */
    fun currentTitle(): String? = activeWebView()?.title

    /**
     * Cancel the in-flight tool dispatch (if any) and clear the single-task timer. Wired
     * to the Activity's "Stop AI" kebab item; the cancelled coroutine surfaces as a normal
     * CancellationException inside the tool's withTimeoutOrNull and the LLM gets a clean
     * envelope instead of a stack trace.
     */
    fun stopCurrentTask() {
        pendingTaskJob?.cancel()
        pendingTaskJob = null
        currentTaskStartedAt = null
        _taskActive.value = false
        recordAction(BrowserAiActionKind.STOPPED)
    }

    /**
     * Start (or refresh) the single-task window. browser_open calls this on every successful
     * navigation; once a task starts, every browser_* call after the window expires gets
     * [taskTimeoutEnvelope] until browser_done fires (which clears the timer). The window
     * length is [singleTaskTimeoutMs] — user-configurable in Settings → Browser.
     *
     * **Task scoping.** Only a genuinely NEW task (no window currently in flight) clears the
     * action trail + step counter — a mid-task re-arm (e.g. the model calling browser_open
     * again to navigate elsewhere in the same task) must not wipe the trail the user is
     * watching.
     */
    fun startTaskWindow() {
        if (currentTaskStartedAt == null) {
            resetActionTrail()
        }
        currentTaskStartedAt = System.currentTimeMillis()
        _taskActive.value = true
    }

    /** browser_done clears the task window (and stops the in-flight job log). The action trail is left intact — the DONE entry [recordAction] adds stays visible as the stripe's headline. */
    fun clearTaskWindow() {
        currentTaskStartedAt = null
        _taskActive.value = false
    }

    /**
     * Returns true if no task is in flight OR the in-flight task hasn't yet exhausted its
     * configured single-task budget ([singleTaskTimeoutMs]). Tools call this BEFORE doing any
     * work so a runaway loop costs at most one envelope per call after the cap.
     */
    fun isWithinTaskWindow(): Boolean {
        val started = currentTaskStartedAt ?: return true
        return System.currentTimeMillis() - started < singleTaskTimeoutMs
    }

    /**
     * Suspend until a bind happens or [timeoutMs] elapses. browser_open uses this after
     * firing the BrowserActivity launch intent — the Activity's onCreate publishes its
     * WebView, the deferred completes, and the tool can then call loadUrl. 5 s is the
     * spec-mandated cap; on a slow device the user's click on Settings → Open Browser
     * also takes about that long.
     */
    suspend fun awaitBind(timeoutMs: Long = 5_000L): Boolean {
        if (isBound()) return true
        return withTimeoutOrNull(timeoutMs) { bindDeferred.await(); true } ?: false
    }

    /**
     * Internal accessor used by [BrowserControllerHandle]. Returns the live WebView or null
     * when no foreground Activity is bound.
     */
    internal fun activeWebView(): WebView? = when (val m = mode) {
        is Mode.Foreground -> m.activityRef.get()
        Mode.Idle -> null
    }

    fun notOpenEnvelope(): JsonObject = buildJsonObject {
        put("error", "browser_not_open")
        put("recovery", "Call browser_open with a URL to launch the browser before invoking this tool.")
    }

    /** Returned when the 5-min single-task window has elapsed without a browser_done call. */
    fun taskTimeoutEnvelope(): JsonObject = buildJsonObject {
        put("error", "browser_task_timeout")
        put("recovery", "Call browser_done with a summary; the per-task 5-minute cap has been reached.")
    }


}

/**
 * Handle / dispatch helper for the visible browser tools. Tools wrap their entire execute body
 * in [withController], get the WebView if
 * one is bound, and uniformly fall back to the [BrowserController.notOpenEnvelope] error
 * shape if not.
 *
 * Pass 2 also exposes [WithControllerScope] so the per-tool helpers in BrowserTools can
 * round-trip JS via `webView.evaluateJavascript` on the main thread without each tool
 * re-implementing the bridge.
 */
object BrowserControllerHandle {

    /**
     * Scope passed into [withController]'s block. Carries the controller (for
     * beginAction/completeAction / startTaskWindow) and the live WebView. Helpers that need the main
     * thread should use [me.rerere.rikkahub.browser.evaluateJavascriptAsync] which posts
     * onto the WebView's looper directly.
     */
    data class WithControllerScope(
        val controller: BrowserController,
        val webView: WebView,
    )

    /**
     * Runs [block] with a [WithControllerScope] if a WebView is bound; otherwise returns
     * the standard browser_not_open envelope. The 5-minute single-task cap is enforced up
     * front — browser_open re-arms it via [BrowserController.startTaskWindow] and
     * browser_done clears it via [BrowserController.clearTaskWindow] (both routed through
     * tool factories, so they remain reachable inside the cap).
     *
     * The block runs on [Dispatchers.Main]. WebView APIs are main-thread-only and will
     * throw `WebViewMethodCalledOnWrongThreadViolation` from any other dispatcher, so
     * baking the bridge in here means every tool author gets safe direct access to
     * `webView.url`, `webView.title`, `webView.canGoBack()`, etc. without re-wrapping.
     * For network or heavy CPU work that must run off-main, suspend out of [block] via
     * `withContext(Dispatchers.IO)` explicitly. The async JS helpers
     * ([evaluateJavascriptAsync], [awaitReadyState]) post via the WebView's looper and
     * suspend on a `CompletableDeferred`, so they stay non-blocking even from main.
     */
    suspend fun withController(
        block: suspend WithControllerScope.() -> JsonObject,
    ): JsonObject {
        val wv = BrowserController.activeWebView() ?: return BrowserController.notOpenEnvelope()
        if (!BrowserController.isWithinTaskWindow()) {
            return BrowserController.taskTimeoutEnvelope()
        }
        return withContext(Dispatchers.Main) {
            WithControllerScope(BrowserController, wv).block()
        }
    }
}

/**
 * Run [code] on the WebView's required main thread and return the JSON-encoded result
 * string the page produced (or "null" on any error / timeout). `evaluateJavascript`
 * itself is documented as main-thread only and routes its result callback onto the UI
 * thread; the [withContext] gets us there and the [CompletableDeferred] bridges the
 * callback back into a coroutine.
 *
 * **Why no `webView.post { ... }` wrapper.** The earlier version posted into the
 * WebView's run-queue.
 * parent LinearLayout never reaches a Window), `View.post` queues the runnable until
 * attach — which never happens, so `evaluateJavascript` was never called and the
 * deferred timed out at 8 s on every call. Calling `evaluateJavascript` directly from
 * the main-thread context fixes both attached and unattached cases.
 *
 * The result is the raw string evaluateJavascript returns: a valid JSON value (number,
 * "string", true, null, [...], {...}). Callers parse it themselves, since JSON shape
 * varies per tool.
 */
suspend fun WebView.evaluateJavascriptAsync(code: String, timeoutMs: Long = 8_000L): String? {
    val deferred = CompletableDeferred<String?>()
    withContext(Dispatchers.Main) {
        try {
            evaluateJavascript(code) { result -> deferred.complete(result) }
        } catch (e: Exception) {
            // evaluateJavascript can throw if the WebView has been destroyed underneath
            // us (for example, because the Activity finished). Log so the cause is
            // visible — the caller still gets a clean null and falls back. Narrowed from
            // Throwable so JVM Errors (OOM etc.) still propagate.
            android.util.Log.w("BrowserController", "evaluateJavascriptAsync: evaluateJavascript threw", e)
            deferred.complete(null)
        }
    }
    return withTimeoutOrNull(timeoutMs) { deferred.await() }
}

/**
 * Wait for `document.readyState === "complete"` for up to [timeoutMs] ms. Used after
 * state-changing tools (click, type, submit) so the next read tool sees the post-action
 * page rather than a half-rendered intermediate state. Polls every 200 ms, exits early
 * on first complete reading.
 */
suspend fun WebView.awaitReadyState(timeoutMs: Long = 8_000L): Boolean {
    val deadline = System.currentTimeMillis() + timeoutMs
    while (System.currentTimeMillis() < deadline) {
        val raw = evaluateJavascriptAsync("(function(){return document.readyState;})()", 1_500L)
        // evaluateJavascript wraps string returns in JSON quotes — `"complete"` comes
        // back as the 10-char literal `"\"complete\""`. Match the exact form so a page
        // that overrides document.readyState to a string merely containing "complete"
        // (e.g. "incomplete", or some adversarial value) doesn't trip the early-exit.
        if (raw != null && raw.trim() == "\"complete\"") return true
        kotlinx.coroutines.delay(200)
    }
    return false
}

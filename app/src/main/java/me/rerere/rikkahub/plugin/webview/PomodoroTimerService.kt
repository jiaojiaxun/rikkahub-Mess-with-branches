/*
 * OrangeChat plugin timer adapter.
 *
 * This is intentionally an in-app timer rather than an Android Service: the slim build
 * does not restore generic background scheduling, overlay permission, or plugin notification
 * components. The normal set_timer tool remains the route for a timer that must survive the
 * app process; this adapter is for the foreground WebView countdown UI only.
 */
package me.rerere.rikkahub.plugin.webview

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log

private const val TAG = "PomodoroTimer"

object PomodoroTimerService {
    const val ACTION_START = "me.rerere.rikkahub.action.POMODORO_START"
    const val ACTION_STOP = "me.rerere.rikkahub.action.POMODORO_STOP"
    const val EXTRA_SECONDS = "seconds"
    const val ACTION_TIMER_END = "me.rerere.rikkahub.TIMER_END"

    private val lock = Any()
    private val handler = Handler(Looper.getMainLooper())
    private var endTimestampMs: Long = 0L
    private var running: Boolean = false
    private var tick: Runnable? = null

    fun getRemainingSeconds(): Int = synchronized(lock) {
        if (!running) return@synchronized 0
        val remaining = ((endTimestampMs - System.currentTimeMillis() + 999L) / 1000L)
            .coerceAtLeast(0L)
            .coerceAtMost(Int.MAX_VALUE.toLong())
            .toInt()
        if (remaining == 0) {
            running = false
            tick = null
        }
        remaining
    }

    fun isRunning(): Boolean = synchronized(lock) {
        running && endTimestampMs > System.currentTimeMillis()
    }

    fun start(@Suppress("UNUSED_PARAMETER") context: Context, seconds: Int) {
        require(seconds > 0) { "seconds must be positive" }
        synchronized(lock) {
            tick?.let(handler::removeCallbacks)
            endTimestampMs = System.currentTimeMillis() + seconds * 1000L
            running = true
            val next = object : Runnable {
                override fun run() {
                    val shouldContinue = synchronized(lock) {
                        val remaining = getRemainingSeconds()
                        if (remaining <= 0) {
                            running = false
                            tick = null
                            false
                        } else true
                    }
                    if (shouldContinue) handler.postDelayed(this, 1000L)
                    else Log.i(TAG, "in-app countdown ended")
                }
            }
            tick = next
            handler.post(next)
        }
    }

    fun stop(@Suppress("UNUSED_PARAMETER") context: Context) {
        synchronized(lock) {
            tick?.let(handler::removeCallbacks)
            tick = null
            running = false
            endTimestampMs = 0L
        }
    }
}

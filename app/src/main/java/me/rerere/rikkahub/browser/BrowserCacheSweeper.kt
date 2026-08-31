package me.rerere.rikkahub.browser

import android.content.Context
import android.util.Log
import java.io.File

/**
 * Best-effort cleanup of the browser screenshot cache directories. Each browser screenshot
 * writes a 1080x1920 ARGB_8888 file ≈ 7.9 MB. Repeated browser actions can otherwise produce
 * hundreds of megabytes of orphaned PNGs in app cache that
 * would otherwise sit there until the OS clears it (which on modern Android is "rarely,
 * if ever, on its own").
 *
 * The cleanup runs on every browser bind so leftovers from a force-stop or process-kill
 * are gone before the new session starts writing.
 *
 * Strategy: keep the most-recent [keepLast] files per subdirectory, sorted by
 * `lastModified()` descending. Failures are swallowed with a single warn-log; missing
 * directories or unreadable files never bubble up to the caller.
 */
internal object BrowserCacheSweeper {

    private const val TAG = "BrowserCacheSweeper"
    private val CACHE_SUBDIRS = listOf("browser-stream", "browser-shots")

    /**
     * Trim the browser-related cache subdirs to [keepLast] entries each (newest first).
     * Idempotent. Safe to call repeatedly. Errors logged at WARN, never thrown.
     */
    fun sweep(context: Context, keepLast: Int = 20) {
        val cacheDir = context.cacheDir ?: return
        sweep(cacheDir, keepLast)
    }

    /**
     * File-based overload. Used by [sweep] (production) and unit tests (which can pass a
     * temp dir directly without mocking a Context).
     *
     * Returns the number of files deleted across both subdirs — useful for tests and for
     * potential future logging at the call site (where Android's Log facility is
     * available without the JVM-unit-test mock-required overhead).
     */
    internal fun sweep(cacheDir: File, keepLast: Int = 20): Int {
        var totalDeleted = 0
        for (sub in CACHE_SUBDIRS) {
            runCatching {
                val dir = File(cacheDir, sub)
                if (!dir.exists() || !dir.isDirectory) return@runCatching
                val files = dir.listFiles()?.filter { it.isFile }?.sortedByDescending { it.lastModified() }
                    ?: return@runCatching
                if (files.size <= keepLast) return@runCatching
                val excess = files.drop(keepLast)
                for (f in excess) {
                    if (runCatching { f.delete() }.getOrDefault(false)) totalDeleted++
                }
            }.onFailure {
                Log.w(TAG, "sweep failed for $sub", it)
            }
        }
        return totalDeleted
    }
}

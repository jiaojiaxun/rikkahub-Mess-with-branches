/*
 * OrangeChat music bridge.
 * Reuses the app's existing MediaPlaybackService instead of shipping a second player service.
 */
package me.rerere.rikkahub.plugin.webview

import android.content.Context
import android.content.Intent
import android.os.Build
import me.rerere.rikkahub.service.MediaPlaybackService

object MusicPlayerService {
    fun play(context: Context, filePath: String, title: String, artist: String) {
        start(context, MediaPlaybackService.buildPlayIntent(context, filePath, title, artist))
    }

    fun pause(context: Context) {
        start(context, Intent(context, MediaPlaybackService::class.java).setAction(MediaPlaybackService.ACTION_PAUSE))
    }

    fun resume(context: Context) {
        start(context, Intent(context, MediaPlaybackService::class.java).setAction(MediaPlaybackService.ACTION_PLAY))
    }

    fun stop(context: Context) {
        start(context, Intent(context, MediaPlaybackService::class.java).setAction(MediaPlaybackService.ACTION_STOP))
    }

    fun seekTo(context: Context, positionMs: Int) {
        start(context, Intent(context, MediaPlaybackService::class.java).apply {
            action = MediaPlaybackService.ACTION_SEEK
            putExtra(MediaPlaybackService.EXTRA_POSITION_MS, positionMs.toLong().coerceAtLeast(0L))
        })
    }

    fun getCurrentPosition(): Int =
        MediaPlaybackService.instance?.positionMs
            ?.coerceIn(0L, Int.MAX_VALUE.toLong())
            ?.toInt() ?: 0

    fun getDuration(): Int =
        MediaPlaybackService.instance?.durationMs
            ?.coerceIn(0L, Int.MAX_VALUE.toLong())
            ?.toInt() ?: 0

    fun getNowPlaying(): Map<String, String> {
        val service = MediaPlaybackService.instance ?: return mapOf("state" to "stopped")
        return mapOf(
            "state" to if (service.isPlaying) "playing" else "paused",
            "title" to (service.currentTitle ?: ""),
            "artist" to (service.currentArtist ?: ""),
        )
    }

    private fun start(context: Context, intent: Intent) {
        val appContext = context.applicationContext
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            appContext.startForegroundService(intent)
        } else {
            @Suppress("DEPRECATION")
            appContext.startService(intent)
        }
    }
}

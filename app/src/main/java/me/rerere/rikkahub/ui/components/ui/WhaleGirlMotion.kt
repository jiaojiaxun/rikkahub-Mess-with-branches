package me.rerere.rikkahub.ui.components.ui

import androidx.annotation.DrawableRes
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.luminance

/**
 * 鲸鱼剪辑定义（移植自 Ayuilos/Miffan WhaleGirlMotion.kt，包名适配）。
 * frameCount 是图集遗留字段——纯 Compose 渲染不按帧切图，仅 durationMillis/looping 生效。
 */
enum class WhaleGirlClip(
    val frameCount: Int,
    val durationMillis: Long,
    val framesPerSecond: Int,
    val looping: Boolean,
) {
    IDLE(120, 4_000, 30, true),
    FOCUSED(120, 4_000, 30, true),
    TYPING(120, 4_000, 30, true),
    SUBMITTED(45, 1_500, 30, false),
    PETTING(45, 1_500, 30, false),
    SUCCESS(45, 1_500, 30, false),
    SURPRISE(45, 1_500, 30, false),
    EATING(120, 4_000, 30, true),
    CHEWING(120, 4_000, 30, true),
    THINKING(120, 4_000, 30, true),
    SLEEPING(120, 4_000, 30, true);
}

/** 播放时钟只累计前台活跃时间；resume 会提供新的时钟原点。 */
internal class WhaleGirlTimeline(
    val clip: WhaleGirlClip,
) {
    val durationNanos = clip.durationMillis * 1_000_000L
    var elapsedNanos: Long = 0L
        private set
    val finished: Boolean get() = !clip.looping && elapsedNanos >= durationNanos
    val frameIndex: Int
        get() = if (finished) clip.frameCount - 1
        else ((elapsedNanos * clip.frameCount) / durationNanos).toInt().coerceIn(0, clip.frameCount - 1)

    fun advance(deltaNanos: Long) {
        if (deltaNanos <= 0L || finished) return
        elapsedNanos = if (clip.looping) {
            (elapsedNanos + deltaNanos % durationNanos) % durationNanos
        } else {
            elapsedNanos + deltaNanos.coerceAtMost(durationNanos - elapsedNanos)
        }
    }
}

/** 兼容入口：头像/介绍/设置预览共用。海报参数仅保持源码兼容，渲染不解码。 */
@Suppress("UNUSED_PARAMETER")
@Composable
fun WhaleGirlAnimatedPortrait(
    clip: WhaleGirlClip,
    playing: Boolean,
    @DrawableRes posterResourceId: Int,
    modifier: Modifier = Modifier,
    reducedMotion: Boolean = false,
    replayId: Int = 0,
    onPlaybackFinished: (() -> Unit)? = null,
    onPlaybackUnavailable: (() -> Unit)? = null,
    attentionTarget: androidx.compose.ui.geometry.Offset? = null,
) {
    WhaleGirlLineArtPortrait(
        clip = clip,
        modifier = modifier.aspectRatio(1f),
        dark = MaterialTheme.colorScheme.background.luminance() < .5f,
        playing = playing,
        reducedMotion = reducedMotion,
        replayId = replayId,
        onPlaybackFinished = onPlaybackFinished,
        attentionTarget = attentionTarget,
    )
}

package me.rerere.rikkahub.ui.components.ui

import androidx.compose.material3.ContainedLoadingIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import me.rerere.rikkahub.ui.context.LocalSettings

/**
 * 加载指示器（fork 适配版）。
 *
 * 原版用 AnimatedVectorDrawable 兔子（R.drawable.rabbit）。
 * fork 改为蓝色大肥鱼吉祥物的 Thinking 状态——纯 Compose 矢量绘制，
 * 不需要 AVD 资源，视觉上和鲸鱼主题统一。
 *
 * useAppIconStyleLoadingIndicator=false 时仍用标准 Material3 indicator。
 */
@Composable
fun RabbitLoadingIndicator(modifier: Modifier = Modifier) {
    val useAppIconStyleLoadingIndicator = LocalSettings.current.displaySetting.useAppIconStyleLoadingIndicator

    if (useAppIconStyleLoadingIndicator) {
        WhaleGirlMascot(
            state = MiffanMascotState.Thinking,
            modifier = modifier,
        )
    } else {
        ContainedLoadingIndicator(
            modifier = modifier,
        )
    }
}

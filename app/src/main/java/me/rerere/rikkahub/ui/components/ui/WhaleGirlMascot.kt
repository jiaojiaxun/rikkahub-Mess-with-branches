package me.rerere.rikkahub.ui.components.ui

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

/** 吉祥物渲染入口。 */
@Composable
internal fun WhaleGirlMascot(
    modifier: Modifier = Modifier,
    state: MiffanMascotState = MiffanMascotState.Idle,
    inputState: MiffanMascotInputState = MiffanMascotInputState.Inactive,
) {
    // 待实现：关联 MascotMotion + GazeTarget
}

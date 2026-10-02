package me.rerere.rikkahub.ui.components.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import me.rerere.ai.core.MessageRole
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart
import me.rerere.rikkahub.BuildConfig
import java.time.Duration
import java.time.LocalTime
import java.time.ZonedDateTime

/**
 * 鲸鱼吉祥物共享枚举与辅助（移植自 Ayuilos/Miffan 多个小文件，合并到一个文件）。
 * fork 适配：assistantGenerationPhase 删掉了 UIMessagePart.ServerTool 分支
 *（fork 2.4.14 的 UIMessagePart 无该子类）。
 */

enum class MiffanMascotState {
    Idle,
    Thinking,
    Happy,
    Error,
    UpdateAvailable,
}

enum class MiffanMascotInputState {
    Inactive,
    Focused,
    Typing,
}

enum class MiffanPresentation { Scene, Avatar }

enum class MiffanDayPhase {
    Morning,
    Noon,
    Night,
}

enum class AssistantGenerationPhase { None, Waiting, Reasoning, Responding }

/** Provider-independent generation meaning（fork 适配：删 ServerTool 分支）。 */
internal fun assistantGenerationPhase(message: UIMessage?, loading: Boolean): AssistantGenerationPhase {
    if (!loading) return AssistantGenerationPhase.None
    if (message?.role != MessageRole.ASSISTANT) return AssistantGenerationPhase.Waiting
    for (part in message.parts.asReversed()) {
        when (part) {
            is UIMessagePart.Text -> if (part.text.isNotBlank()) return AssistantGenerationPhase.Responding
            is UIMessagePart.Reasoning -> return if (part.finishedAt == null) {
                AssistantGenerationPhase.Reasoning
            } else AssistantGenerationPhase.Waiting
            is UIMessagePart.Tool -> return AssistantGenerationPhase.Waiting
            is UIMessagePart.Image, is UIMessagePart.Audio, is UIMessagePart.Video ->
                return AssistantGenerationPhase.Responding
            else -> Unit
        }
    }
    return AssistantGenerationPhase.Waiting
}

object MiffanDayPhaseDebugOverride {
    private val mutablePhase = MutableStateFlow<MiffanDayPhase?>(null)
    val phase = mutablePhase.asStateFlow()

    fun set(value: MiffanDayPhase?) {
        mutablePhase.value = value
    }
}

@Composable
fun rememberMiffanDayPhase(): MiffanDayPhase {
    val actualPhase by produceState(initialValue = miffanDayPhaseAt(LocalTime.now())) {
        while (true) {
            val now = ZonedDateTime.now()
            value = miffanDayPhaseAt(now.toLocalTime())
            delay(millisUntilNextPhase(now))
        }
    }
    val debugOverride by MiffanDayPhaseDebugOverride.phase.collectAsState()
    return if (BuildConfig.DEBUG) debugOverride ?: actualPhase else actualPhase
}

internal fun miffanDayPhaseAt(time: LocalTime): MiffanDayPhase = when (time.hour) {
    in 5..10 -> MiffanDayPhase.Morning
    in 11..17 -> MiffanDayPhase.Noon
    else -> MiffanDayPhase.Night
}

private fun millisUntilNextPhase(now: ZonedDateTime): Long {
    val next = when (miffanDayPhaseAt(now.toLocalTime())) {
        MiffanDayPhase.Morning -> now.withHour(11).withMinute(0).withSecond(0).withNano(0)
        MiffanDayPhase.Noon -> now.withHour(18).withMinute(0).withSecond(0).withNano(0)
        MiffanDayPhase.Night -> {
            if (now.hour < 5) {
                now.withHour(5).withMinute(0).withSecond(0).withNano(0)
            } else {
                now.plusDays(1).withHour(5).withMinute(0).withSecond(0).withNano(0)
            }
        }
    }
    return Duration.between(now, next).toMillis().coerceAtLeast(1_000L)
}

/** 系统减弱动画开关（读 ANIMATOR_DURATION_SCALE==0）。 */
@Composable
internal fun rememberMiffanReducedMotion(): Boolean {
    val context = LocalContext.current
    return remember {
        android.provider.Settings.Global.getFloat(
            context.contentResolver,
            android.provider.Settings.Global.ANIMATOR_DURATION_SCALE, 1f,
        ) == 0f
    }
}

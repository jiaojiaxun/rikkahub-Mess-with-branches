package me.rerere.rikkahub.ui.components.richtext

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import kotlinx.coroutines.delay

// rhSmoothStream285: 流式渲染平滑层(打字机+淡入)。
// ChatMessage 层用 RhTypewriterState 把"每 80ms 一帧的变速增量"整流成
// 恒定速率的字符流; Markdown 渲染层用 LocalRhStreamFade 给新增块做淡入。

// 流式淡入开关: 只有"正在生成的助手消息"所在子树 provide true,
// 历史消息/用户消息保持 false(直通零开销)。
internal val LocalRhStreamFade = compositionLocalOf { false }

// rhStreamResumeFix290: 消息级"重进/重建"信号。
// ChatMessage 按 message.createdAt 年龄判定(>1s)后 provide;
// true => 该消息在本次组合前已有内容: 打字机不重放、淡入不重播。
internal val LocalRhStreamResumed = compositionLocalOf { false }

// 消息年龄阈值(ms): 超过即视为"打开/重进对话时已有内容"。
// 正常流式首块在发送后 1s 内到达, 故发送瞬间判定为 false。
internal const val RH_TW_RESUME_AGE_MS = 1000L

// 打字机参数:
// START_DELAY  首批内容到达后先攒 0.5s, 吃到足够 buffer 再开始吐字。
//              累计式计时: drive 被重启后只等剩余部分, 缓冲结束立即推进。
// BASE_RATE    基础吐字速率(字符/秒); 低于多数模型到达率, 平滑层始终工作
// CATCHUP      积压追赶窗口(秒); 积压大时 rate 提升到 backlog/CATCHUP,
//              显示最多落后约 1.5s, 速率随积压连续变化(无跳变, 观感匀速)
// FINISH_MS    生成结束后的冲线时长(剩余字符快速补完)
private const val RH_TW_START_DELAY_MS = 500L
private const val RH_TW_BASE_RATE = 24f
private const val RH_TW_CATCHUP_WINDOW_S = 1.5f
private const val RH_TW_FINISH_MS = 220

internal class RhTypewriterState {
    private val revealed = Animatable(0f)
    private var started = false
    private var startAtMillis = 0L

    // 读取当前应显示的文本(组合期调用, 无副作用)。
    // 从未流式过的历史消息(started=false, revealed=0)直通全文, 零帧空白。
    fun clip(latest: String, active: Boolean, resumed: Boolean): String { // rhStreamResumeFix290
        if ((!active || resumed) && !started && revealed.value == 0f) return latest // rhStreamResumeFix290: 历史/重进消息直通, 消除首帧空白
        val len = revealed.value.toInt()
        return if (len >= latest.length) latest else latest.substring(0, len)
    }

    // 驱动动画: target 变化时由 LaunchedEffect 重启, 从当前 revealed 匀速推进。
    // skipReplay=true: 本次组合前已有内容(打开/重进对话, 消息年龄>1s, 或滚动重建),
    // 直接 snapTo 全量, 不重放; 发送瞬间 age≈0 不属于重放, 照常走打字机。
    suspend fun drive(targetLen: Int, active: Boolean, skipReplay: Boolean) { // rhStreamResumeFix290
        if (!active) {
            if (revealed.value < targetLen) {
                if (!started && revealed.value == 0f) {
                    // 历史消息首次组合: 直接全量, 不播放任何动画
                    revealed.snapTo(targetLen.toFloat())
                } else {
                    revealed.animateTo(targetLen.toFloat(), tween(RH_TW_FINISH_MS))
                }
            }
            return
        }
        if (targetLen <= 0) return
        if (skipReplay) {
            revealed.snapTo(targetLen.toFloat())
            return
        }
        if (!started) {
            // 累计式缓冲门: 反复被 LaunchedEffect 重启也不会超过总 500ms,
            // 缓冲结束后同一协程立即推进(不依赖下一个 chunk 到来)。
            if (startAtMillis == 0L) startAtMillis = System.currentTimeMillis()
            val remain = RH_TW_START_DELAY_MS - (System.currentTimeMillis() - startAtMillis)
            if (remain > 0) delay(remain)
            started = true
        }
        val backlog = targetLen - revealed.value
        if (backlog <= 0f) return
        val rate = maxOf(RH_TW_BASE_RATE, backlog / RH_TW_CATCHUP_WINDOW_S)
        val durMs = (backlog / rate * 1000f).toInt().coerceAtLeast(60)
        revealed.animateTo(targetLen.toFloat(), tween(durationMillis = durMs, easing = LinearEasing))
    }
}

// 新块淡入: alpha 0->1 (300ms)。played 用 rememberSaveable 记录"已播放",
// 滚动出屏销毁组合后回来不重放(靠 LazyColumn 的 item 状态保存)。
// enabled=false 时直通不引入 Box, 历史消息布局逐字节不变。
@Composable
internal fun RhFadeIn(
    enabled: Boolean,
    content: @Composable () -> Unit,
) {
    if (!enabled) {
        content()
        return
    }
    var played by rememberSaveable { mutableStateOf(false) }
    if (played) {
        content()
        return
    }
    val alpha = remember { Animatable(0f) }
    LaunchedEffect(Unit) {
        alpha.animateTo(1f, tween(durationMillis = 300))
        played = true
    }
    Box(modifier = Modifier.graphicsLayer { this.alpha = alpha.value }) {
        content()
    }
}

// 流式文本按"已闭合块"切分: 代码围栏/块级公式配对才允许切;
// 仅在顶层空行处切且距上一刀>=480字符; 下一行是表格/引用/列表项/缩进续行
// 时不切; 总长<1200不切。返回 size<=1 表示未达阈值, 调用方走原路径。
private val RH_ORDERED_ITEM_285 = Regex("^[0-9]{1,3}[.)] ")

internal fun rhSplitStreamBlocks285(content: String): List<String> {
    if (content.length < 1200) return listOf(content)
    val blocks = ArrayList<String>()
    var inFence = false
    var fenceMarker = ""
    var inMath = false
    var blockStart = 0
    var i = 0
    val len = content.length
    while (i < len) {
        val lineEnd = content.indexOf('\n', i).let { if (it == -1) len else it }
        val trimmed = content.substring(i, lineEnd).trimStart()
        if (!inMath && (trimmed.startsWith("```") || trimmed.startsWith("~~~"))) {
            val marker = trimmed.take(3)
            if (!inFence) {
                inFence = true
                fenceMarker = marker
            } else if (marker == fenceMarker) {
                inFence = false
            }
        } else if (!inFence && trimmed.contains('$')) {
            val dd = trimmed.windowed(2, 1).count { it[0] == '$' && it[1] == '$' }
            if (dd % 2 == 1) inMath = !inMath
        }
        if (!inFence && !inMath && trimmed.isEmpty() && (i - blockStart) >= 480 && lineEnd + 1 < len) {
            val nextStart = lineEnd + 1
            val nextEnd = content.indexOf('\n', nextStart).let { if (it == -1) len else it }
            val nextTrimmed = content.substring(nextStart, nextEnd).trimStart()
            val nextChar = content[nextStart]
            val unsafe = nextTrimmed.startsWith("|") || nextTrimmed.startsWith(">")
                || nextTrimmed.startsWith("- ") || nextTrimmed.startsWith("* ")
                || nextTrimmed.startsWith("+ ") || RH_ORDERED_ITEM_285.containsMatchIn(nextTrimmed)
                || nextChar == ' ' || nextChar == '\t'
            if (!unsafe) {
                blocks.add(content.substring(blockStart, i))
                blockStart = nextStart
            }
        }
        i = lineEnd + 1
    }
    if (blocks.isEmpty()) return listOf(content)
    val tail = content.substring(blockStart)
    if (tail.isBlank()) return listOf(content)
    blocks.add(tail)
    return blocks
}

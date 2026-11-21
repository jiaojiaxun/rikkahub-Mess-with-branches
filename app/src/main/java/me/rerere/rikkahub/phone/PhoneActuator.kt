package me.rerere.rikkahub.phone

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.graphics.Rect
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.HandlerThread
import android.os.SystemClock
import android.view.ViewConfiguration
import android.view.accessibility.AccessibilityNodeInfo
import android.view.accessibility.AccessibilityNodeInfo.AccessibilityAction
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * rhPhone328 -- 执行器，逐条对应 dsh-go 的 a11y/Actuator.kt。
 *
 * 顺序：先试节点动作（ACTION_CLICK / ACTION_SET_TEXT），失败再往上找可点的祖先，
 * 最后才注入手势（坐标）。注入期间标记 [InjectGuard]，让悬浮确认卡拒收自己造的点击。
 */
object InjectGuard {
    @Volatile
    var until = 0L
        private set

    fun mark(durationMs: Long) {
        until = maxOf(until, SystemClock.uptimeMillis() + durationMs + 400)
    }

    fun active() = SystemClock.uptimeMillis() < until
}

class PhoneActuator(private val service: AccessibilityService) {
    private val gestureThread = HandlerThread("rh-phone-gesture").apply { start() }
    private val gestureHandler = Handler(gestureThread.looper)

    enum class Via { NODE, ANCESTOR, GESTURE }

    class Outcome(val accepted: Boolean, val via: Via?)

    fun close() {
        gestureThread.quitSafely()
    }

    /** 节点或最近的可点祖先上 ACTION_CLICK / ACTION_LONG_CLICK；最后才用点击手势。 */
    fun click(node: AccessibilityNodeInfo, bounds: Box, screen: Box, long: Boolean): Outcome {
        val action = if (long) AccessibilityNodeInfo.ACTION_LONG_CLICK else AccessibilityNodeInfo.ACTION_CLICK
        fun able(n: AccessibilityNodeInfo) = n.isEnabled && if (long) n.isLongClickable else n.isClickable
        if (able(node) && node.performAction(action)) return Outcome(true, Via.NODE)
        // 一段文字在可点的行里：手指落在那儿，命中的是那一行。
        val rect = Rect()
        var parent: AccessibilityNodeInfo? = node.parent
        var depth = 0
        while (parent != null && depth < 4) {
            parent.getBoundsInScreen(rect)
            if (able(parent) && rect.contains(bounds.centerX, bounds.centerY)) {
                if (parent.performAction(action)) return Outcome(true, Via.ANCESTOR)
                break
            }
            parent = parent.parent
            depth++
        }
        val point = visiblePoint(bounds, screen) ?: return Outcome(false, null)
        val ok = tap(point.first, point.second, long)
        return Outcome(ok, if (ok) Via.GESTURE else null)
    }

    /** [bounds] 里在屏幕上的一个点，优先中心。 */
    private fun visiblePoint(bounds: Box, screen: Box): Pair<Int, Int>? {
        val clipped = bounds.intersect(screen)
        if (clipped.isEmpty) return null
        return clipped.centerX to clipped.centerY
    }

    fun tap(x: Int, y: Int, long: Boolean = false): Boolean {
        val path = Path().apply { moveTo(x.toFloat(), y.toFloat()) }
        val duration = if (long) ViewConfiguration.getLongPressTimeout().toLong() + 300 else 60L
        return gesture(
            GestureDescription.Builder().addStroke(GestureDescription.StrokeDescription(path, 0, duration)).build(),
            duration,
        )
    }

    fun swipe(x1: Int, y1: Int, x2: Int, y2: Int, durationMs: Long = 350): Boolean {
        val path = Path().apply {
            moveTo(x1.toFloat(), y1.toFloat())
            lineTo(x2.toFloat(), y2.toFloat())
        }
        return gesture(
            GestureDescription.Builder().addStroke(GestureDescription.StrokeDescription(path, 0, durationMs)).build(),
            durationMs,
        )
    }

    /** 派发手势并等它完成。InjectGuard 覆盖手势在途的时间。 */
    fun gesture(description: GestureDescription, durationMs: Long): Boolean {
        InjectGuard.mark(durationMs)
        try {
            val latch = CountDownLatch(1)
            var completed = false
            val sent = service.dispatchGesture(
                description,
                object : AccessibilityService.GestureResultCallback() {
                    override fun onCompleted(gestureDescription: GestureDescription?) {
                        completed = true
                        latch.countDown()
                    }

                    override fun onCancelled(gestureDescription: GestureDescription?) {
                        latch.countDown()
                    }
                },
                gestureHandler,
            )
            if (!sent) return false
            latch.await(durationMs + 2_000, TimeUnit.MILLISECONDS)
            return completed
        } catch (_: Throwable) {
            return false
        } finally {
            InjectGuard.mark(0)
        }
    }

    fun setText(node: AccessibilityNodeInfo, text: String): Boolean {
        val args = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, text)
        }
        if (!node.isFocused) node.performAction(AccessibilityNodeInfo.ACTION_FOCUS)
        if (node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)) return true
        // 有些输入框要先点进去才接受文字。
        node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
        node.refresh()
        return node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
    }

    /** 键盘上的动作键（搜索 / 发送 / 完成）：仅 API 30+。 */
    fun imeEnter(node: AccessibilityNodeInfo): Boolean {
        if (Build.VERSION.SDK_INT < 30) return false
        val id = AccessibilityAction.ACTION_IME_ENTER.id
        node.refresh()
        if (node.actionList.none { it.id == id }) return false
        return node.performAction(id)
    }

    /** [direction] 有节点动作就发动作，否则在 [bounds] 里划一下。 */
    fun scroll(
        node: AccessibilityNodeInfo?,
        scrollBits: Int,
        horizontal: Boolean,
        bounds: Box,
        screen: Box,
        direction: Direction,
    ): Outcome {
        if (node != null) {
            val action = scrollAction(scrollBits, horizontal, direction)
            if (action != null && node.performAction(action)) return Outcome(true, Via.NODE)
        }
        // 避开状态栏与底部手势条。
        val area = bounds.intersect(
            Box(screen.left, screen.top + screen.height / 20, screen.right, screen.bottom - screen.height * 6 / 100)
        )
        if (area.isEmpty || area.height < 40 || area.width < 40) return Outcome(false, null)
        val cx = area.centerX
        val cy = area.centerY
        val dy = area.height * 3 / 10
        val dx = area.width * 3 / 10
        val ok = when (direction) {
            // DOWN = 看下面的内容：手指往上走。
            Direction.DOWN -> swipe(cx, cy + dy, cx, cy - dy)
            Direction.UP -> swipe(cx, cy - dy, cx, cy + dy)
            Direction.RIGHT -> swipe(cx + dx, cy, cx - dx, cy)
            Direction.LEFT -> swipe(cx - dx, cy, cx + dx, cy)
        }
        return Outcome(ok, if (ok) Via.GESTURE else null)
    }

    private fun scrollAction(bits: Int, horizontal: Boolean, direction: Direction): Int? = when (direction) {
        Direction.DOWN -> when {
            bits and Scroll.DOWN != 0 -> AccessibilityAction.ACTION_SCROLL_DOWN.id
            !horizontal && bits and Scroll.FORWARD != 0 -> AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
            else -> null
        }
        Direction.UP -> when {
            bits and Scroll.UP != 0 -> AccessibilityAction.ACTION_SCROLL_UP.id
            !horizontal && bits and Scroll.BACKWARD != 0 -> AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
            else -> null
        }
        Direction.RIGHT -> when {
            bits and Scroll.RIGHT != 0 -> AccessibilityAction.ACTION_SCROLL_RIGHT.id
            horizontal && bits and Scroll.FORWARD != 0 -> AccessibilityNodeInfo.ACTION_SCROLL_FORWARD
            else -> null
        }
        Direction.LEFT -> when {
            bits and Scroll.LEFT != 0 -> AccessibilityAction.ACTION_SCROLL_LEFT.id
            horizontal && bits and Scroll.BACKWARD != 0 -> AccessibilityNodeInfo.ACTION_SCROLL_BACKWARD
            else -> null
        }
    }

    /** back / home / recents / notifications。 */
    fun global(action: Int): Boolean = try {
        service.performGlobalAction(action)
    } catch (_: Throwable) {
        false
    }

    enum class Direction { UP, DOWN, LEFT, RIGHT }
}

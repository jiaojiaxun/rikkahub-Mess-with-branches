#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhPhone328 -- 手机操控第三批：执行层 + 无障碍服务 + Manifest 注册。

来源：dsh-go (ccch1mneyyy/dsh-go, AGPL-3.0)
  app/android/app/src/main/kotlin/io/github/ccch1mneyyy/dsh_app/phone/a11y/Actuator.kt
  app/android/app/src/main/kotlin/io/github/ccch1mneyyy/dsh_app/phone/a11y/PhoneA11yService.kt

新增：
  app/src/main/java/me/rerere/rikkahub/phone/PhoneActuator.kt
  app/src/main/java/me/rerere/rikkahub/phone/PhoneAccessibilityService.kt
  app/src/main/res/xml/phone_accessibility_service.xml
修改：
  app/src/main/AndroidManifest.xml  -- 在 application 起始属性块之后插入 service

与 dsh-go 的差异（已核对，均有理由）：
  * 没有 ControlOverlay（悬浮条是 M3），所以 gesture 里不做 setPassThrough；
    InjectGuard 保留为进程内标记，供将来的悬浮确认卡拒判"自己注入的点击"。
  * 服务不持有 PhoneCore（RikkaHub 侧由 PhoneCore 单例按需取服务实例），
    避免服务生命周期与聊天生命周期耦合。
  * 屏幕尺寸用 WindowManager 当前窗口边界（API 30+），低版本回落 displayMetrics。
"""
import os
import sys

MARK = "rhPhone328"
DIAG_NAME = "ci_diag_batch328_phone_driver.txt"
DIAG = []


def log(msg):
    line = "[batch328] " + str(msg)
    print(line)
    DIAG.append(line)


def fail(msg):
    line = "FAIL " + str(msg)
    print("::error title=phone328::" + line)
    DIAG.append(line)
    write_diag()
    sys.exit(0)


def write_diag():
    try:
        with open(DIAG_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(DIAG) + "\n")
    except Exception as exc:  # noqa: BLE001
        print("::warning title=phone328::diag write failed: " + str(exc))


def repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    guess = os.path.abspath(os.path.join(here, ".."))
    if os.path.isdir(os.path.join(guess, "app")):
        return guess
    return os.getcwd()


ROOT = repo_root()
PKG_DIR = "app/src/main/java/me/rerere/rikkahub/phone"
RES_XML = "app/src/main/res/xml"
MANIFEST = "app/src/main/AndroidManifest.xml"


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def write_text(rel, content):
    path = os.path.join(ROOT, rel)
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def write_new(rel, content):
    path = os.path.join(ROOT, rel)
    if os.path.exists(path):
        old = read(rel)
        if MARK in old:
            log("skip (already applied) " + rel)
            return
        fail("target exists without marker: " + rel + " (refusing to overwrite)")
    write_text(rel, content)
    back = read(rel)
    if MARK not in back:
        fail("read-back lost marker: " + rel)
    for op, cl in [("{", "}"), ("(", ")"), ("[", "]")]:
        if back.count(op) != back.count(cl):
            fail("unbalanced " + op + cl + " in " + rel + ": " + str(back.count(op)) + "/" + str(back.count(cl)))
    log("wrote " + rel + " (" + str(len(content)) + " chars)")


ACTUATOR = r'''package me.rerere.rikkahub.phone

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
'''

SERVICE = r'''package me.rerere.rikkahub.phone

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.graphics.Rect
import android.os.Build
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent

/**
 * rhPhone328 -- 无障碍服务：对应 dsh-go 的 a11y/PhoneA11yService.kt。
 *
 * 它只做三件事：登记自己的实例、提供当前屏幕边界、把服务被关掉的事实告诉用户。
 * 具体的读屏与动作在 PhoneCapture / PhoneActuator 里，按需取 [instance]。
 *
 * 不常驻任何任务状态：RikkaHub 的聊天生成本身已有前台服务，
 * 电话栈只在工具调用期间活着，服务断开就该立刻报"去设置里打开"。
 */
class PhoneAccessibilityService : AccessibilityService() {
    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        screen = computeScreen()
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // 不订阅事件：读屏是拉取式的，事件回调只会浪费电。
    }

    override fun onInterrupt() {
        // 系统要求实现；没有正在进行的动作需要打断。
    }

    override fun onUnbind(intent: Intent?): Boolean {
        if (instance === this) instance = null
        return super.onUnbind(intent)
    }

    override fun onDestroy() {
        if (instance === this) instance = null
        super.onDestroy()
    }

    private fun computeScreen(): Box {
        if (Build.VERSION.SDK_INT >= 30) {
            val bounds = runCatching {
                val wm = getSystemService(WindowManager::class.java)
                wm?.currentWindowMetrics?.bounds
            }.getOrNull()
            if (bounds != null && bounds.width() > 0 && bounds.height() > 0) {
                return Box(bounds.left, bounds.top, bounds.right, bounds.bottom)
            }
        }
        val metrics = resources.displayMetrics
        val rect = Rect(0, 0, metrics.widthPixels, metrics.heightPixels)
        return Box(rect.left, rect.top, rect.right, rect.bottom)
    }

    companion object {
        @Volatile
        var instance: PhoneAccessibilityService? = null
            private set

        /** 当前屏幕边界；服务没连上时给一个 1080x2400 的保守值。 */
        @Volatile
        var screen: Box = Box(0, 0, 1080, 2400)
            private set

        fun connected(): Boolean = instance != null
    }
}
'''

XML = r'''<?xml version="1.0" encoding="utf-8"?>
<!-- rhPhone328: 手机操控无障碍服务配置。isAccessibilityTool=false 是如实申报：
     本服务不是为残障用户提供的辅助工具，而是用户授权 AI 操作自己手机的通道。 -->
<accessibility-service xmlns:android="http://schemas.android.com/apk/res/android"
    android:accessibilityEventTypes="typeWindowStateChanged|typeWindowContentChanged"
    android:accessibilityFeedbackType="feedbackGeneric"
    android:accessibilityFlags="flagReportViewIds|flagRetrieveInteractiveWindows|flagIncludeNotImportantViews"
    android:canPerformGestures="true"
    android:canRetrieveWindowContent="true"
    android:isAccessibilityTool="false"
    android:notificationTimeout="100" />
'''

SERVICE_BLOCK = r'''    <!-- rhPhone328: 手机操控无障碍服务（AI 代操作通道，默认关闭，需用户在设置里显式开启） -->
    <service
      android:name=".phone.PhoneAccessibilityService"
      android:exported="true"
      android:label="手机操控"
      android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE">
      <intent-filter>
        <action android:name="android.accessibilityservice.AccessibilityService" />
      </intent-filter>
      <meta-data
        android:name="android.accessibilityservice"
        android:resource="@xml/phone_accessibility_service" />
    </service>
'''


def patch_manifest():
    text = read(MANIFEST)
    if MARK in text:
        log("skip manifest (already applied)")
        return
    needle = 'tools:targetApi="37">'
    count = text.count(needle)
    if count != 1:
        fail("manifest anchor count=" + str(count) + " for " + needle)
    text = text.replace(needle, needle + "\n" + SERVICE_BLOCK, 1)
    write_text(MANIFEST, text)
    back = read(MANIFEST)
    if MARK not in back:
        fail("manifest read-back lost marker")
    if back.count("<service") != text.count("<service"):
        fail("manifest service count mismatch")
    log("patched manifest (+1 service)")


def main():
    log("root=" + ROOT)
    write_new(PKG_DIR + "/PhoneActuator.kt", ACTUATOR)
    write_new(PKG_DIR + "/PhoneAccessibilityService.kt", SERVICE)
    write_new(RES_XML + "/phone_accessibility_service.xml", XML)
    patch_manifest()
    log("DONE")
    write_diag()


if __name__ == "__main__":
    main()
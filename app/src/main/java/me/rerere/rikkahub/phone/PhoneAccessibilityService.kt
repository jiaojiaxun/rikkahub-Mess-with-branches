package me.rerere.rikkahub.phone

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

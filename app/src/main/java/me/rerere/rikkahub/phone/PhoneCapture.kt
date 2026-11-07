package me.rerere.rikkahub.phone

import android.accessibilityservice.AccessibilityService
import android.graphics.Rect
import android.os.Build
import android.os.SystemClock
import android.view.accessibility.AccessibilityNodeInfo
import android.view.accessibility.AccessibilityNodeInfo.AccessibilityAction
import android.view.accessibility.AccessibilityWindowInfo

/**
 * rhPhone327 -- 一次读取主屏窗口：纯 Kotlin 的 [UiWindow]（给 PhoneFormat 用）
 * 加上它们索引的原生节点（[UiNode.ref] 指到这里，给 PhoneActuator 动作用）。
 * 被更新的捕获替换后调 [recycle]。
 */
class PhoneCapture(
    /** 最上层在前；最后一个是主窗口。前面没有可读内容时为空。 */
    val windows: List<UiWindow>,
    val natives: List<AccessibilityNodeInfo>,
    val keyboardShown: Boolean,
    val screen: Box,
    /** 最上层可读窗口的包名（用户正在看的那个）。 */
    val packageName: String?,
    /** RikkaHub 自己在前。照样读（"读一下当前屏幕"要显示），安全门会把它从模型侧挡掉。 */
    val ownAppInFront: Boolean,
    /** 系统窗口（通知栏、快捷设置）盖住了屏幕。 */
    val systemInFront: Boolean,
    /** 撞到节点数或时间上限：树可能不全。 */
    val truncated: Boolean,
    /**
     * 前台窗口的标题，但系统不给内容（root 为 null）：标了 accessibilityDataSensitive 的页面，
     * 非无障碍工具服务读不到。按安全窗口处理。
     */
    val hiddenWindowTitle: String? = null,
    val takenAt: Long = SystemClock.uptimeMillis(),
) {
    fun native(ref: Int): AccessibilityNodeInfo? = natives.getOrNull(ref)

    fun windowBounds(id: Int): Box? = windows.firstOrNull { it.id == id }?.bounds

    @Suppress("DEPRECATION")
    fun recycle() {
        if (Build.VERSION.SDK_INT < 33) natives.forEach { runCatching { it.recycle() } }
    }
}

object PhoneCapturer {
    private const val MAX_NODES = 2000
    private const val MAX_DEPTH = 80
    private const val MAX_WINDOWS = 4

    private val scrollIds by lazy {
        mapOf(
            AccessibilityAction.ACTION_SCROLL_FORWARD.id to Scroll.FORWARD,
            AccessibilityAction.ACTION_SCROLL_BACKWARD.id to Scroll.BACKWARD,
            AccessibilityAction.ACTION_SCROLL_UP.id to Scroll.UP,
            AccessibilityAction.ACTION_SCROLL_DOWN.id to Scroll.DOWN,
            AccessibilityAction.ACTION_SCROLL_LEFT.id to Scroll.LEFT,
            AccessibilityAction.ACTION_SCROLL_RIGHT.id to Scroll.RIGHT,
        )
    }

    private class State(val deadline: Long) {
        val natives = ArrayList<AccessibilityNodeInfo>(256)
        var count = 0
        var truncated = false
        val rect = Rect()
    }

    fun capture(service: AccessibilityService, screen: Box, ownPackage: String, budgetMs: Long): PhoneCapture {
        val st = State(SystemClock.uptimeMillis() + budgetMs)
        val all = try {
            service.windows
        } catch (_: Throwable) {
            emptyList()
        }
        val sorted = all.sortedByDescending { it.layer }
        var keyboard = false
        val chosen = mutableListOf<UiWindow>()
        var topPackage: String? = null
        var ownFront = false
        var systemFront = false
        var hidden: String? = null
        val screenArea = screen.area.coerceAtLeast(1)
        try {
            for (w in sorted) {
                when (w.type) {
                    AccessibilityWindowInfo.TYPE_INPUT_METHOD -> {
                        keyboard = true
                        continue
                    }
                    AccessibilityWindowInfo.TYPE_APPLICATION, AccessibilityWindowInfo.TYPE_SYSTEM -> {}
                    else -> continue // 我们自己的悬浮层、别的服务的悬浮窗、分屏分隔条、放大镜
                }
                if (chosen.size >= MAX_WINDOWS) break
                w.getBoundsInScreen(st.rect)
                val bounds = Box(st.rect.left, st.rect.top, st.rect.right, st.rect.bottom)
                val share = bounds.intersect(screen).area.toDouble() / screenArea
                // 状态栏、导航栏、悬浮球：小的系统窗口是外壳，不是内容。
                if (w.type == AccessibilityWindowInfo.TYPE_SYSTEM && share < 0.5) continue
                val root = w.root ?: (if (w.isActive || w.isFocused) activeRoot(service, w.id) else null)
                if (root == null) {
                    // 一扇全屏应用窗口读不到：它盖住了下面的一切。
                    if (w.type == AccessibilityWindowInfo.TYPE_APPLICATION && share >= 0.8) {
                        if (chosen.isEmpty()) hidden = if (Build.VERSION.SDK_INT >= 24) w.title?.toString() else null ?: ""
                        break
                    }
                    continue
                }
                val pkg = root.packageName?.toString()
                if (chosen.isEmpty()) {
                    topPackage = pkg
                    ownFront = pkg == ownPackage
                    systemFront = w.type == AccessibilityWindowInfo.TYPE_SYSTEM
                }
                val title = if (Build.VERSION.SDK_INT >= 24) w.title?.toString() else null
                val node = convert(root, 0, st)
                chosen += UiWindow(
                    w.id,
                    if (w.type == AccessibilityWindowInfo.TYPE_SYSTEM) WindowKind.SYSTEM else WindowKind.APP,
                    pkg,
                    title,
                    bounds,
                    node,
                )
                if (share >= 0.8) break // 全屏窗口下面的东西都算被盖住
            }
        } finally {
            @Suppress("DEPRECATION")
            if (Build.VERSION.SDK_INT < 33) all.forEach { runCatching { it.recycle() } }
        }
        return PhoneCapture(
            windows = chosen,
            natives = st.natives,
            keyboardShown = keyboard,
            screen = screen,
            packageName = topPackage,
            ownAppInFront = ownFront,
            systemInFront = systemFront,
            truncated = st.truncated,
            hiddenWindowTitle = hidden,
        )
    }

    /** 最上层应用 / 全屏系统窗口的包名，不读树。 */
    fun foregroundPackage(service: AccessibilityService, screen: Box): String? {
        val all = try {
            service.windows
        } catch (_: Throwable) {
            return null
        }
        val rect = Rect()
        try {
            for (w in all.sortedByDescending { it.layer }) {
                if (w.type != AccessibilityWindowInfo.TYPE_APPLICATION && w.type != AccessibilityWindowInfo.TYPE_SYSTEM) continue
                w.getBoundsInScreen(rect)
                val share = Box(rect.left, rect.top, rect.right, rect.bottom).intersect(screen).area.toDouble() /
                    screen.area.coerceAtLeast(1)
                if (w.type == AccessibilityWindowInfo.TYPE_SYSTEM && share < 0.5) continue
                val root = w.root ?: (if (w.isActive || w.isFocused) activeRoot(service, w.id) else null) ?: continue
                try {
                    return root.packageName?.toString()
                } finally {
                    release(root)
                }
            }
        } finally {
            @Suppress("DEPRECATION")
            if (Build.VERSION.SDK_INT < 33) all.forEach { runCatching { it.recycle() } }
        }
        return null
    }

    private fun activeRoot(service: AccessibilityService, windowId: Int): AccessibilityNodeInfo? {
        val root = try {
            service.rootInActiveWindow
        } catch (_: Throwable) {
            null
        } ?: return null
        if (root.windowId == windowId) return root
        release(root)
        return null
    }

    @Suppress("DEPRECATION")
    private fun release(node: AccessibilityNodeInfo) {
        if (Build.VERSION.SDK_INT < 33) runCatching { node.recycle() }
    }

    private fun convert(node: AccessibilityNodeInfo, depth: Int, st: State): UiNode? {
        if (!node.isVisibleToUser) {
            release(node)
            return null
        }
        if (st.count >= MAX_NODES || depth > MAX_DEPTH || SystemClock.uptimeMillis() > st.deadline) {
            st.truncated = true
            release(node)
            return null
        }
        st.count++
        node.getBoundsInScreen(st.rect)
        val box = Box(st.rect.left, st.rect.top, st.rect.right, st.rect.bottom)
        if (box.isEmpty) {
            release(node)
            return null
        }
        val ref = st.natives.size
        st.natives.add(node)

        var scroll = 0
        try {
            for (action in node.actionList) {
                val bit = scrollIds[action.id] ?: continue
                scroll = scroll or bit
            }
        } catch (_: Throwable) {
            // 拿不到 action 列表就当不可滚
        }

        val children = ArrayList<UiNode>(node.childCount.coerceAtMost(24))
        for (i in 0 until node.childCount) {
            val child = try {
                node.getChild(i)
            } catch (_: Throwable) {
                null
            } ?: continue
            val converted = convert(child, depth + 1, st) ?: continue
            children.add(converted)
        }

        return UiNode(
            ref = ref,
            className = node.className?.toString().orEmpty(),
            text = node.text?.toString(),
            desc = node.contentDescription?.toString(),
            hint = if (Build.VERSION.SDK_INT >= 26) node.hintText?.toString() else null,
            viewId = node.viewIdResourceName,
            bounds = box,
            clickable = node.isClickable,
            longClickable = node.isLongClickable,
            editable = node.isEditable,
            scrollable = node.isScrollable,
            checkable = node.isCheckable,
            checked = node.isChecked,
            selected = node.isSelected,
            focused = node.isFocused,
            enabled = node.isEnabled,
            password = node.isPassword,
            heading = if (Build.VERSION.SDK_INT >= 28) node.isHeading else false,
            showingHint = if (Build.VERSION.SDK_INT >= 26) node.isShowingHintText else false,
            scroll = scroll,
            // 没有 getRoleDescription()：Compose / Chromium 把角色放在 extras 里，读不到就 null。
            roleHint = runCatching {
                val extras = node.extras
                val role = extras?.getCharSequence("AccessibilityNodeInfo.role")
                    ?: extras?.getCharSequence("role")
                role?.toString()?.lowercase()
            }.getOrNull(),
            stateDesc = if (Build.VERSION.SDK_INT >= 30) node.stateDescription?.toString() else null,
            rangeCurrent = node.rangeInfo?.current,
            rangeMax = node.rangeInfo?.max,
            children = children,
        )
    }
}

package me.rerere.rikkahub.phone

/**
 * rhPhone326 -- 无障碍树的纯 Kotlin 副本，逐字段对应 dsh-go 的 a11y/UiTree.kt。
 *
 * 不含任何 Android 类型：PhoneCapture 从 AccessibilityNodeInfo 填它，
 * 格式化（PhoneFormat）与安全判定（PhoneRules）只吃这里的数据，
 * 因此规则可以在 JVM 单测里跑。
 */

/** 屏幕矩形（像素，左/上含，右/下不含，与 android.graphics.Rect 一致）。 */
data class Box(val left: Int, val top: Int, val right: Int, val bottom: Int) {
    val width get() = right - left
    val height get() = bottom - top
    val centerX get() = (left + right) / 2
    val centerY get() = (top + bottom) / 2
    val isEmpty get() = width <= 0 || height <= 0
    val area: Long get() = if (isEmpty) 0L else width.toLong() * height

    fun contains(x: Int, y: Int) = x >= left && x < right && y >= top && y < bottom

    /** 垂直重叠占较矮者的比例：1.0 = 同一行。 */
    fun rowOverlap(other: Box): Double {
        val overlap = minOf(bottom, other.bottom) - maxOf(top, other.top)
        val shorter = minOf(height, other.height)
        return if (overlap <= 0 || shorter <= 0) 0.0 else overlap.toDouble() / shorter
    }

    fun intersect(other: Box) = Box(
        maxOf(left, other.left),
        maxOf(top, other.top),
        minOf(right, other.right),
        minOf(bottom, other.bottom),
    )

    override fun toString() = "$left,$top,$right,$bottom"
}

/** 可滚动节点当前能往哪些方向滚（来自它的 action 列表）。 */
object Scroll {
    const val FORWARD = 1
    const val BACKWARD = 2
    const val UP = 4
    const val DOWN = 8
    const val LEFT = 16
    const val RIGHT = 32
}

/** 一个无障碍节点。[ref] 指到本次捕获的原生节点表（单测里是 -1）。 */
class UiNode(
    val ref: Int = -1,
    val className: String = "",
    val text: String? = null,
    val desc: String? = null,
    val hint: String? = null,
    val viewId: String? = null,
    val bounds: Box,
    val clickable: Boolean = false,
    val longClickable: Boolean = false,
    val editable: Boolean = false,
    val scrollable: Boolean = false,
    val checkable: Boolean = false,
    val checked: Boolean = false,
    val selected: Boolean = false,
    val focused: Boolean = false,
    val enabled: Boolean = true,
    val password: Boolean = false,
    val heading: Boolean = false,
    /** 输入框正在显示 hint（API 26+）；此时 [text] 是 hint，不是内容。 */
    val showingHint: Boolean = false,
    /** [Scroll] 的位。 */
    val scroll: Int = 0,
    /** 网页 chromeRole / Compose role 描述，小写（link / tab / button）。 */
    val roleHint: String? = null,
    /** API 30 的 stateDescription（Compose 开关、自定义控件）。 */
    val stateDesc: String? = null,
    val rangeCurrent: Float? = null,
    val rangeMax: Float? = null,
    val children: List<UiNode> = emptyList(),
)

enum class WindowKind { APP, SYSTEM }

/** 本次捕获读到的一扇窗口；[ScreenInput.windows] 里最上层在前。 */
class UiWindow(
    val id: Int,
    val kind: WindowKind,
    val packageName: String?,
    val title: String?,
    val bounds: Box,
    val root: UiNode?,
)

/**
 * collect 的去重：按文字、按屏幕顺序。列表边缘被截断的一行只露出半截文字，
 * 因此"被已收集项包含的文字"算重复，"包含已收集项的更完整文字"原地替换它。
 */
class CollectedItems {
    private val items = ArrayList<String>()
    var chars = 0
        private set

    /** [text] 带来了新内容（新的项，或某个已有项的更完整形式）时返回 true。 */
    fun add(text: String): Boolean {
        if (items.any { it == text || (text.length >= 4 && it.contains(text)) }) return false
        val shorter = items.indexOfFirst { it.length >= 4 && text.contains(it) }
        if (shorter >= 0) {
            chars += text.length - items[shorter].length
            items[shorter] = text
            return true
        }
        items += text
        chars += text.length
        return true
    }

    fun list(): List<String> = items.toList()
}

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhPhone327 -- 手机操控第二批：感知层（捕获 + 文本化）。

来源：dsh-go (ccch1mneyyy/dsh-go, AGPL-3.0)
  app/android/app/src/main/kotlin/io/github/ccch1mneyyy/dsh_app/phone/a11y/TreeCapture.kt
  app/android/app/src/main/kotlin/io/github/ccch1mneyyy/dsh_app/phone/a11y/ScreenFormat.kt

新增两个文件，不改现有文件：
  - PhoneCapture.kt：一次读取主屏所有可读窗口，填成纯 Kotlin 的 UiWindow 树；
                     同时保留原生节点表供执行层动作（ref 索引）。
  - PhoneFormat.kt ：把捕获结果渲染成模型读的紧凑文字（顶部/中部/底部三段、
                     一行一个元素、编号、⚠ 敏感标记、页预算与"…另有 N 项"）。

行为对齐要点（逐条来自 ScreenFormat.kt）：
  header  屏幕 s7 · 应用 · 竖屏 · 键盘收起 · 共 N 项
  元素    [12] 按钮 发送 · 已勾选 @540,2200
  输入框  [3] 输入框 搜索  已聚焦 / [4] 输入框(密码，不可代填)
  列表    列表 [5] 可下滑  （子项缩进 2）
  分区    顶部 / 中部 / 底部（y < 20% / > 86%）
  合并    同行同类短标签（<=16 字）用 3 空格拼一行，行宽上限 64
  预算    每页 3000 字符，优先保留底部导航，中间截断成 "…另有 N 项"
"""
import os
import sys

MARK = "rhPhone327"
DIAG_NAME = "ci_diag_batch327_phone_capture.txt"
DIAG = []


def log(msg):
    line = "[batch327] " + str(msg)
    print(line)
    DIAG.append(line)


def fail(msg):
    line = "FAIL " + str(msg)
    print("::error title=phone327::" + line)
    DIAG.append(line)
    write_diag()
    sys.exit(0)


def write_diag():
    try:
        with open(DIAG_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(DIAG) + "\n")
    except Exception as exc:  # noqa: BLE001
        print("::warning title=phone327::diag write failed: " + str(exc))


def repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    guess = os.path.abspath(os.path.join(here, ".."))
    if os.path.isdir(os.path.join(guess, "app")):
        return guess
    return os.getcwd()


ROOT = repo_root()
PKG_DIR = "app/src/main/java/me/rerere/rikkahub/phone"


def write_new(rel, content):
    path = os.path.join(ROOT, rel)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            old = f.read()
        if MARK in old:
            log("skip (already applied) " + rel)
            return
        fail("target exists without marker: " + rel + " (refusing to overwrite)")
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    with open(path, encoding="utf-8") as f:
        back = f.read()
    if MARK not in back:
        fail("read-back lost marker: " + rel)
    for op, cl in [("{", "}"), ("(", ")"), ("[", "]")]:
        if back.count(op) != back.count(cl):
            fail("unbalanced " + op + cl + " in " + rel + ": " + str(back.count(op)) + "/" + str(back.count(cl)))
    log("wrote " + rel + " (" + str(len(content)) + " chars)")


CAPTURE = r'''package me.rerere.rikkahub.phone

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

object PhoneCapture {
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
            roleHint = runCatching { node.roleDescription?.toString()?.lowercase() }.getOrNull(),
            stateDesc = if (Build.VERSION.SDK_INT >= 30) node.stateDescription?.toString() else null,
            rangeCurrent = node.rangeInfo?.current,
            rangeMax = node.rangeInfo?.max,
            children = children,
        )
    }
}
'''

FORMAT = r'''package me.rerere.rikkahub.phone

/**
 * rhPhone327 -- 模型读的紧凑屏幕文字，逐条对应 dsh-go 的 a11y/ScreenFormat.kt。
 *
 *   屏幕 s7 · 高德地图 · 竖屏 · 键盘收起 · 共 12 项
 *   顶部
 *     [1] 按钮 返回
 *     [2] 输入框 "瑞幸咖啡" 已聚焦
 *   列表 [4] 可下滑
 *     [5] 瑞幸咖啡(科技园店) · 4.6分 · 320m · 营业中
 *         [6] 按钮 路线   [7] 按钮 电话
 *   底部
 *     [11] 标签 综合排序 · 已选   [12] 标签 距离优先
 *
 * 规则：一个"可交互或带文字"的节点一行，纯布局节点折叠；
 * 可点行收下它那些不可交互后代的文字（TalkBack 的朗读单元）；
 * 文字顺序 text → contentDescription → hint → view-id 尾部；
 * 每段标签 60 字、每页约 3000 字，超出写 "…另有 N 项"；
 * 按位置分 顶部 / 中部 / 底部，每层滚动容器缩进一级；
 * 安全门会问的动作在行首标 ⚠，密码内容永不渲染。纯 Kotlin。
 */
class ScreenInput(
    val screenId: String,
    val appLabel: String?,
    val packageName: String?,
    val screenWidth: Int,
    val screenHeight: Int,
    val keyboardShown: Boolean,
    /** 最上层在前；最后一个是主窗口，其它渲染成 弹窗。 */
    val windows: List<UiWindow>,
    val detail: Boolean = false,
    /** 同一 App 上一次快照的元素键（标 +）。null = 不标。 */
    val previousKeys: Set<String>? = null,
    /** header 下面的额外行（受保护页、安全窗口…）。 */
    val notes: List<String> = emptyList(),
    val charBudget: Int = 3000,
)

enum class ElementKind { ITEM, INPUT, LIST }

/** 快照里的一个带编号元素。 */
class ScreenElement(
    val id: Int,
    val windowId: Int,
    val packageName: String?,
    /** 本次捕获原生节点表的下标。 */
    val ref: Int,
    val kind: ElementKind,
    val role: String,
    /** 渲染出来的样子：已遮罩、<= 60 字。输入框这里是名字，绝不是内容。 */
    val label: String,
    /** 已遮罩、不截断（<= 300）：行内文字，供 collect 与操作日志用。 */
    val fullText: String,
    val bounds: Box,
    val clickable: Boolean,
    val longClickable: Boolean,
    val editable: Boolean,
    val password: Boolean,
    val secret: Boolean,
    val checkable: Boolean,
    val scroll: Int,
    val horizontal: Boolean,
    val viewId: String?,
    /** 让这次点击要先问用户的敏感词（⚠），没有则 null。 */
    val sensitiveWord: String?,
    /** 所属列表的编号。 */
    val listId: Int?,
    /** 一行里的控件所属那一行的编号。 */
    val parentId: Int?,
    /** 每次动作前复验：window | bounds | role | text（| checked）。 */
    val fingerprint: String,
    /** + 与上一次快照比较用的键。 */
    val key: String,
)

class FormattedScreen(
    val text: String,
    val elements: List<ScreenElement>,
    /** 带文字或描述的节点数（低于 [PhoneFormat.POOR_TREE] 说明树太差）。 */
    val textNodes: Int,
    val poorTree: Boolean,
    val keys: Set<String>,
    /** 被页预算省掉的元素数。 */
    val hidden: Int,
) {
    fun element(id: Int): ScreenElement? =
        elements.getOrNull(id - 1)?.takeIf { it.id == id } ?: elements.firstOrNull { it.id == id }
}

object PhoneFormat {
    const val LABEL_CAP = 60
    const val FULL_CAP = 300
    const val POOR_TREE = 5
    private const val ROW_CAP = 64
    private const val MERGE_LABEL = 16
    private const val NEW_RATIO_LIMIT = 0.6

    const val POOR_TREE_NOTE =
        "提示：本页文字信息不足（游戏、自绘界面、部分小程序常见）。能看图的模型可以在 screen 里加 image 看标号截图；否则请用户协助。"

    fun format(input: ScreenInput): FormattedScreen {
        val textNodes = input.windows.sumOf { w -> w.root?.let(::countText) ?: 0 }
        val lines = mutableListOf<Line>()
        val windows = input.windows.filter { it.root != null }
        for ((index, window) in windows.withIndex()) {
            val items = flatten(window.root!!, window, null)
                .sortedWith(compareBy({ it.node.bounds.top }, { it.node.bounds.left }))
            if (index < windows.size - 1) {
                if (items.isEmpty()) continue
                lines += Line.Header(
                    if (window.title.isNullOrBlank()) "弹窗" else "弹窗 · " + clip(clean(window.title) ?: "", 20)
                )
                emit(items, 2, lines, false, null, null)
            } else {
                zones(items, input.screenHeight, lines)
            }
        }

        val notes = input.notes.toMutableList()
        val poor = textNodes < POOR_TREE && windows.isNotEmpty()
        if (poor) notes += POOR_TREE_NOTE

        // 页预算：保住底部（导航），从中间截断并给提示。
        val headerLen = 40 + (input.appLabel?.length ?: 0) + notes.sumOf { it.length + 1 }
        val lengths = lines.map { it.estimate(input.detail) }
        val total = headerLen + lengths.sum()
        var kept: List<Line> = lines
        var hidden = 0
        if (total > input.charBudget) {
            val reservedLen = lines.indices.filter { lines[it].reserved }.sumOf { lengths[it] }
            val keepReserved = headerLen + reservedLen + 60 < input.charBudget * 2 / 3
            var available = input.charBudget - headerLen - 40 - (if (keepReserved) reservedLen else 0)
            val out = mutableListOf<Line>()
            var cut = false
            for ((i, line) in lines.withIndex()) {
                if (keepReserved && line.reserved) {
                    out += line
                    continue
                }
                if (!cut && lengths[i] <= available) {
                    out += line
                    available -= lengths[i]
                    continue
                }
                if (!cut) {
                    cut = true
                    out += Line.More(line.indent)
                }
                hidden += line.elementCount()
            }
            if (hidden > 0) out.filterIsInstance<Line.More>().forEach { it.count = hidden }
            kept = out
        }

        // 阅读顺序发号。
        val ids = HashMap<Item, Int>()
        var next = 1
        for (line in kept) for (item in line.items()) ids[item] = next++
        val count = next - 1

        val prev = input.previousKeys
        val keyOf = HashMap<Item, String>()
        for (item in ids.keys) keyOf[item] = item.key()
        val markNew = prev != null && count > 0 &&
            ids.keys.count { it.kind != ElementKind.LIST && keyOf[it] !in prev }.toDouble() / count <= NEW_RATIO_LIMIT

        val orientation = if (input.screenWidth > input.screenHeight) "横屏" else "竖屏"
        val keyboard = if (input.keyboardShown) "键盘弹出" else "键盘收起"
        val app = clean(input.appLabel) ?: input.packageName ?: "未知应用"
        val header = StringBuilder()
        header.append("屏幕 ").append(input.screenId).append(" · ").append(app).append(" · ")
            .append(orientation).append(" · ").append(keyboard).append(" · 共 ").append(count).append(" 项")
        for (note in notes) header.append('\n').append(note)
        if (count == 0) header.append('\n').append("（没有可读的元素）")
        for (line in kept) {
            header.append('\n')
            header.append(line.render(ids, input.detail) { item -> markNew && item.kind != ElementKind.LIST && keyOf[item] !in prev })
        }

        val elements = ids.entries.sortedBy { it.value }.map { (item, id) ->
            item.toElement(id, item.list?.let { ids[it] }, item.parent?.let { ids[it] }, keyOf[item] ?: "")
        }
        val keys = ids.keys.map { keyOf[it] ?: "" }.toSet()
        return FormattedScreen(header.toString(), elements, textNodes, poor, keys, hidden)
    }

    /** 全部元素，不受页预算限制（复验、collect）。 */
    fun index(windows: List<UiWindow>): List<ScreenElement> {
        val out = mutableListOf<ScreenElement>()
        var next = 1
        for (window in windows) {
            val root = window.root ?: continue
            val items = flatten(root, window, null)
                .sortedWith(compareBy({ it.node.bounds.top }, { it.node.bounds.left }))
            for (item in items) {
                out += item.toElement(next++, null, null, item.key())
                for (sub in item.subs) out += sub.toElement(next++, null, null, sub.key())
            }
        }
        return out
    }

    // ---- 折叠 ---------------------------------------------------------------------------

    private class Item(
        val node: UiNode,
        val window: UiWindow,
        val kind: ElementKind,
        val role: String,
        /** 已遮罩、单行、不截断。输入框这里是名字。 */
        val label: String,
        val states: List<String>,
        /** 输入框内容（已遮罩）；空 / 密码 / 机密时为 null。 */
        val content: String?,
        val subs: List<Item>,
        val checkedState: Boolean?,
        val secret: Boolean,
        val horizontal: Boolean = false,
    ) {
        var list: Item? = null
        var parent: Item? = null

        val sensitive: String? = if (
            kind == ElementKind.ITEM && (node.clickable || node.longClickable || node.checkable) && role != "文本"
        ) SensitiveWords.confirmHit(label, node.viewId) else null

        fun fingerprint(): String {
            val identity = when (kind) {
                ElementKind.LIST -> node.className + "|" + node.viewId + "|" + label
                ElementKind.INPUT -> label + "|" + node.viewId + "|" + node.password
                ElementKind.ITEM -> label
            }
            return "w" + window.id + "|" + node.bounds + "|" + role + "|" + identity +
                (checkedState?.let { "|c=" + it } ?: "")
        }

        fun key() = role + "|" + clip(label, LABEL_CAP)

        fun fullText(): String {
            val parts = mutableListOf<String>()
            if (label.isNotEmpty()) parts += label
            if (kind == ElementKind.INPUT && content != null) parts += "\"" + content + "\""
            if (kind != ElementKind.LIST) {
                for (sub in subs) {
                    if (sub.kind == ElementKind.LIST) {
                        sub.subs.forEach { if (it.label.isNotEmpty()) parts += it.label }
                    } else if (sub.role == "文本" || sub.role == "图片" || sub.role == "标题" || sub.role == "") {
                        if (sub.label.isNotEmpty()) parts += sub.label
                    }
                }
            }
            return clip(parts.distinct().joinToString(" · "), FULL_CAP)
        }

        fun toElement(id: Int, listId: Int?, parentId: Int?, key: String) = ScreenElement(
            id = id,
            windowId = window.id,
            packageName = window.packageName,
            ref = node.ref,
            kind = kind,
            role = role,
            label = clip(label, LABEL_CAP),
            fullText = fullText(),
            bounds = node.bounds,
            clickable = node.clickable,
            longClickable = node.longClickable,
            editable = kind == ElementKind.INPUT,
            password = node.password,
            secret = secret,
            checkable = node.checkable,
            scroll = node.scroll,
            horizontal = horizontal,
            viewId = node.viewId,
            sensitiveWord = sensitive,
            listId = listId,
            parentId = parentId,
            fingerprint = fingerprint(),
            key = key,
        )
    }

    private fun actionable(n: UiNode) = n.clickable || n.longClickable || n.checkable

    private fun isList(n: UiNode) = n.scrollable && n.children.isNotEmpty() && !n.editable

    private fun flatten(node: UiNode, window: UiWindow, parentClass: String?): List<Item> = when {
        node.editable -> listOf(input(node, window))
        isList(node) -> listOf(list(node, window))
        actionable(node) -> action(node, window, parentClass)
        else -> {
            val own = clean(node.text) ?: clean(node.desc)
            val children = node.children.flatMap { flatten(it, window, node.className) }
            if (own == null) {
                children
            } else {
                listOf(text(node, window, own, parentClass)) +
                    children.filterNot {
                        it.kind == ElementKind.ITEM && it.subs.isEmpty() && it.role == "文本" && it.label == own
                    }
            }
        }
    }

    private fun text(node: UiNode, window: UiWindow, label: String, parentClass: String?): Item {
        val role = when {
            node.heading -> "标题"
            role(node, true, parentClass) == "标签" -> "标签"
            node.text.isNullOrBlank() && isImage(node) -> "图片"
            else -> "文本"
        }
        val states = if (node.selected) listOf("已选") else emptyList()
        return Item(node, window, ElementKind.ITEM, role, label, states, null, emptyList(), null, false)
    }

    private fun input(node: UiNode, window: UiWindow): Item {
        val hint = clean(node.hint) ?: if (node.showingHint) clean(node.text) else null
        val secretWord = SensitiveWords.secretHit(hint, node.desc, node.viewId)
        val name = clean(node.desc) ?: hint ?: idTail(node.viewId) ?: ""
        val secret = secretWord != null && !node.password
        val role = when {
            node.password -> "输入框(密码，不可代填)"
            secret -> "输入框(" + secretLabel(secretWord) + "，不可代填)"
            else -> "输入框"
        }
        val content = if (node.password || secret || node.showingHint) null else clean(node.text)
        val states = mutableListOf<String>()
        if (content == null && !node.password && !secret) states += "空"
        if (node.focused) states += "已聚焦"
        if (!node.enabled) states += "不可用"
        return Item(node, window, ElementKind.INPUT, role, name, states, content, emptyList(), null, secret)
    }

    private fun list(node: UiNode, window: UiWindow): Item {
        val subs = node.children.flatMap { flatten(it, window, node.className) }
        val horizontal = node.scroll and (Scroll.LEFT or Scroll.RIGHT) != 0 ||
            node.className.contains("Horizontal") || node.className.contains("ViewPager") ||
            (node.children.size >= 2 && node.children[0].bounds.rowOverlap(node.children[1].bounds) > 0.5 &&
                node.children[1].bounds.left >= node.children[0].bounds.right - 2)
        val forward = node.scroll and Scroll.FORWARD != 0
        val backward = node.scroll and Scroll.BACKWARD != 0
        val states = if (horizontal) {
            val right = node.scroll and Scroll.RIGHT != 0 || forward
            val left = node.scroll and Scroll.LEFT != 0 || backward
            listOfNotNull(
                when {
                    left && right -> "可左右滑"
                    right -> "可右滑"
                    left -> "可左滑"
                    else -> null
                }
            )
        } else {
            val down = node.scroll and Scroll.DOWN != 0 || forward
            val up = node.scroll and Scroll.UP != 0 || backward
            listOfNotNull(
                when {
                    up && down -> "可上下滑"
                    down -> "可下滑"
                    up -> "可上滑"
                    else -> null
                }
            )
        }
        val label = clean(node.desc) ?: ""
        return Item(node, window, ElementKind.LIST, "列表", label, states, null, subs, null, false, horizontal)
    }

    private fun action(node: UiNode, window: UiWindow, parentClass: String?): List<Item> {
        val texts = mutableListOf<String>()
        val subs = mutableListOf<Item>()
        fun gather(n: UiNode) {
            for (c in n.children) {
                when {
                    c.editable -> subs += input(c, window)
                    isList(c) -> subs += list(c, window)
                    actionable(c) -> subs += action(c, window, n.className)
                    else -> {
                        (clean(c.text) ?: clean(c.desc))?.let { texts += it }
                        gather(c)
                    }
                }
            }
        }
        gather(node)

        // 一行里只有一个不可点的开关 / 复选框时，整行读成那个开关（设置项）。
        var checkNode: UiNode? = if (node.checkable) node else null
        if (checkNode == null) {
            val found = mutableListOf<UiNode>()
            fun collect(n: UiNode) {
                for (c in n.children) {
                    if (c.checkable && !actionable(c)) found.add(c) else collect(c)
                }
            }
            collect(node)
            if (found.size == 1) checkNode = found[0]
        }
        val check = checkNode
        val checkChecked = check?.checked

        val own = clean(node.text) ?: clean(node.desc)
        val label = own ?: texts.joinToString(" · ").ifBlank { null }
        val roleText = role(check ?: node, own != null, parentClass, check != null)

        val states = mutableListOf<String>()
        if (check != null) states += if (check.checked) "已勾选" else "未勾选"
        if (node.selected) states += "已选"
        val current = node.rangeCurrent
        val max = node.rangeMax
        if (current != null) {
            states += if (max != null && max > 0f && max <= 1000f && max != 100f) fmt(current) + "/" + fmt(max) else fmt(current)
        }
        clean(node.stateDesc)?.let { sd ->
            if (roleText != "开关" && roleText != "勾选框" && roleText != "单选" && sd.length <= 10 && sd != label && sd !in states) {
                states += sd
            }
        }
        if (!node.enabled) states += "不可用"
        val item = Item(node, window, ElementKind.ITEM, roleText, label ?: "", states, null, subs, checkChecked, false)
        return listOf(item)
    }

    private fun role(node: UiNode, ownText: Boolean, parentClass: String?, forcedCheck: Boolean = false): String {
        val cls = node.className.substringAfterLast('.')
        val hint = node.roleHint
        return when {
            cls.contains("Switch") || cls == "ToggleButton" || hint == "switch" || hint == "开关" -> "开关"
            cls == "CheckBox" || cls == "CheckedTextView" || hint == "checkbox" || hint == "复选框" -> "勾选框"
            cls == "RadioButton" || hint == "radio" || hint == "radiobutton" || hint == "单选按钮" -> "单选"
            cls == "SeekBar" || cls == "RatingBar" || cls.contains("Slider") || hint == "slider" || hint == "滑块" -> "滑块"
            cls == "Spinner" || hint == "combobox" || hint == "popupbutton" || hint == "下拉列表" -> "下拉框"
            hint == "link" || hint == "链接" -> "链接"
            cls.contains("TabView") || cls.endsWith("\$Tab") || cls == "Tab" || hint == "tab" || hint == "标签" ||
                cls.contains("NavigationItemView") || cls.contains("NavigationBarItemView") ||
                (parentClass != null && (
                    parentClass.contains("TabWidget") || parentClass.contains("TabLayout") ||
                        parentClass.contains("BottomNavigation")
                    )) -> "标签"
            forcedCheck || node.checkable -> "勾选框"
            cls == "Button" || cls == "ImageButton" || cls.endsWith("Button") || hint == "button" || hint == "按钮" -> "按钮"
            isImage(node) -> "按钮"
            ownText && node.children.isEmpty() -> "按钮"
            else -> ""
        }
    }

    // ---- 行 -----------------------------------------------------------------------------

    private sealed class Line(val indent: Int, val reserved: Boolean) {
        abstract fun items(): List<Item>
        open fun elementCount() = items().size
        abstract fun estimate(detail: Boolean): Int
        abstract fun render(ids: Map<Item, Int>, detail: Boolean, isNew: (Item) -> Boolean): String

        class Header(val text: String, reserved: Boolean = false) : Line(0, reserved) {
            override fun items() = emptyList<Item>()
            override fun estimate(detail: Boolean) = text.length + 1
            override fun render(ids: Map<Item, Int>, detail: Boolean, isNew: (Item) -> Boolean) = text
        }

        class More(indent: Int) : Line(indent, false) {
            var count = 0
            override fun items() = emptyList<Item>()
            override fun estimate(detail: Boolean) = 30
            override fun render(ids: Map<Item, Int>, detail: Boolean, isNew: (Item) -> Boolean) =
                " ".repeat(indent) + "…另有 " + count + " 项，用 collect 或 scroll"
        }

        class Row(indent: Int, reserved: Boolean, val row: List<Item>) : Line(indent, reserved) {
            override fun items() = row
            override fun estimate(detail: Boolean) =
                indent + row.sumOf { body(it, 99, detail, false).length + 3 }

            override fun render(ids: Map<Item, Int>, detail: Boolean, isNew: (Item) -> Boolean) =
                " ".repeat(indent) + row.joinToString("   ") { body(it, ids[it] ?: 0, detail, isNew(it)) }
        }

        class ListHead(indent: Int, reserved: Boolean, val list: Item) : Line(indent, reserved) {
            override fun items() = listOf(list)
            override fun estimate(detail: Boolean) = indent + body(list, 99, detail, false).length + 1
            override fun render(ids: Map<Item, Int>, detail: Boolean, isNew: (Item) -> Boolean) =
                " ".repeat(indent) + body(list, ids[list] ?: 0, detail, false)
        }
    }

    private enum class Zone(val title: String) { TOP("顶部"), MIDDLE("中部"), BOTTOM("底部") }

    private fun zones(items: List<Item>, screenHeight: Int, out: MutableList<Line>) {
        val h = screenHeight.coerceAtLeast(1)
        fun zone(item: Item): Zone {
            val b = item.node.bounds
            return when {
                b.centerY < h * 0.2 -> Zone.TOP
                b.centerY > h * 0.86 -> Zone.BOTTOM
                else -> Zone.MIDDLE
            }
        }
        val byZone = items.groupBy(::zone)
        byZone[Zone.TOP]?.let {
            out += Line.Header(Zone.TOP.title)
            emit(it, 2, out, false, null, null)
        }
        byZone[Zone.MIDDLE]?.let { middle ->
            var needHeader = true
            val run = mutableListOf<Item>()
            fun flush() {
                if (run.isNotEmpty()) {
                    if (needHeader) out += Line.Header(Zone.MIDDLE.title)
                    needHeader = false
                    emit(run.toList(), 2, out, false, null, null)
                    run.clear()
                }
            }
            for (item in middle) {
                if (item.kind == ElementKind.LIST) {
                    flush()
                    emit(listOf(item), 0, out, false, null, null)
                    needHeader = true
                } else {
                    run += item
                }
            }
            flush()
        }
        byZone[Zone.BOTTOM]?.let {
            out += Line.Header(Zone.BOTTOM.title, reserved = true)
            emit(it, 2, out, true, null, null)
        }
    }

    private fun emit(items: List<Item>, indent: Int, out: MutableList<Line>, reserved: Boolean, list: Item?, parent: Item?) {
        var i = 0
        while (i < items.size) {
            val item = items[i]
            item.list = list
            item.parent = parent
            if (item.kind == ElementKind.LIST) {
                out += Line.ListHead(indent, reserved, item)
                emit(item.subs, indent + 2, out, reserved, item, null)
                i++
                continue
            }
            val row = mutableListOf(item)
            var length = body(item, 99, false, false).length
            while (i + 1 < items.size && mergeable(row.last(), items[i + 1])) {
                val nextItem = items[i + 1]
                val add = body(nextItem, 99, false, false).length + 3
                if (indent + length + add > ROW_CAP) break
                nextItem.list = list
                nextItem.parent = parent
                row += nextItem
                length += add
                i++
            }
            out += Line.Row(indent, reserved, row)
            for (member in row) if (member.subs.isNotEmpty()) emit(member.subs, indent + 4, out, reserved, list, member)
            i++
        }
    }

    private fun mergeable(a: Item, b: Item) =
        a.kind == ElementKind.ITEM && b.kind == ElementKind.ITEM && a.subs.isEmpty() && b.subs.isEmpty() &&
            a.role.isNotEmpty() && a.role == b.role &&
            a.label.length <= MERGE_LABEL && b.label.length <= MERGE_LABEL &&
            a.node.bounds.rowOverlap(b.node.bounds) >= 0.5 && b.node.bounds.left >= a.node.bounds.left

    private fun body(item: Item, id: Int, detail: Boolean, isNew: Boolean): String {
        val sb = StringBuilder()
        if (item.kind == ElementKind.LIST) {
            sb.append("列表 [").append(id).append(']')
            if (item.label.isNotEmpty()) sb.append(' ').append(clip(item.label, LABEL_CAP))
            if (item.states.isNotEmpty()) {
                sb.append(if (item.label.isNotEmpty()) " · " else " ").append(item.states.joinToString(" · "))
            }
        } else {
            if (isNew) sb.append('+')
            if (item.sensitive != null) sb.append('⚠')
            sb.append('[').append(id).append(']')
            if (item.role.isNotEmpty()) sb.append(' ').append(item.role)
            val label = clip(item.label, LABEL_CAP)
            if (label.isNotEmpty()) sb.append(' ').append(label)
            if (item.kind == ElementKind.INPUT && item.content != null) {
                sb.append(" \"").append(clip(item.content, LABEL_CAP)).append('"')
                if (item.states.isNotEmpty()) sb.append(' ').append(item.states.joinToString(" · "))
            } else if (item.states.isNotEmpty()) {
                sb.append(if (label.isNotEmpty() || item.role.isNotEmpty()) " · " else " ")
                    .append(item.states.joinToString(" · "))
            }
            if (label.isEmpty() && item.role.isNotEmpty() && item.kind == ElementKind.ITEM && item.states.isEmpty()) {
                sb.append(" (无文字)")
            }
        }
        if (detail) sb.append(" @").append(item.node.bounds.centerX).append(',').append(item.node.bounds.centerY)
        return sb.toString()
    }

    // ---- 文本工具 -----------------------------------------------------------------------

    private val space = Regex("\\s+")
    private val invisible = Regex("[\\u200B-\\u200F\\u2060\\uFEFF]")

    /** 单行、已遮罩，空白返回 null。 */
    fun clean(value: String?): String? {
        if (value.isNullOrBlank()) return null
        val flat = space.replace(invisible.replace(value, ""), " ").trim()
        return if (flat.isEmpty()) null else ScreenMask.mask(flat)
    }

    fun clip(value: String, cap: Int) = if (value.length <= cap) value else value.take(cap - 1) + "…"

    fun idTail(viewId: String?): String? =
        viewId?.substringAfterLast(":id/")?.substringAfterLast('/')?.takeIf { it.isNotBlank() }

    private fun isImage(node: UiNode) =
        node.className.endsWith("ImageView") || node.className.endsWith("Image") ||
            node.roleHint == "image" || node.roleHint == "img"

    private fun secretLabel(word: String?) = when (word) {
        "支付密码" -> "支付密码"
        "密码", "password", "passcode", "passwd", "pwd" -> "密码"
        "安全码", "cvv", "cvc" -> "安全码"
        else -> "验证码"
    }

    private fun fmt(value: Float) = if (value == value.toLong().toFloat()) value.toLong().toString() else "%.1f".format(value)

    /** [windows] 里带文字或描述的节点数：低于 [POOR_TREE] 就是"树太差"。 */
    fun textCount(windows: List<UiWindow>) = windows.sumOf { w -> w.root?.let(::countText) ?: 0 }

    private fun countText(node: UiNode): Int =
        (if (!node.text.isNullOrBlank() || !node.desc.isNullOrBlank()) 1 else 0) + node.children.sumOf(::countText)
}
'''

FILES = [
    (PKG_DIR + "/PhoneCapture.kt", CAPTURE),
    (PKG_DIR + "/PhoneFormat.kt", FORMAT),
]


def main():
    log("root=" + ROOT)
    for rel, body in FILES:
        if MARK not in body:
            fail("generated body missing marker: " + rel)
        write_new(rel, body)
    log("DONE files=" + str(len(FILES)))
    write_diag()


if __name__ == "__main__":
    main()
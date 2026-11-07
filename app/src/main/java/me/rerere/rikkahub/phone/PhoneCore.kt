package me.rerere.rikkahub.phone

import android.accessibilityservice.AccessibilityService
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.AlarmClock
import android.provider.Settings
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonPrimitive
import java.util.Collections

/**
 * rhPhone329 -- 手机操控的调度核心，对应 dsh-go 的 phone/PhoneCore.kt（M1 子集）。
 *
 * 一次调用 = 串行队列里的一步：读屏 / 点 / 输入 / 滚 / 按键 / 开应用 / 交接。
 * 所有动作前都过 [checkWrite]（自己 / deny 名单 / 系统页 / 机密输入 → 硬拒绝），
 * 动作后再读一次屏，把新屏幕还给模型。
 *
 * 编号规则：每次读屏生成一个屏幕号（s1、s2…），元素编号只在该屏幕号内有效；
 * 工具带来的 screen 与最近一次不一致时，直接告诉模型"屏幕已变化，重新 screen"，
 * 而不是拿旧坐标乱点。
 */
object PhoneCore {
    private val mutex = Mutex()
    private val approvedApps: MutableSet<String> = Collections.synchronizedSet(mutableSetOf<String>())

    /** 用户设置里的策略；设置页写入，这里只读。 */
    @Volatile
    var policies: PhonePolicies = PhonePolicies()

    @Volatile
    private var seq = 0

    @Volatile
    private var last: Snapshot? = null

    /** 一次调用的结果：正文 + 是否算失败。 */
    class Result(val text: String, val failed: Boolean = false)

    class Snapshot(
        val id: String,
        val capture: PhoneCapture,
        val formatted: FormattedScreen,
        val at: Long,
    )

    private class Refused(message: String) : Exception(message)

    // ---- 入口 ---------------------------------------------------------------------------

    suspend fun call(context: Context, tool: String, args: JsonObject): Result = mutex.withLock {
        withContext(Dispatchers.IO) {
            try {
                when (tool) {
                    PHONE_SCREEN -> screen(context, args)
                    PHONE_COLLECT -> collect(context, args)
                    PHONE_TAP -> tap(context, args)
                    PHONE_TYPE -> type(context, args)
                    PHONE_SCROLL -> scroll(context, args)
                    PHONE_KEY -> key(context, args)
                    PHONE_TAP_XY -> tapXY(context, args)
                    PHONE_OPEN -> open(context, args)
                    PHONE_APPS -> apps(context, args)
                    PHONE_HANDOFF -> handoff(context, args)
                    PHONE_INTENT -> intent(context, args)
                    else -> Result("未知的手机操控工具：$tool", true)
                }
            } catch (e: Refused) {
                Result(e.message ?: "被安全规则拒绝", true)
            } catch (e: Throwable) {
                Result("手机操控失败：" + (e.message ?: e.toString()), true)
            }
        }
    }

    /** 清掉上一次任务的记账（新任务开始时调用；M2 接到会话切换上）。 */
    fun resetTask() {
        approvedApps.clear()
        last = null
    }

    fun connected(): Boolean = PhoneAccessibilityService.connected()

    // ---- 读屏 ---------------------------------------------------------------------------

    private fun screen(context: Context, args: JsonObject): Result {
        val service = requireService()
        val detail = args.bool("detail")
        val cap = capture(service, context)
        val snap = publish(context, cap, detail, null, notesFor(cap, service))
        return Result(snap.formatted.text)
    }

    private fun collect(context: Context, args: JsonObject): Result {
        val service = requireService()
        val snap = requireSnapshot(args.str("screen"))
        val listId = args.int("list") ?: return Result("collect 需要 list（列表编号）", true)
        val listEl = snap.formatted.element(listId) ?: return Result("这个屏幕里没有编号 $listId 的列表", true)
        if (listEl.kind != ElementKind.LIST) return Result("[$listId] 不是列表，不能 collect", true)
        val maxPages = (args.int("max_pages") ?: 10).coerceIn(1, 30)
        val until = args.str("until")
        val collected = CollectedItems()

        var cap = snap.capture
        var el = listEl
        val notes = mutableListOf<String>()
        for (page in 0 until maxPages) {
            for (sub in subTexts(cap, el)) collected.add(sub)
            notes.add("列表 ${el.id} 第 " + (page + 1) + " 页：" + collected.list().size + " 条")
            if (until != null && collected.list().any { it.contains(until) }) break
            val node = cap.native(el.ref) ?: break
            val actuator = PhoneActuator(service)
            val outcome = try {
                actuator.scroll(node, el.scroll, el.horizontal, el.bounds, cap.screen, PhoneActuator.Direction.DOWN)
            } finally {
                actuator.close()
            }
            if (!outcome.accepted) break
            sleepForUi()
            val next = capture(service, context)
            if (sameItems(cap, next, el)) break
            cap.recycle()
            cap = next
            el = equivalentList(next, el) ?: break
        }
        cap.recycle()
        val text = buildString {
            append("收集完成，共 ").append(collected.list().size).append(" 条")
            if (collected.chars > 0) append("（").append(collected.chars).append(" 字）")
            append('\n')
            collected.list().forEach { append("- ").append(it).append('\n') }
        }
        return Result(text.trimEnd())
    }

    // ---- 动作 ---------------------------------------------------------------------------

    private fun tap(context: Context, args: JsonObject): Result {
        val service = requireService()
        val snap = requireSnapshot(args.str("screen"))
        val id = args.int("id") ?: return Result("tap 需要 id（元素编号）", true)
        val el = snap.formatted.element(id) ?: return Result("这个屏幕里没有编号 $id 的元素", true)
        val node = snap.capture.native(el.ref) ?: return Result("[$id] 已经不在了，重新 screen 一下", true)
        if (!node.isVisibleToUser) return Result("[$id] 已经不可见，重新 screen 一下", true)
        checkWrite(context, snap, WriteKind.TAP, el, null, false, null)
        val actuator = PhoneActuator(service)
        val outcome = try {
            actuator.click(node, el.bounds, snap.capture.screen, args.bool("long"))
        } finally {
            actuator.close()
        }
        if (!outcome.accepted) return Result("点击 [$id] 没有生效（界面可能已经变化）", true)
        sleepForUi()
        val next = publish(context, capture(service, context), false, snap.formatted.keys, emptyList())
        return Result("已点击 " + describeElement(el) + "\n" + next.formatted.text)
    }

    private fun type(context: Context, args: JsonObject): Result {
        val service = requireService()
        val snap = requireSnapshot(args.str("screen"))
        val id = args.int("id") ?: return Result("type 需要 id（输入框编号）", true)
        val text = args.str("text") ?: return Result("type 需要 text", true)
        val submit = args.bool("submit")
        val el = snap.formatted.element(id) ?: return Result("这个屏幕里没有编号 $id 的输入框", true)
        if (el.kind != ElementKind.INPUT && !el.editable) return Result("[$id] 不是输入框", true)
        val target = TargetInfo(
            screenId = snap.id,
            id = el.id,
            role = el.role,
            label = el.label,
            packageName = el.packageName,
            appLabel = snap.formatted.text.lineSequence().firstOrNull()?.split(" · ")?.getOrNull(1),
            password = el.password,
            isSecretField = el.secret,
            editable = el.editable,
            viewId = el.viewId,
        )
        checkWrite(context, snap, WriteKind.TYPE, el, text, submit, target)
        val node = snap.capture.native(el.ref) ?: return Result("[$id] 已经不在了，重新 screen 一下", true)
        val actuator = PhoneActuator(service)
        try {
            if (!actuator.setText(node, text)) return Result("这个输入框不接受直接写文字，可以让用户点一下再试", true)
            if (submit) actuator.imeEnter(node)
        } finally {
            actuator.close()
        }
        // 回读：秘密字段不回读内容，只确认焦点离开了输入框。
        val readBack = runCatching { node.text?.toString() }.getOrNull()
        val masked = if (el.password || el.secret) PhoneRules.MASK else text
        sleepForUi()
        val next = publish(context, capture(service, context), false, snap.formatted.keys, emptyList())
        val note = when {
            el.password || el.secret -> "已输入 " + masked + "（内容不回读）"
            readBack != null && readBack.contains(text) -> "已输入 \"" + PhoneRules.quoteText(text, 30) + "\""
            else -> "已写入，回读结果与输入不完全一致（输入法可能改写了内容）"
        }
        val suffix = if (submit) "，并已提交" else ""
        return Result(note + suffix + "\n" + next.formatted.text)
    }

    private fun scroll(context: Context, args: JsonObject): Result {
        val service = requireService()
        val snap = requireSnapshot(args.str("screen"))
        val direction = when (args.str("direction")?.lowercase()) {
            "up" -> PhoneActuator.Direction.UP
            "down" -> PhoneActuator.Direction.DOWN
            "left" -> PhoneActuator.Direction.LEFT
            "right" -> PhoneActuator.Direction.RIGHT
            else -> return Result("direction 只能是 up / down / left / right", true)
        }
        val id = args.int("id")
        val el = if (id != null) {
            snap.formatted.element(id) ?: return Result("这个屏幕里没有编号 $id 的元素", true)
        } else {
            snap.formatted.elements.firstOrNull { it.kind == ElementKind.LIST }
                ?: return Result("这个屏幕里没有可滚动的列表，可以用 scroll 指定 id，或直接点元素", true)
        }
        val node = snap.capture.native(el.ref)
        val actuator = PhoneActuator(service)
        val outcome = try {
            actuator.scroll(node, el.scroll, el.horizontal, el.bounds, snap.capture.screen, direction)
        } finally {
            actuator.close()
        }
        if (!outcome.accepted) return Result("滚动没有生效（也许已经到顶 / 到底）", true)
        sleepForUi()
        val next = publish(context, capture(service, context), false, snap.formatted.keys, emptyList())
        return Result("已" + directionLabel(direction) + "\n" + next.formatted.text)
    }

    private fun key(context: Context, args: JsonObject): Result {
        val service = requireService()
        val name = args.str("key")?.lowercase() ?: return Result("key 需要按键名", true)
        val action = when (name) {
            "back" -> AccessibilityService.GLOBAL_ACTION_BACK
            "home" -> AccessibilityService.GLOBAL_ACTION_HOME
            "recents" -> AccessibilityService.GLOBAL_ACTION_RECENTS
            "notifications" -> AccessibilityService.GLOBAL_ACTION_NOTIFICATIONS
            else -> return Result("key 只能是 back / home / recents / notifications", true)
        }
        val snap = last
        if (snap != null) checkWrite(context, snap, WriteKind.KEY, null, null, false, null)
        val actuator = PhoneActuator(service)
        val ok = try {
            actuator.global(action)
        } finally {
            actuator.close()
        }
        if (!ok) return Result("按键没有生效", true)
        sleepForUi()
        val next = publish(context, capture(service, context), false, null, emptyList())
        return Result("已按 " + name + "\n" + next.formatted.text)
    }

    private fun tapXY(context: Context, args: JsonObject): Result {
        val service = requireService()
        val x = args.int("x") ?: return Result("tap_xy 需要 x", true)
        val y = args.int("y") ?: return Result("tap_xy 需要 y", true)
        val snap = last
        if (snap != null) checkWrite(context, snap, WriteKind.TAP_XY, null, null, false, null)
        val actuator = PhoneActuator(service)
        val ok = try {
            actuator.tap(x, y, false)
        } finally {
            actuator.close()
        }
        if (!ok) return Result("坐标点击没有生效", true)
        sleepForUi()
        val next = publish(context, capture(service, context), false, null, emptyList())
        return Result("已点击坐标 ($x,$y)\n" + next.formatted.text)
    }

    // ---- 应用与意图 ---------------------------------------------------------------------

    private fun apps(context: Context, args: JsonObject): Result {
        val query = args.str("query")?.trim()?.lowercase()
        val pm = context.packageManager
        val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        val list = pm.queryIntentActivities(intent, 0)
            .mapNotNull { info ->
                val pkg = info.activityInfo?.packageName ?: return@mapNotNull null
                val label = info.loadLabel(pm)?.toString() ?: pkg
                label to pkg
            }
            .distinctBy { it.second }
            .sortedBy { it.first.lowercase() }
            .filter { query == null || it.first.lowercase().contains(query) || it.second.lowercase().contains(query) }
        if (list.isEmpty()) return Result("没有匹配的应用（query=" + (query ?: "") + "）")
        val text = buildString {
            append("可打开的应用 ").append(list.size).append(" 个：\n")
            list.take(80).forEach { append("- ").append(it.first).append(" · ").append(it.second).append('\n') }
            if (list.size > 80) append("（只列前 80 个，用 query 缩小范围）")
        }
        return Result(text.trimEnd())
    }

    private fun open(context: Context, args: JsonObject): Result {
        val app = args.str("app")?.trim()?.takeIf { it.isNotEmpty() }
        val url = args.str("url")?.trim()?.takeIf { it.isNotEmpty() }
        if (app == null && url == null) return Result("open 需要 app 或 url（二选一）", true)
        val intent = when {
            url != null -> Intent(Intent.ACTION_VIEW, Uri.parse(url))
            else -> {
                val pkg = resolvePackage(context, app!!) ?: return Result("找不到应用「$app」，可以先用 apps 查包名", true)
                context.packageManager.getLaunchIntentForPackage(pkg)
                    ?: return Result("「$app」没有可启动的界面", true)
            }
        }
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        val pkg = intent.`package` ?: app
        if (pkg != null) {
            val snap = last
            val kind = WriteKind.KEY
            val verdict = gate(context, pkg, kind, null, null, false, null)
            if (verdict is Verdict.Refuse) throw Refused(verdict.message)
        }
        context.startActivity(intent)
        sleepForUi(600)
        val next = publish(context, capture(requireService(), context), false, null, emptyList())
        return Result("已打开 " + (url ?: app) + "\n" + next.formatted.text)
    }

    private fun intent(context: Context, args: JsonObject): Result {
        val kind = args.str("kind") ?: return Result("intent 需要 kind", true)
        val intent = when (kind) {
            "settings" -> {
                val page = args.str("page") ?: "home"
                val action = when (page) {
                    "wifi" -> Settings.ACTION_WIFI_SETTINGS
                    "bluetooth" -> Settings.ACTION_BLUETOOTH_SETTINGS
                    "mobile_network" -> Settings.ACTION_DATA_ROAMING_SETTINGS
                    "airplane" -> Settings.ACTION_AIRPLANE_MODE_SETTINGS
                    "display" -> Settings.ACTION_DISPLAY_SETTINGS
                    "sound" -> Settings.ACTION_SOUND_SETTINGS
                    "battery" -> Settings.ACTION_BATTERY_SAVER_SETTINGS
                    "location" -> Settings.ACTION_LOCATION_SOURCE_SETTINGS
                    "date" -> Settings.ACTION_DATE_SETTINGS
                    "language" -> Settings.ACTION_LOCALE_SETTINGS
                    "storage" -> Settings.ACTION_INTERNAL_STORAGE_SETTINGS
                    "nfc" -> Settings.ACTION_NFC_SETTINGS
                    else -> Settings.ACTION_SETTINGS
                }
                Intent(action)
            }
            "dial" -> Intent(Intent.ACTION_DIAL, Uri.parse("tel:" + (args.str("number") ?: "")))
            "sms_draft" -> Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:" + (args.str("number") ?: ""))).apply {
                putExtra("sms_body", args.str("text") ?: "")
            }
            "share" -> Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_TEXT, args.str("text") ?: "")
            }
            "navigate" -> {
                val destination = args.str("destination")
                    ?: return Result("navigate 需要 destination", true)
                Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0?q=" + Uri.encode(destination)))
            }
            "calendar" -> {
                val begin = args.str("begin") ?: return Result("calendar 需要 begin", true)
                Intent(Intent.ACTION_INSERT).apply {
                    data = android.provider.CalendarContract.Events.CONTENT_URI
                    putExtra(android.provider.CalendarContract.EXTRA_EVENT_BEGIN_TIME, parseMillis(begin))
                    args.str("end")?.let {
                        putExtra(android.provider.CalendarContract.EXTRA_EVENT_END_TIME, parseMillis(it))
                    }
                    putExtra(android.provider.CalendarContract.Events.TITLE, args.str("title") ?: "")
                }
            }
            else -> return Result(
                "intent 的 kind 只能是 settings / dial / sms_draft / share / navigate / calendar",
                true,
            )
        }
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            context.startActivity(intent)
            sleepForUi(500)
            val next = publish(context, capture(requireService(), context), false, null, emptyList())
            Result("已打开 " + kind + "\n" + next.formatted.text)
        } catch (e: Throwable) {
            Result("打不开这个界面：" + (e.message ?: e.toString()) + "。可以让用户自己打开，或改用 phone_handoff。", true)
        }
    }

    /** 接受 2026-10-24T19:00 或 2026-10-24；解析失败给"一小时后"，不让日程直接丢掉。 */
    private fun parseMillis(value: String): Long = runCatching {
        java.time.LocalDateTime.parse(value).atZone(java.time.ZoneId.systemDefault()).toInstant().toEpochMilli()
    }.recoverCatching {
        java.time.LocalDate.parse(value).atStartOfDay(java.time.ZoneId.systemDefault()).toInstant().toEpochMilli()
    }.getOrElse { System.currentTimeMillis() + 3_600_000L }

    private fun handoff(context: Context, args: JsonObject): Result {
        val reason = args.str("reason")?.trim().orEmpty().ifEmpty { "需要你亲自完成这一步" }
        return Result(
            "已把手机交给用户：$reason\n" +
                "用户完成这一步后，会在聊天里回你一句；在收到回复之前不要再操作这个界面。",
        )
    }

    // ---- 安全门 -------------------------------------------------------------------------

    private sealed class Verdict {
        class Allow(val reason: String) : Verdict()
        class Refuse(val message: String) : Verdict()
    }

    /**
     * 判定顺序与 dsh-go SafetyGate.checkWrite 一致：
     * 自己 → deny 名单 → 滚动放行 → 系统页 → 机密输入 → 本任务已豁免 → 需要确认（这里直接放行，
     * 因为调用前 RikkaHub 的工具审批已经问过一次） → 放行。
     */
    private fun gate(
        context: Context,
        pkg: String?,
        kind: WriteKind,
        el: ScreenElement?,
        typed: String?,
        submit: Boolean,
        target: TargetInfo?,
    ): Verdict {
        val p = policies
        val unlocked = p.unlocks
        val own = context.packageName
        if (pkg == own && !unlocked.ownApp) {
            return Verdict.Refuse("这是 RikkaHub 自己的界面，手机操控不操作自己（避免自己点自己的确认按钮）。")
        }
        if (pkg != null && pkg in p.denyPackages) {
            return Verdict.Refuse("「" + appName(context, pkg) + "」在银行 / 支付 / 券商的黑名单里，手机操控既不读也不点它。需要的话请用户自己操作，或让用户到设置里把它移出黑名单。")
        }
        if (kind == WriteKind.SCROLL) return Verdict.Allow("scroll")
        if (PhoneRules.isSystemPackage(pkg) && !unlocked.systemPages) {
            return Verdict.Refuse("这是系统设置 / 权限 / 安装 / 系统界面（「" + appName(context, pkg) + "」），只能看不能操作。请用 handoff 让用户自己完成。")
        }
        val secret = PhoneRules.isSecretTarget(target)
        if (secret && !unlocked.secretFields) {
            return Verdict.Refuse("这是密码 / 验证码 / 支付密码一类的输入框，不代填、也不替用户点。请用 handoff 让用户自己输入。")
        }
        // 首次进入一个 App 的记账：工具审批已经问过，这里只记录，避免重复问同一 App。
        if (pkg != null && pkg !in p.confirmEveryWritePackages) approvedApps.add(pkg)
        return Verdict.Allow("ok")
    }

    private fun checkWrite(
        context: Context,
        snap: Snapshot,
        kind: WriteKind,
        el: ScreenElement?,
        typed: String?,
        submit: Boolean,
        target: TargetInfo?,
    ) {
        val pkg = el?.packageName ?: snap.capture.packageName
        when (val verdict = gate(context, pkg, kind, el, typed, submit, target)) {
            is Verdict.Refuse -> throw Refused(verdict.message)
            is Verdict.Allow -> Unit
        }
    }

    // ---- 捕获与格式化 -------------------------------------------------------------------

    private fun requireService(): AccessibilityService =
        PhoneAccessibilityService.instance ?: throw Refused(
            "无障碍服务没有开启。请让用户到 设置 → 手机操控 → 无障碍服务 里打开 RikkaHub 的手机操控服务，再重试。"
        )

    private fun capture(service: AccessibilityService, context: Context): PhoneCapture {
        val screen = PhoneAccessibilityService.screen
        return PhoneCapturer.capture(service, screen, context.packageName, 800)
    }

    private fun publish(
        context: Context,
        cap: PhoneCapture,
        detail: Boolean,
        previous: Set<String>?,
        notes: List<String>,
    ): Snapshot {
        val id = "s" + (++seq)
        val appLabel = appNameOrNull(context, cap.packageName)
        val formatted = PhoneFormat.format(
            ScreenInput(
                screenId = id,
                appLabel = appLabel,
                packageName = cap.packageName,
                screenWidth = cap.screen.width,
                screenHeight = cap.screen.height,
                keyboardShown = cap.keyboardShown,
                windows = cap.windows,
                detail = detail,
                previousKeys = previous,
                notes = notes,
            )
        )
        val old = last
        val snap = Snapshot(id, cap, formatted, System.currentTimeMillis())
        last = snap
        if (old != null && old.capture !== cap) old.capture.recycle()
        return snap
    }

    private fun requireSnapshot(id: String?): Snapshot {
        val snap = last ?: throw Refused(
            "还没有读过屏幕。先调用 phone_screen 读一次，拿到屏幕号和元素编号。"
        )
        if (id != null && id != snap.id) {
            throw Refused("屏幕号 $id 已经过期（当前是 " + snap.id + "）。先重新 phone_screen，再按新编号操作。")
        }
        return snap
    }

    private fun notesFor(cap: PhoneCapture, service: AccessibilityService): List<String> {
        val notes = mutableListOf<String>()
        val p = policies
        val pkg = cap.packageName
        if (pkg != null && pkg == service.packageName && !p.unlocks.ownApp) {
            notes += "这是 RikkaHub 自己的界面，不读取内容也不操作。"
        }
        if (pkg != null && pkg in p.denyPackages) {
            notes += "「" + appNameOrNull(service, pkg) + "」在银行 / 支付黑名单里，不读取内容。"
        }
        if (cap.hiddenWindowTitle != null) {
            notes += "当前窗口是安全窗口（禁止截屏 / 读取，常见于支付、银行、密码页），不读取内容。需要用户操作请用 handoff。"
        }
        if (PhoneRules.isSystemPackage(pkg) && !p.unlocks.systemPages) {
            notes += "这是系统页面，只能看不能操作；需要用户自己完成请用 handoff。"
        }
        return notes
    }

    // ---- 小工具 -------------------------------------------------------------------------

    private fun subTexts(cap: PhoneCapture, el: ScreenElement): List<String> {
        val out = mutableListOf<String>()
        for (e in PhoneFormat.index(cap.windows)) {
            if (e.kind == ElementKind.LIST) continue
            if (e.fullText.isBlank()) continue
            if (e.bounds.top < el.bounds.top || e.bounds.bottom > el.bounds.bottom) continue
            out += e.fullText
        }
        return out.distinct()
    }

    private fun sameItems(a: PhoneCapture, b: PhoneCapture, el: ScreenElement): Boolean {
        val before = subTexts(a, el)
        val after = subTexts(b, el)
        return before.isNotEmpty() && before == after
    }

    private fun equivalentList(cap: PhoneCapture, el: ScreenElement): ScreenElement? =
        PhoneFormat.index(cap.windows).firstOrNull { it.kind == ElementKind.LIST && it.role == "列表" } ?: el

    private fun describeElement(el: ScreenElement): String =
        "[" + el.id + "]" + (if (el.role.isNotBlank()) " " + el.role else "") +
            (if (el.label.isNotBlank()) " " + PhoneRules.quoteText(el.label, 30) else "")

    private fun directionLabel(d: PhoneActuator.Direction) = when (d) {
        PhoneActuator.Direction.UP -> "向上滚"
        PhoneActuator.Direction.DOWN -> "向下滚"
        PhoneActuator.Direction.LEFT -> "向左滚"
        PhoneActuator.Direction.RIGHT -> "向右滚"
    }

    private fun resolvePackage(context: Context, nameOrPkg: String): String? {
        val pm = context.packageManager
        val direct = runCatching { pm.getPackageInfo(nameOrPkg, 0) }.getOrNull()
        if (direct != null) return nameOrPkg
        val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        return pm.queryIntentActivities(intent, 0)
            .firstOrNull { info ->
                val label = info.loadLabel(pm)?.toString() ?: ""
                label.equals(nameOrPkg, ignoreCase = true) || label.contains(nameOrPkg, ignoreCase = true)
            }
            ?.activityInfo?.packageName
    }

    private fun appName(context: Context, pkg: String?): String =
        appNameOrNull(context, pkg) ?: (pkg ?: "当前应用")

    private fun appNameOrNull(context: Context, pkg: String?): String? {
        if (pkg == null) return null
        return runCatching {
            val pm = context.packageManager
            pm.getApplicationLabel(pm.getApplicationInfo(pkg, 0)).toString()
        }.getOrNull()
    }

    private fun sleepForUi(ms: Long = 350) {
        try {
            Thread.sleep(ms)
        } catch (_: InterruptedException) {
            Thread.currentThread().interrupt()
        }
    }

    private fun JsonObject.str(key: String): String? =
        (this[key] as? JsonPrimitive)?.contentOrNull?.takeIf { it.isNotEmpty() }

    private fun JsonObject.int(key: String): Int? = (this[key] as? JsonPrimitive)?.intOrNull

    private fun JsonObject.bool(key: String): Boolean = (this[key] as? JsonPrimitive)?.booleanOrNull ?: false

    const val PHONE_SCREEN = "phone_screen"
    const val PHONE_COLLECT = "phone_collect"
    const val PHONE_TAP = "phone_tap"
    const val PHONE_TYPE = "phone_type"
    const val PHONE_SCROLL = "phone_scroll"
    const val PHONE_KEY = "phone_key"
    const val PHONE_TAP_XY = "phone_tap_xy"
    const val PHONE_OPEN = "phone_open"
    const val PHONE_APPS = "phone_apps"
    const val PHONE_HANDOFF = "phone_handoff"
    const val PHONE_INTENT = "phone_intent"
}

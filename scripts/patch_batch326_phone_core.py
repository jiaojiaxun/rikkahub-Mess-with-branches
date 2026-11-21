#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhPhone326 -- 手机操控（路径 A）第一批：纯 Kotlin 数据层与安全规则。

来源：dsh-go (ccch1mneyyy/dsh-go, AGPL-3.0)
  app/android/app/src/main/kotlin/io/github/ccch1mneyyy/dsh_app/phone/a11y/UiTree.kt
  app/android/app/src/main/kotlin/io/github/ccch1mneyyy/dsh_app/phone/SensitiveWords.kt
  app/android/app/src/main/kotlin/io/github/ccch1mneyyy/dsh_app/phone/a11y/ScreenMask.kt
  app/android/app/src/main/kotlin/io/github/ccch1mneyyy/dsh_app/phone/SafetyGate.kt
  app/android/app/src/main/kotlin/io/github/ccch1mneyyy/dsh_app/phone/a11y/ProtectedPages.kt

本批只新增文件，不改任何现有文件；四个新文件之间零外部依赖（无 Android 类型），
所以即使后续批次失败，这一批也一定编译得过。

规则：
  * 幂等 marker：rhPhone326（每个文件都带）
  * 每个文件写盘后读回校验 marker 与括号平衡
  * 任何一步失败都 ::error 打印现场，不静默
"""
import os
import sys

MARK = "rhPhone326"
DIAG_NAME = "ci_diag_batch326_phone_core.txt"
DIAG = []


def log(msg):
    line = "[batch326] " + str(msg)
    print(line)
    DIAG.append(line)


def fail(msg):
    line = "FAIL " + str(msg)
    print("::error title=phone326::" + line)
    DIAG.append(line)
    write_diag()
    sys.exit(0)


def write_diag():
    try:
        with open(DIAG_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(DIAG) + "\n")
    except Exception as exc:  # noqa: BLE001
        print("::warning title=phone326::diag write failed: " + str(exc))


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
    if len(back) != len(content):
        fail("read-back length mismatch: " + rel + " " + str(len(back)) + "/" + str(len(content)))
    pairs = [("{", "}"), ("(", ")"), ("[", "]")]
    for op, cl in pairs:
        if back.count(op) != back.count(cl):
            fail("unbalanced " + op + cl + " in " + rel + ": " + str(back.count(op)) + "/" + str(back.count(cl)))
    log("wrote " + rel + " (" + str(len(content)) + " chars)")


UI_TREE = r'''package me.rerere.rikkahub.phone

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
'''

SENSITIVE = r'''package me.rerere.rikkahub.phone

/**
 * rhPhone326 -- 安全规则背后的词表，逐条对应 dsh-go 的 SensitiveWords.kt。
 *
 * 词表只放一处：安全门（要确认的动作）与屏幕格式化（行首的 ⚠）都读它，
 * 保证"标了 ⚠ 的"和"会被拦下确认的"永远是同一批。
 * 纯 Kotlin，无 Android 类型。
 */
object SensitiveWords {
    /** 敏感动作：label 或 view-id 命中其一就要确认。 */
    val confirm: List<String> = listOf(
        "发送", "发布", "提交", "支付", "付款", "购买", "下单", "转账", "红包",
        "删除", "清空", "卸载", "注销", "退出登录", "授权", "同意", "拨打",
    )

    /** 同样语义的 view-id 词（btn_send、payButton），按整词匹配。 */
    val confirmIdWords: Set<String> = setOf(
        "send", "publish", "submit", "pay", "payment", "checkout", "purchase", "buy",
        "transfer", "redpacket", "hongbao", "delete", "uninstall", "logout", "signout",
        "unregister", "authorize", "agree", "dial",
    )

    /** 英文控件文字按词边界匹配：buy 不能命中 buyer。 */
    private val confirmEnglish = (confirmIdWords + setOf(
        "post", "clear", "call", "log out", "sign out", "place order", "red packet",
    )).map { word -> word to wholeWords(word) }

    private fun wholeWords(word: String): Regex = Regex(
        "(?<![\\p{L}\\p{N}_])" + word.split(' ').joinToString("\\s+") { Regex.escape(it) } +
            "(?![\\p{L}\\p{N}_])",
        RegexOption.IGNORE_CASE,
    )

    private val otpHint = wholeWords("otp")
    private val oneTimeHint = wholeWords("one-time")

    /** 机密输入：即使允许输入，内容也永远遮罩。 */
    val secret: List<String> = listOf(
        "支付密码", "密码", "验证码", "校验码", "动态码", "安全码", "cvv", "cvc",
        "password", "passcode", "verification code",
    )

    /** 机密输入框的 view-id 词（et_pwd、smsCode）。 */
    val secretIdWords: Set<String> = setOf(
        "password", "passwd", "pwd", "passcode", "otp", "cvv", "cvc", "smscode", "verifycode", "authcode",
    )

    /**
     * 超过这个长度的 label 属于内容（一条消息、一张卡片），不是控件：
     * 只有词出现在开头或结尾才算数。避免每条含"发送"的消息都被标 ⚠。
     */
    const val SHORT_LABEL = 24

    /**
     * 让这个目标变成敏感目标的词，没有则 null。
     * [label] 是渲染出来的文字（text → contentDescription → hint），[viewId] 是资源 id。
     */
    fun confirmHit(label: String?, viewId: String?): String? {
        val text = label?.trim().orEmpty()
        if (text.isNotEmpty()) {
            for (word in confirm) {
                if (!text.contains(word)) continue
                if (text.length <= SHORT_LABEL || text.startsWith(word) || text.endsWith(word)) return word
            }
            for ((word, pattern) in confirmEnglish) {
                for (match in pattern.findAll(text)) {
                    if (text.length <= SHORT_LABEL || match.range.first == 0 || match.range.last == text.lastIndex) {
                        return word
                    }
                }
            }
        }
        return idWords(viewId).firstOrNull { it in confirmIdWords }
    }

    /** 让这个输入框成为机密框的词，没有则 null。 */
    fun secretHit(hint: String?, description: String?, viewId: String?): String? {
        for (value in listOf(hint, description)) {
            val text = value?.lowercase() ?: continue
            secret.firstOrNull { text.contains(it) }?.let { return it }
            if (otpHint.containsMatchIn(text)) return "otp"
            if (oneTimeHint.containsMatchIn(text)) return "one-time"
        }
        return idWords(viewId).firstOrNull { it in secretIdWords }
    }

    /**
     * com.tencent.mm:id/btn_sendMsg → [btn, send, msg, btnsend, sendmsg]：
     * id 尾部按分隔符与驼峰切开、小写，再补上相邻两词拼接（verify_code 也给出 verifycode）。
     */
    fun idWords(viewId: String?): List<String> {
        if (viewId.isNullOrBlank()) return emptyList()
        val tail = viewId.substringAfterLast(":id/").substringAfterLast('/')
        val words = mutableListOf<String>()
        val current = StringBuilder()
        fun flush() {
            if (current.isNotEmpty()) {
                words.add(current.toString().lowercase())
                current.setLength(0)
            }
        }
        for ((index, char) in tail.withIndex()) {
            when {
                !char.isLetterOrDigit() -> flush()
                char.isUpperCase() && index > 0 && tail[index - 1].isLowerCase() -> {
                    flush()
                    current.append(char)
                }
                else -> current.append(char)
            }
        }
        flush()
        return words + words.zipWithNext { a, b -> a + b }
    }
}
'''

MASK = r'''package me.rerere.rikkahub.phone

/**
 * rhPhone326 -- 屏幕文字里的银行卡号 / 身份证号在离开手机前先遮罩，
 * 例如 «银行卡 ****1234»。逐条对应 dsh-go 的 a11y/ScreenMask.kt。
 *
 * 需要完整号码的任务，正是我们拒绝的任务。纯 Kotlin，可在 JVM 单测里跑。
 */
object ScreenMask {
    /** 18 位居民身份证：地区 + 生日 + 顺序 + 校验位。 */
    private val idNumber = Regex(
        "(?<![0-9A-Za-z])[1-9][0-9]{5}(?:19|20)[0-9]{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12][0-9]|3[01])[0-9]{3}[0-9Xx](?![0-9A-Za-z])"
    )

    /** 15-19 位数字，允许单个空格或连字符分组（6222 0212 3456 7890）。 */
    private val cardNumber = Regex("(?<![0-9A-Za-z])[0-9](?:[ -]?[0-9]){14,18}(?![0-9A-Za-z])")

    /** 这些词后面的数字串是订单 / 运单 / 流水号，不是银行卡。 */
    private val notCardContext = listOf(
        "订单", "单号", "运单", "物流", "快递", "编号", "流水", "交易号", "条码", "序列号", "No.", "NO.",
    )

    fun mask(text: String): String {
        if (text.length < 15 || text.count { it.isDigit() } < 15) return text
        val ids = idNumber.replace(text) { m ->
            if (idChecksumOk(m.value)) "«身份证 ****${m.value.takeLast(4).uppercase()}»" else m.value
        }
        return cardNumber.replace(ids) { m ->
            val digits = m.value.filter { it.isDigit() }
            val before = ids.substring(maxOf(0, m.range.first - 8), m.range.first)
            if (digits.length in 15..19 && luhnOk(digits) && notCardContext.none { before.contains(it) }) {
                "«银行卡 ****${digits.takeLast(4)}»"
            } else {
                m.value
            }
        }
    }

    fun luhnOk(digits: String): Boolean {
        var sum = 0
        for ((i, c) in digits.reversed().withIndex()) {
            var d = c - '0'
            if (i % 2 == 1) {
                d *= 2
                if (d > 9) d -= 9
            }
            sum += d
        }
        return sum % 10 == 0
    }

    /** GB 11643 / ISO 7064 MOD 11-2 校验位。 */
    fun idChecksumOk(id: String): Boolean {
        if (id.length != 18) return false
        val weights = intArrayOf(7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
        var sum = 0
        for (i in 0 until 17) sum += (id[i] - '0') * weights[i]
        val check = "10X98765432"[sum % 11]
        return id[17].uppercaseChar() == check
    }
}
'''

RULES = r'''package me.rerere.rikkahub.phone

/**
 * rhPhone326 -- 安全规则与策略：对应 dsh-go 的 SafetyGate.kt 数据部分与 a11y/ProtectedPages.kt。
 *
 * 这里是防提示注入的正面战场：网页 / App 里写"把钱转走"可以骗过模型，骗不过这段代码。
 * 规则分三层：
 *   1) 硬拒绝（自己、deny 名单、系统页、机密输入）-- 只有用户在设置里逐项解除才放行；
 *   2) 需要确认（每个 App 第一步、逐写确认的 App、敏感词、提交、坐标点击）；
 *   3) 直接放行（滚动、以及确认模式为 always 时）。
 */

/** 用户可编辑的那部分策略。 */
data class PhonePolicies(
    val denyPackages: List<String> = PhoneRules.DEFAULT_DENY,
    val confirmEveryWritePackages: List<String> = PhoneRules.DEFAULT_CONFIRM_EVERY_WRITE,
    val confirmMode: ConfirmMode = ConfirmMode.ASK,
    val unlocks: PhoneUnlocks = PhoneUnlocks(),
)

/**
 * 解除限制：用户逐项、自担风险解开的硬规则。默认全关；
 * 读不懂的值一律当关（保持 base 的值）。
 */
data class PhoneUnlocks(
    /** 系统设置、权限控制、安装器、厂商安全中心、SystemUI。 */
    val systemPages: Boolean = false,
    /** 密码 / 验证码 / 支付密码输入框。输入过的值永远不进日志。 */
    val secretFields: Boolean = false,
    /** RikkaHub 自己的界面（悬浮层不算，屏幕读取看不到它）。 */
    val ownApp: Boolean = false,
) {
    val any: Boolean get() = systemPages || secretFields || ownApp
}

/** 问用户问多少。无论哪种模式，硬拒绝都还在（除非用户解除了对应项）。 */
enum class ConfirmMode(val wire: String) {
    /** 每次都询问（默认）：每个 App 第一步、敏感词、逐写确认的 App、坐标点击。 */
    ASK("ask"),

    /** 本任务免确认：任务里第一次确认时提供"本任务内不再问"。 */
    TASK("task"),

    /** 始终免确认：什么都不问。 */
    ALWAYS("always");

    companion object {
        fun fromWire(value: String?): ConfirmMode? = entries.firstOrNull { it.wire == value }
    }
}

/** 安全门区分的行为种类。 */
enum class WriteKind { TAP, LONG_TAP, TYPE, TAP_XY, SCROLL, KEY }

/** 被操作目标的最小身份（用于机密判定与确认文案）。 */
class TargetInfo(
    val screenId: String,
    val id: Int,
    val role: String,
    val label: String,
    val packageName: String?,
    val appLabel: String?,
    val password: Boolean,
    val isSecretField: Boolean,
    val editable: Boolean,
    val viewId: String?,
)

object PhoneRules {
    /** 输入过的机密在日志、状态行、确认卡里显示成这个。 */
    const val MASK = "••••"

    /**
     * 系统页：能读、绝不能动。无障碍、设备管理、开发者选项都在设置里，
     * 权限控制、安装器、厂商安全中心、SystemUI（快捷设置、通知栏里还有我们自己的确认按钮、锁屏）。
     * 契约只给包名不给页面，所以整个 App 都算。
     */
    val SYSTEM_PACKAGES = setOf(
        "com.android.settings",
        "com.android.systemui",
        "com.android.permissioncontroller", "com.google.android.permissioncontroller",
        "com.android.packageinstaller", "com.google.android.packageinstaller", "com.miui.packageinstaller",
        "com.android.settings.intelligence",
        "com.miui.securitycenter", "com.miui.securityadd", "com.miui.securitycore",
        "com.coloros.safecenter", "com.oplus.safecenter", "com.coloros.securitypermission", "com.oplus.securitypermission",
        "com.vivo.permissionmanager", "com.iqoo.secure",
        "com.huawei.systemmanager", "com.hihonor.systemmanager", "com.huawei.security", "com.hihonor.security",
        "com.samsung.android.lool", "com.samsung.android.sm", "com.samsung.accessibility",
        "com.google.android.marvin.talkback",
        "com.android.keychain", "com.android.vpndialogs", "com.android.certinstaller",
    )

    fun isSystemPackage(pkg: String?): Boolean = pkg != null && pkg in SYSTEM_PACKAGES

    /** 银行、券商、支付：默认既不读也不写。猜错的包名只是永不命中。 */
    val DEFAULT_DENY = listOf(
        "com.eg.android.AlipayGphone", "com.unionpay", "com.chinatelecom.bestpayclient", "com.jd.jrapp",
        "cn.gov.pbc.dcep", "com.paypal.android.p2pmobile", "com.mybank.android.phone", "com.webank.wemoney",
        "com.icbc", "com.chinamworld.main", "com.android.bankabc", "com.chinamworld.bocmbci", "com.bankcomm.Bankcomm",
        "cmb.pb", "com.cmbchina.ccd.pluto.cmbActivity", "com.yitong.mbank.psbc", "cn.com.spdb.mobilebank.per",
        "cn.com.cmbc.newmbank", "com.ecitic.bank.mobile", "com.cebbank.mobile.cemb", "com.pingan.paces.ccms",
        "com.cgbchina.xpt", "com.bankofbeijing.mobilebanking",
        "com.hexin.plat.android", "com.eastmoney.android.berlin", "com.lphtsccft", "com.xueqiu.android",
        "cn.futu.trader", "com.tigerbrokers.stock",
    )

    /** 微信：能读，每次写都要确认。 */
    val DEFAULT_CONFIRM_EVERY_WRITE = listOf("com.tencent.mm")

    fun quoteText(text: String, max: Int = 60): String {
        val t = text.replace('\n', ' ').trim()
        return if (t.length <= max) t else t.take(max) + "…"
    }

    fun isSecret(label: String?, viewId: String?): Boolean = SensitiveWords.secretHit(label, null, viewId) != null

    /** 密码 / 验证码输入框：锁着时拒绝，解锁后输入值在所有地方遮罩。 */
    fun isSecretTarget(t: TargetInfo?): Boolean =
        t != null && (t.password || t.isSecretField || (t.editable && isSecret(t.label, t.viewId)))
}

/**
 * 系统页永远交还给用户：无障碍、设备管理、开发者选项、安装 / 卸载、权限页，
 * 这样代理永远无法给自己授权。驱动能读这些页，但拒绝对它们动手。
 */
object ProtectedPages {
    /** 只显示安装 / 权限 / 安全界面的整包。 */
    val packages: Set<String> = setOf(
        "com.android.packageinstaller", "com.google.android.packageinstaller", "com.miui.packageinstaller",
        "com.samsung.android.packageinstaller", "com.oplus.packageinstaller", "com.coloros.packageinstaller",
        "com.android.permissioncontroller", "com.google.android.permissioncontroller",
        "com.lbe.security.miui", "com.miui.securitycenter", "com.miui.securityadd",
        "com.coloros.securitypermission", "com.oplus.securitypermission", "com.coloros.safecenter", "com.oplus.safecenter",
        "com.iqoo.secure", "com.vivo.permissionmanager", "com.vivo.safecenter",
        "com.huawei.systemmanager", "com.hihonor.systemmanager", "com.huawei.securitymgr",
        "com.android.settings.intelligence",
    )

    /** 设置类 App：只有标题命中 [titleWords] 的页面才受保护。 */
    val settingsPackages: Set<String> = setOf(
        "com.android.settings", "com.miui.settings", "com.coloros.settings", "com.oplus.settings",
        "com.vivo.settings", "com.huawei.settings", "com.hihonor.settings", "com.samsung.android.settings",
    )

    val titleWords: List<String> = listOf(
        "无障碍", "辅助功能", "开发者选项", "开发人员选项", "设备管理", "权限", "安装未知应用", "未知来源",
        "安装外部来源", "特殊应用权限", "锁屏", "屏幕锁定", "密码", "指纹", "人脸", "生物识别", "安全", "隐私",
        "Accessibility", "Developer options", "Device admin", "Permission", "Install unknown", "Security", "Privacy",
    )

    /** [titles]：窗口标题与页面自报的标题文字。 */
    fun isProtected(packageName: String?, titles: List<String>): Boolean {
        if (packageName == null) return false
        if (packageName in packages) return true
        if (packageName !in settingsPackages) return false
        return titles.any { t -> titleWords.any { t.contains(it, ignoreCase = true) } }
    }

    /**
     * 页面自报名字的位置：屏幕顶部 30% 内的标题，以及顶部 20% 内、不在可滚动容器里的文字
     * （列表被滚到工具栏下面的行是内容，不是标题）。
     */
    fun titleTexts(root: UiNode?, screenHeight: Int, limit: Int = 8): List<String> {
        val out = mutableListOf<String>()
        fun walk(n: UiNode, inScroll: Boolean) {
            if (out.size >= limit) return
            val text = (n.text ?: n.desc)?.takeIf { it.isNotBlank() && !n.editable }
            if (text != null && (
                    (n.heading && n.bounds.centerY < screenHeight * 0.3) ||
                        (!inScroll && n.bounds.centerY < screenHeight * 0.2)
                    )
            ) {
                out += text
            }
            n.children.forEach { walk(it, inScroll || n.scrollable) }
        }
        root?.let { walk(it, false) }
        return out
    }
}
'''

FILES = [
    (PKG_DIR + "/PhoneUiTree.kt", UI_TREE),
    (PKG_DIR + "/PhoneSensitive.kt", SENSITIVE),
    (PKG_DIR + "/PhoneMask.kt", MASK),
    (PKG_DIR + "/PhoneRules.kt", RULES),
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
package me.rerere.rikkahub.phone

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

package me.rerere.rikkahub.phone

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

package me.rerere.rikkahub.phone

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

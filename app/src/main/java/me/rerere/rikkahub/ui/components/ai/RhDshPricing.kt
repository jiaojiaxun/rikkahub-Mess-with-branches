package me.rerere.rikkahub.ui.components.ai

// rhPricing346 - 本地价格表，用于在没有余额查询入口的供应商上估算消费。
// 单位：人民币元 / 百万 token。价格为 2026-11-08 检索到的公开价，可能随官方调整，
// 修改此文件即可更新；Gemini 按 7.2 汇率折算，DeepSeek 区分峰谷时段。

import kotlinx.datetime.DayOfWeek
import kotlinx.datetime.LocalDateTime

data class RhDshPrice(
    val input: Double,
    val cachedInput: Double,
    val output: Double,
)

data class RhDshPriceEntry(
    val label: String,
    val day: RhDshPrice,
    val night: RhDshPrice? = null,
    val note: String = "",
    val keys: List<String> = emptyList(),
)

object RhDshPricing {

    private val deepSeekV41Day = RhDshPrice(input = 2.0, cachedInput = 0.04, output = 8.0)
    private val deepSeekV41Night = RhDshPrice(input = 1.0, cachedInput = 0.02, output = 4.0)

    val entries: List<RhDshPriceEntry> = listOf(
        RhDshPriceEntry(
            label = "DeepSeek V4.1 Flash",
            day = deepSeekV41Day,
            night = deepSeekV41Night,
            note = "峰时工作日 9-12 / 14-18，其余半价",
            keys = listOf("deepseek-v4.1", "deepseek-v4-1", "v4.1-flash", "deepseek-flash", "v4.1"),
        ),
        RhDshPriceEntry(
            label = "DeepSeek V3.2",
            day = RhDshPrice(input = 1.95, cachedInput = 0.20, output = 7.90),
            note = "缓存命中价为估算",
            keys = listOf("deepseek-v3.2", "deepseek-v3-2", "deepseek-chat", "deepseek-reasoner", "v3.2"),
        ),
        RhDshPriceEntry(
            label = "Kimi K3.1 Pro",
            day = RhDshPrice(input = 13.0, cachedInput = 1.3, output = 68.0),
            keys = listOf("kimi-k3.1", "kimi-k3-1", "k3.1-pro", "k3.1"),
        ),
        RhDshPriceEntry(
            label = "Kimi K3",
            day = RhDshPrice(input = 20.0, cachedInput = 2.0, output = 100.0),
            keys = listOf("kimi-k3", "kimi-k2.7", "kimi"),
        ),
        RhDshPriceEntry(
            label = "GLM-5.3 / 5.2",
            day = RhDshPrice(input = 8.0, cachedInput = 2.0, output = 28.0),
            keys = listOf("glm-5.3", "glm-5-3", "glm-5.2", "glm-5-2", "glm-5"),
        ),
        RhDshPriceEntry(
            label = "Gemini 3.1 Pro",
            day = RhDshPrice(input = 14.4, cachedInput = 1.44, output = 86.4),
            note = "≤200K 上下文，汇率 7.2",
            keys = listOf("gemini-3.1-pro", "gemini-3-1-pro", "gemini-3.1"),
        ),
        RhDshPriceEntry(
            label = "Gemini 2.5 Pro",
            day = RhDshPrice(input = 9.0, cachedInput = 0.9, output = 72.0),
            note = "≤200K 上下文，汇率 7.2",
            keys = listOf("gemini-2.5-pro", "gemini-2-5-pro", "gemini-2.5"),
        ),
    )

    /** 最长 key 命中优先，避免 "kimi-k3" 抢先匹配 "kimi-k3.1"。 */
    fun find(vararg names: String?): RhDshPriceEntry? {
        val haystack = names.filterNotNull().joinToString(" ").lowercase()
        if (haystack.isBlank()) return null
        var best: RhDshPriceEntry? = null
        var bestLen = 0
        entries.forEach { entry ->
            entry.keys.forEach { key ->
                if (haystack.contains(key) && key.length > bestLen) {
                    best = entry
                    bestLen = key.length
                }
            }
        }
        return best
    }

    /** 工作日 9:00-11:59 与 14:00-17:59 为峰时，其余按谷价。 */
    fun isPeak(at: LocalDateTime?): Boolean {
        val time = at ?: return false // rhPricing348: 无消息时按谷价，且不含 Clock 依赖
        val weekday = time.dayOfWeek
        if (weekday == DayOfWeek.SATURDAY || weekday == DayOfWeek.SUNDAY) return false
        val hour = time.hour
        return hour in 9..11 || hour in 14..17
    }

    fun priceFor(entry: RhDshPriceEntry, at: LocalDateTime?): RhDshPrice {
        val night = entry.night
        return if (night != null && !isPeak(at)) night else entry.day
    }

    /**
     * 估算消费（元）。promptTokens 含缓存命中与未命中两部分，
     * 所以未命中 = prompt - cached。
     */
    fun estimate(
        entry: RhDshPriceEntry,
        promptTokens: Int,
        cachedTokens: Int,
        completionTokens: Int,
        at: LocalDateTime?,
    ): Double {
        val price = priceFor(entry, at)
        val cached = cachedTokens.coerceIn(0, promptTokens.coerceAtLeast(0))
        val uncached = (promptTokens - cached).coerceAtLeast(0)
        val million = 1_000_000.0
        return uncached / million * price.input +
            cached / million * price.cachedInput +
            completionTokens / million * price.output
    }

    fun formatCny(value: Double): String {
        if (value <= 0.0) return "¥0"
        if (value < 0.0001) return "<¥0.0001"
        if (value < 1.0) {
            val v = (value * 10000).toLong() / 10000.0
            return "¥" + v.toString()
        }
        val rounded = (value * 100).toLong() / 100.0
        return "¥" + rounded.toString()
    }
}

"""batch346 — 余额板块：官方查不到余额时，用本地价格表估算消费。

背景：多数中转站/供应商没有余额查询入口，ProviderBalanceText 只认 OpenAI 类型，
所以卡片常年空白。用户要求用「输入 / 缓存输入 / 输出」三档单价本地算账。

价格（2026-11-08 检索，已换算为 CNY / 百万 token）：
  DeepSeek V4.1 Flash  峰 ¥2.00 / ¥0.04 / ¥8.00  谷 ¥1.00 / ¥0.02 / ¥4.00
  DeepSeek V3.2        ¥1.95 / ¥0.20(估) / ¥7.90
  Kimi K3              ¥20   / ¥2    / ¥100
  Kimi K3.1 Pro        ¥13   / ¥1.3  / ¥68
  GLM-5.3 / GLM-5.2    ¥8    / ¥2    / ¥28
  Gemini 3.1 Pro(≤200K) ¥14.4 / ¥1.44 / ¥86.4   ($2/$0.2/$12 × 7.2)
  Gemini 2.5 Pro(≤200K) ¥9    / ¥0.9  / ¥72     ($1.25/$0.125/$10 × 7.2)

配套改动：
  1) UIMessage 增加 totalCachedTokens（342 只累计了 prompt/completion）
  2) StreamChunkHandler 三条路径都累加 cached
  3) 新文件 RhDshPricing.kt：价格表 + 最长子串匹配 + 峰谷判断 + 算费
  4) RhDshUsage 增加 costCny/priceLabel；computeUsage 接收 modelIdentifier
  5) 余额卡优先显示估算消费，官方余额仍作为补充
"""

import os

ROOT = os.getcwd()
MSG = os.path.join(ROOT, "ai/src/main/java/me/rerere/ai/ui/Message.kt")
HANDLER = os.path.join(ROOT, "ai/src/main/java/me/rerere/ai/ui/StreamChunkHandler.kt")
CHROME = os.path.join(
    ROOT, "app/src/main/java/me/rerere/rikkahub/ui/components/ai/RhDshChrome.kt"
)
PRICING = os.path.join(
    ROOT, "app/src/main/java/me/rerere/rikkahub/ui/components/ai/RhDshPricing.kt"
)
DIAG = os.path.join(ROOT, "ci_diag_batch346_pricing.txt")

log = []


def note(m):
    print(m)
    log.append(str(m))


def bal(t):
    return (t.count('{') - t.count('}'), t.count('(') - t.count(')'))


def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


PRICING_SRC = r'''package me.rerere.rikkahub.ui.components.ai

// rhPricing346 - 本地价格表，用于在没有余额查询入口的供应商上估算消费。
// 单位：人民币元 / 百万 token。价格为 2026-11-08 检索到的公开价，可能随官方调整，
// 修改此文件即可更新；Gemini 按 7.2 汇率折算，DeepSeek 区分峰谷时段。

import kotlinx.datetime.DayOfWeek
import kotlinx.datetime.LocalDateTime
import kotlinx.datetime.TimeZone
import kotlinx.datetime.toLocalDateTime
import kotlin.time.Clock

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
        val time = at ?: Clock.System.now().toLocalDateTime(TimeZone.currentSystemDefault())
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
            val cents = (value * 10000).toLong() / 100.0
            return "¥" + cents.toString()
        }
        val rounded = (value * 100).toLong() / 100.0
        return "¥" + rounded.toString()
    }
}
'''


def patch_message():
    src = read(MSG)
    before = bal(src)
    old = "    val totalCompletionTokens: Int = 0\n) {"
    new = "    val totalCompletionTokens: Int = 0,\n    val totalCachedTokens: Int = 0 // rhUsageTotal346\n) {"
    count = src.count(old)
    note("message: cached field anchor count=" + str(count))
    if count != 1:
        raise ValueError("anchor count=" + str(count))
    src = src.replace(old, new)
    if bal(src) != before:
        raise ValueError("balance drift")
    write(MSG, src)
    note("message: totalCachedTokens added")


def patch_handler():
    src = read(HANDLER)
    before = bal(src)

    finish_old = "                totalCompletionTokens = totalCompletionTokens + (streamUsage?.completionTokens ?: 0),"
    finish_new = (
        finish_old
        + "\n                totalCachedTokens = totalCachedTokens + (streamUsage?.cachedTokens ?: 0), // rhUsageTotal346"
    )
    if src.count(finish_old) != 1:
        raise ValueError("finish cached anchor count=" + str(src.count(finish_old)))
    src = src.replace(finish_old, finish_new)

    step_old = "            totalCompletionTokens = last().totalCompletionTokens + (result.usage?.completionTokens ?: 0),"
    step_new = (
        step_old
        + "\n            totalCachedTokens = last().totalCachedTokens + (result.usage?.cachedTokens ?: 0), // rhUsageTotal346"
    )
    if src.count(step_old) != 1:
        raise ValueError("non-stream cached anchor count=" + str(src.count(step_old)))
    src = src.replace(step_old, step_new)

    first_old = "            totalCompletionTokens = result.usage?.completionTokens ?: 0,"
    first_new = (
        first_old
        + "\n            totalCachedTokens = result.usage?.cachedTokens ?: 0, // rhUsageTotal346"
    )
    if src.count(first_old) != 1:
        raise ValueError("first-step cached anchor count=" + str(src.count(first_old)))
    src = src.replace(first_old, first_new)

    if bal(src) != before:
        raise ValueError("handler balance drift")
    write(HANDLER, src)
    note("handler: cached accrual in all three paths")


def patch_chrome():
    src = read(CHROME)
    before = bal(src)

    # 1) data class 加 costCny / priceLabel
    a1 = "    val outputTps: Float? = null, // rhTps345\n) {"
    b1 = (
        "    val outputTps: Float? = null, // rhTps345\n"
        "    val costCny: Double? = null, // rhPricing346\n"
        "    val priceLabel: String? = null,\n"
        "    val pricePeak: Boolean? = null,\n"
        ") {"
    )
    if src.count(a1) != 1:
        raise ValueError("usage dataclass anchor count=" + str(src.count(a1)))
    src = src.replace(a1, b1)

    # 2) rememberRhDshUsage 传 modelIdentifier
    a2 = "    return remember(messages, limit) { rhDshComputeUsage(messages, limit) }"
    b2 = "    return remember(messages, limit, modelIdentifier) { rhDshComputeUsage(messages, limit, modelIdentifier) } // rhPricing346"
    if src.count(a2) != 1:
        raise ValueError("remember anchor count=" + str(src.count(a2)))
    src = src.replace(a2, b2)

    # 3) computeUsage 签名 + 计算
    a3 = "private fun rhDshComputeUsage(messages: List<UIMessage>, limit: Int?): RhDshUsage {"
    b3 = "private fun rhDshComputeUsage(messages: List<UIMessage>, limit: Int?, modelIdentifier: String?): RhDshUsage { // rhPricing346"
    if src.count(a3) != 1:
        raise ValueError("compute signature anchor count=" + str(src.count(a3)))
    src = src.replace(a3, b3)

    # 变量：cached 累计已有；加 lastCached / lastAt / lastModelLabel
    a4 = "    var lastTps: Float? = null // rhTps345\n"
    b4 = (
        a4
        + "    var lastCached = 0\n"
        + "    var lastAt: kotlinx.datetime.LocalDateTime? = null\n"
        + "    var lastModelName: String? = null\n"
    )
    if src.count(a4) != 1:
        raise ValueError("var anchor count=" + str(src.count(a4)))
    src = src.replace(a4, b4)

    # 循环内：累计 cached 与记录时间/模型名
    a5 = (
        "            cached += usage.cachedTokens\n"
        "            if (usage.promptTokens > 0) lastPrompt = usage.promptTokens\n"
        "        }"
    )
    b5 = (
        "            cached += usage.cachedTokens\n"
        "            lastCached += if (message.totalCachedTokens > 0) message.totalCachedTokens else usage.cachedTokens\n"
        "            if (usage.promptTokens > 0) lastPrompt = usage.promptTokens\n"
        "        }\n"
        "        if (message.role == MessageRole.ASSISTANT) {\n"
        "            lastAt = message.createdAt\n"
        "            lastModelName = message.modelId?.toString()\n"
        "        }"
    )
    if src.count(a5) != 1:
        raise ValueError("loop anchor count=" + str(src.count(a5)))
    src = src.replace(a5, b5)

    # return 前算钱
    a6 = (
        "    val rate = if (input > 0) cached.toFloat() / input.toFloat() else null\n"
        "    return RhDshUsage("
    )
    b6 = (
        "    val rate = if (input > 0) cached.toFloat() / input.toFloat() else null\n"
        "    val priceEntry = RhDshPricing.find(modelIdentifier, lastModelName)\n"
        "    val costCny = priceEntry?.let {\n"
        "        RhDshPricing.estimate(it, input, lastCached, output, lastAt)\n"
        "    }\n"
        "    return RhDshUsage("
    )
    if src.count(a6) != 1:
        raise ValueError("rate anchor count=" + str(src.count(a6)))
    src = src.replace(a6, b6)

    # return 传参
    a7 = "        outputTps = lastTps, // rhTps345\n    )"
    b7 = (
        "        outputTps = lastTps, // rhTps345\n"
        "        costCny = costCny, // rhPricing346\n"
        "        priceLabel = priceEntry?.label,\n"
        "        pricePeak = priceEntry?.let { RhDshPricing.isPeak(lastAt) },\n"
        "    )"
    )
    if src.count(a7) != 1:
        raise ValueError("return anchor count=" + str(src.count(a7)))
    src = src.replace(a7, b7)

    if bal(src) != before:
        raise ValueError("chrome balance drift")
    write(CHROME, src)
    note("chrome: pricing computation wired")


def patch_sheet():
    src = read(CHROME)
    before = bal(src)

    old = (
        "                Column(Modifier.fillMaxWidth().padding(16.dp)) {\n"
        "                    if (provider is ProviderSetting.OpenAI && provider.balanceOption.enabled) {\n"
        "                        ProviderBalanceText(\n"
        "                            providerSetting = provider,\n"
        "                            style = MaterialTheme.typography.bodyMedium,\n"
        "                            color = scheme.onSurface,\n"
        "                        )\n"
        "                    } else {\n"
        "                        Text(\"填写 API Key 后可查询余额\", fontSize = 14.sp, color = scheme.onSurfaceVariant)\n"
        "                    }\n"
        "                }"
    )
    new = (
        "                Column(Modifier.fillMaxWidth().padding(16.dp)) {\n"
        "                    val cost = usage.costCny // rhPricing346\n"
        "                    if (cost != null) {\n"
        "                        Text(\n"
        "                            text = \"估算消费 \" + RhDshPricing.formatCny(cost),\n"
        "                            fontSize = 18.sp,\n"
        "                            fontWeight = FontWeight.Medium,\n"
        "                            color = scheme.onSurface,\n"
        "                        )\n"
        "                        Text(\n"
        "                            text = (usage.priceLabel ?: \"\") +\n"
        "                                (if (usage.pricePeak == true) \" · 峰时\" else \" · 谷时\") +\n"
        "                                \" · 本地估算\",\n"
        "                            fontSize = 11.sp,\n"
        "                            color = scheme.onSurfaceVariant,\n"
        "                        )\n"
        "                    } else if (provider is ProviderSetting.OpenAI && provider.balanceOption.enabled) {\n"
        "                        ProviderBalanceText(\n"
        "                            providerSetting = provider,\n"
        "                            style = MaterialTheme.typography.bodyMedium,\n"
        "                            color = scheme.onSurface,\n"
        "                        )\n"
        "                    } else {\n"
        "                        Text(\"该模型暂无价格表，无法估算消费\", fontSize = 14.sp, color = scheme.onSurfaceVariant)\n"
        "                    }\n"
        "                }"
    )
    if src.count(old) != 1:
        raise ValueError("balance card anchor count=" + str(src.count(old)))
    src = src.replace(old, new)

    if bal(src) != before:
        raise ValueError("sheet balance drift")
    write(CHROME, src)
    note("sheet: cost line installed")


def main():
    errors = []
    try:
        write(PRICING, PRICING_SRC)
        note("pricing: wrote " + str(len(PRICING_SRC)) + " bytes")
    except Exception as exc:
        errors.append("pricing FAILED: " + str(exc))

    for name, fn in (("message", patch_message), ("handler", patch_handler), ("chrome", patch_chrome), ("sheet", patch_sheet)):
        try:
            fn()
        except Exception as exc:
            errors.append(name + " FAILED: " + str(exc))
            note(name + " FAILED: " + str(exc))

    open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
    if errors:
        print("::error title=rhPricing346::" + " | ".join(errors))
    else:
        print("::error title=rhPricing346::OK local cost estimate in balance card")


main()
package me.rerere.rikkahub.data.model

import kotlinx.serialization.Serializable

/**
 * 定时任务配置
 */
@Serializable
data class CronJob(
    val id: String,
    val name: String,
    val prompt: String,
    val cronExpression: String,  // 标准5位cron：分 时 日 月 周
    val assistantId: String? = null,  // 目标助手（null=当前）
    val conversationId: String? = null,  // 目标会话（null=新建）
    val enabled: Boolean = true,
    val lastRunAt: Long? = null,  // 上次执行时间戳
    val nextRunAt: Long? = null,  // 下次执行时间戳（由调度器计算）
    val createdAt: Long = System.currentTimeMillis(),
)

/**
 * Cron表达式解析器（仅支持5位标准格式；日与周字段遵循 Vixie 语义：
 * 两者都受限时取 OR——如 `0 0 1 * 1` 表示每月1号**或**每周一）
 */
object CronParser {

    /**
     * 解析cron表达式，计算下次执行时间
     * @param cronExpression 5位cron：分(0-59) 时(0-23) 日(1-31) 月(1-12) 周(0-6, 0=周日)
     * @param fromTime 基准时间（默认当前）
     * @return 下次执行时间戳（无匹配返回null）
     */
    fun parseNextRun(cronExpression: String, fromTime: Long = System.currentTimeMillis()): Long? {
        val parts = cronExpression.trim().split("\\s+".toRegex())
        if (parts.size != 5) return null

        try {
            val minutePattern = parseField(parts[0], 0, 59) ?: return null
            val hourPattern = parseField(parts[1], 0, 23) ?: return null
            val dayPattern = parseField(parts[2], 1, 31) ?: return null
            val monthPattern = parseField(parts[3], 1, 12) ?: return null
            val weekdayPattern = parseField(parts[4], 0, 6) ?: return null

            // Vixie cron：日与周是否「受限」（未写全量）。两者都受限时按 OR 匹配。
            val dayRestricted = dayPattern != (1..31).toSet()
            val weekdayRestricted = weekdayPattern != (0..6).toSet()

            // 从下一分钟开始找
            var time = fromTime + 60_000 - (fromTime % 60_000)
            val calendar = java.util.Calendar.getInstance()

            // 最多找366天（避免死循环）
            for (i in 0 until 366 * 24 * 60) {
                calendar.timeInMillis = time
                val minute = calendar.get(java.util.Calendar.MINUTE)
                val hour = calendar.get(java.util.Calendar.HOUR_OF_DAY)
                val day = calendar.get(java.util.Calendar.DAY_OF_MONTH)
                val month = calendar.get(java.util.Calendar.MONTH) + 1
                val weekday = calendar.get(java.util.Calendar.DAY_OF_WEEK) - 1  // Calendar: 1=周日, Cron: 0=周日

                // 标准 Vixie 语义：日和周都受限时取 OR（每月1号或每周一），
                // 只有其一受限时按 AND（未受限字段本就匹配所有值）。
                val dayMatches = if (dayRestricted && weekdayRestricted) {
                    day in dayPattern || weekday in weekdayPattern
                } else {
                    day in dayPattern && weekday in weekdayPattern
                }

                if (minute in minutePattern &&
                    hour in hourPattern &&
                    dayMatches &&
                    month in monthPattern
                ) {
                    return time
                }
                time += 60_000  // 下一分钟
            }
        } catch (e: Exception) {
            return null
        }
        return null
    }

    /**
     * 解析单个cron字段，返回匹配的值集合
     * 支持：* , - / 四种语法（N/step 表示从 N 到字段上限每 step 步，如分 5/10 = 5,15,25,...）
     */
    private fun parseField(field: String, min: Int, max: Int): Set<Int>? {
        val result = mutableSetOf<Int>()

        // 分割逗号
        val segments = field.split(",")
        for (seg in segments) {
            val rangePart: String
            val stepPart: String
            val hasStep: Boolean

            if ("/" in seg) {
                val parts = seg.split("/")
                if (parts.size != 2) return null
                rangePart = parts[0]
                stepPart = parts[1]
                hasStep = true
            } else {
                rangePart = seg
                stepPart = "1"
                hasStep = false
            }

            val step = stepPart.toIntOrNull() ?: return null
            if (step <= 0) return null

            val range: IntRange
            if (rangePart == "*") {
                range = min..max
            } else if ("-" in rangePart) {
                val rangeParts = rangePart.split("-")
                if (rangeParts.size != 2) return null
                val start = rangeParts[0].toIntOrNull() ?: return null
                val end = rangeParts[1].toIntOrNull() ?: return null
                if (start < min || end > max || start > end) return null
                range = start..end
            } else {
                val value = rangePart.toIntOrNull() ?: return null
                if (value < min || value > max) return null
                // 标准 cron：N/step = 从 N 到字段上限每 step 步；不带 step 才是单值
                range = if (hasStep) value..max else value..value
            }

            // 按步长采样
            var current = range.first
            while (current <= range.last) {
                result.add(current)
                current += step
            }
        }

        return if (result.isEmpty()) null else result
    }

    /**
     * 验证cron表达式格式
     */
    fun isValid(cronExpression: String): Boolean {
        return parseNextRun(cronExpression, System.currentTimeMillis()) != null
    }
}

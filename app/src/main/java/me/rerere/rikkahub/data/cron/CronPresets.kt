package me.rerere.rikkahub.data.cron

import kotlinx.serialization.Serializable

/**
 * rhCronPresets: 定时任务 cron 规则的唯一数据源。
 *
 * rhCronPreset373: 把两套消费方的 API 合并到同一份数据上。
 *   · 274 的消费方（CronTools / AppControlService）用 title / cronExpression / suggestedPrompt
 *   · 371 的消费方（SettingScheduledJobsPage）用 label / expression / CATEGORIES / of / match
 * 数据只存一份，别名用计算属性，避免两边各改一遍、也避免再撞一次在链 patch 的锚点。
 */
@Serializable
data class CronPreset(
    val id: String,
    val title: String,
    val cronExpression: String,
    val description: String,
    val suggestedPrompt: String = "",
    val category: String = "每天",
) {
    /** rhCronPreset373: 设置页 chip 上显示的短标签。 */
    val label: String get() = title

    /** rhCronPreset373: 设置页 chip 写入输入框的表达式。 */
    val expression: String get() = cronExpression
}

object CronPresets {

    const val CAT_HIGH_FREQ = "高频"
    const val CAT_DAILY = "每天"
    const val CAT_WEEKLY = "每周"
    const val CAT_MONTHLY = "每月"

    val ALL: List<CronPreset> = listOf(
        CronPreset("hourly", "每小时整点", "0 * * * *", "每个整点触发", "", CAT_HIGH_FREQ),
        CronPreset("every_30min", "每30分钟", "*/30 * * * *", "每半小时", "", CAT_HIGH_FREQ),
        CronPreset("every_15min", "每15分钟", "*/15 * * * *", "每 15 分钟", "", CAT_HIGH_FREQ),
        CronPreset("daily_9am", "每天9点", "0 9 * * *", "每天上午9点", "", CAT_DAILY),
        CronPreset("twice_daily_8_20", "每天早晚8点", "0 8,20 * * *", "08:00 与 20:00", "", CAT_DAILY),
        CronPreset("daily_18pm", "每天18点", "0 18 * * *", "每天傍晚18点", "", CAT_DAILY),
        CronPreset("workday_9am", "工作日9点", "0 9 * * 1-5", "周一至周五上午9点", "", CAT_WEEKLY),
        CronPreset("weekly_mon_8am", "每周一8点", "0 8 * * 1", "每周一早8点", "", CAT_WEEKLY),
        CronPreset("weekly_fri_18pm", "每周五18点", "0 18 * * 5", "每周五傍晚18点", "", CAT_WEEKLY),
        CronPreset("weekly_sun_20pm", "每周日20点", "0 20 * * 0", "每周日晚8点", "", CAT_WEEKLY),
        CronPreset("monthly_1st_9am", "每月1号9点", "0 9 1 * *", "每月1号上午9点", "", CAT_MONTHLY),
        CronPreset("monthly_15th_9am", "每月15号9点", "0 9 15 * *", "每月15号上午9点", "", CAT_MONTHLY),
    )

    /** rhCronPreset373: 设置页按这个顺序分组渲染，每组先露 2 个。 */
    val CATEGORIES: List<String> = listOf(CAT_HIGH_FREQ, CAT_DAILY, CAT_WEEKLY, CAT_MONTHLY)

    fun of(category: String): List<CronPreset> = ALL.filter { it.category == category }

    fun match(expression: String): CronPreset? =
        ALL.firstOrNull { it.cronExpression == expression.trim() }

    private val byId: Map<String, CronPreset> = ALL.associateBy { it.id }

    fun resolve(id: String?): CronPreset? = if (id == null) null else byId[id]

    /** 报错时列出的可用 id 清单。 */
    fun ids(): String = ALL.joinToString(", ") { it.id }
}

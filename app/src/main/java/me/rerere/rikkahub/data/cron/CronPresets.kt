package me.rerere.rikkahub.data.cron

import kotlinx.serialization.Serializable

/**
 * rhCronPresets: 定时任务 cron 规则的唯一数据源。
 *
 * 工具入口（CronTools.schedule_job）与 App Control 入口（AppControlService.scheduleCronJob）
 * 都从这里取表达式，禁止各写一份。新增预设只需往 [CronPresets.ALL] 加一条。
 */
@Serializable
data class CronPreset(
    val id: String,
    val title: String,
    val cronExpression: String,
    val description: String,
    val suggestedPrompt: String = "",
)

object CronPresets {
    val ALL: List<CronPreset> = listOf(
        CronPreset("hourly", "每小时整点", "0 * * * *", "每个整点触发"),
        CronPreset("daily_9am", "每天9点", "0 9 * * *", "每天上午9点"),
        CronPreset("workday_9am", "工作日9点", "0 9 * * 1-5", "周一至周五上午9点"),
        CronPreset("weekly_mon_8am", "每周一8点", "0 8 * * 1", "每周一早8点"),
        CronPreset("monthly_1st_9am", "每月1号9点", "0 9 1 * *", "每月1号上午9点"),
        CronPreset("every_30min", "每30分钟", "*/30 * * * *", "每半小时"),
        CronPreset("twice_daily_8_20", "每天早晚8点", "0 8,20 * * *", "08:00 与 20:00"),
    )

    private val byId: Map<String, CronPreset> = ALL.associateBy { it.id }

    fun resolve(id: String?): CronPreset? = if (id == null) null else byId[id]

    /** 报错时列出的可用 id 清单。 */
    fun ids(): String = ALL.joinToString(", ") { it.id }
}

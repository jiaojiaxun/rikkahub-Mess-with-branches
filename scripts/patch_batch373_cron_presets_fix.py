"""batch373 — 修 CronPresets 双版本冲突（371 的 UI 引用落空，编译红在 SettingScheduledJobsPage）

现象（run#655 annotations）：
  SettingScheduledJobsPage.kt:280 Unresolved reference 'id'
  SettingScheduledJobsPage.kt:281 @Composable invocations can only happen from the context of a @Composable function
  SettingScheduledJobsPage.kt:282 Unresolved reference 'expression'

根因（读脚本 + snapshot 实证）：
  · batch274 建了 data/cron/CronPresets.kt，字段 id/title/cronExpression/description/suggestedPrompt，
    另有 ALL/byId/resolve()/ids()。CronTools 与 AppControlService 按这套消费。
  · batch371 想把同一文件换成 12 预设 + CATEGORIES/of()/match()/label/expression 的版本，
    但幂等判据写成「文件存在且含 object CronPresets 就跳过」——274 已建文件，于是 371 跳过写文件，
    只把设置页改成了新 API。结果 CATEGORIES/of()/match() 全部未解析 → preset 变成 error type
    → preset.id / preset.expression 连带报错 → Surface 的 content lambda 失去 @Composable 推断。
  · 371 自己的 diag 已经喊了：check:preset-count-12:FAIL / check:four-categories:FAIL / check:match-fn:FAIL

修法：
  整文件重写 CronPresets.kt，把两套 API 合并到同一份数据：
    · 274 侧：title / cronExpression / description / suggestedPrompt / resolve / ids 原样保留
    · 371 侧：label / expression 用计算属性别名，补 CATEGORIES / of() / match()
    · 预设扩到 12 个、4 个分类（且每个表达式都是 5 位标准 cron，CronParser 能解析）
  不动 SettingScheduledJobsPage.kt（避免再撞 371 的锚点），也不动 CronTools / AppControlService。
"""

import os

ROOT = os.getcwd()
TARGET = os.path.join(
    ROOT,
    "app/src/main/java/me/rerere/rikkahub/data/cron/CronPresets.kt",
)
DIAG = os.path.join(ROOT, "ci_diag_batch373_cron_presets.txt")

log = []


def note(m):
    print(m)
    log.append(str(m))


def bal(t):
    return (t.count('{') - t.count('}'), t.count('(') - t.count(')'))


SRC = r'''package me.rerere.rikkahub.data.cron

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
'''


def main():
    existing = ""
    if os.path.isfile(TARGET):
        existing = open(TARGET, "r", encoding="utf-8").read()

    if "rhCronPreset373" in existing:
        note("already applied, skip")
        open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
        return

    check = bal(SRC)
    note("source balance " + str(check) + " len=" + str(len(SRC)))
    if check != (0, 0):
        note("FAIL source unbalanced")
        open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
        raise SystemExit(1)

    id_list = []
    for line in SRC.splitlines():
        stripped = line.strip()
        if stripped.startswith('CronPreset("'):
            first = stripped.split('"')
            if len(first) > 1:
                id_list.append(first[1])
    note("preset ids=" + str(len(id_list)) + " " + ",".join(id_list))
    if len(id_list) != 12:
        note("FAIL preset count " + str(len(id_list)))
        open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
        raise SystemExit(1)
    if len(set(id_list)) != 12:
        note("FAIL duplicate preset ids")
        open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
        raise SystemExit(1)

    for must in [
        "const val CAT_HIGH_FREQ",
        "val CATEGORIES",
        "fun of(category: String)",
        "fun match(expression: String)",
        "fun resolve(id: String?)",
        "fun ids()",
        "val label: String get()",
        "val expression: String get()",
    ]:
        if must not in SRC:
            note("FAIL missing " + must)
            open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
            raise SystemExit(1)

    # 274 的四个字段必须还在（CronTools / AppControlService 依赖）
    for keep in ["val title:", "val cronExpression:", "val description:", "val suggestedPrompt:"]:
        if keep not in SRC:
            note("FAIL lost field " + keep)
            open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
            raise SystemExit(1)

    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    open(TARGET, "w", encoding="utf-8").write(SRC)

    written = open(TARGET, "r", encoding="utf-8").read()
    note("written balance " + str(bal(written)) + " len=" + str(len(written)))
    if bal(written) != (0, 0):
        note("FAIL written unbalanced")
        open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
        raise SystemExit(1)

    note("DONE cron presets merged (274 api + 371 api)")
    print("::error title=rhCronPreset373::OK CronPresets 双版本合并：12 预设 4 分类 + label/expression 别名")
    open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")


main()

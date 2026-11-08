#!/usr/bin/env python3
# rhCronPreset371: 定时任务预设成体系 —— 4 个硬编码 → 12 个分组 + 输入框说人话
#
# 实读现状（SettingScheduledJobsPage.kt）：
#   · 新建/编辑对话框里只有 4 个硬编码 chips（marker rhCronBeautify）：
#       "0 9 * * *" 每天 9:00 / "0 * * * *" 每小时 / "0 9 * * 1" 每周一 9:00 / "*/30 * * * *" 每 30 分钟
#   · cron 输入框的 supportingText 只写"格式正确"/"格式错误"，不给实际含义
#   · 文件底部已有 private describeCron（marker rhCronDesc），但有两个洞：
#       hour = "*/2" → 落到最后 else 分支，输出「每天 */2:00」（错）
#       week = "1-5" → 落到 week 分支，输出「每周1-5 09:00」（丑，应为"工作日"）
#
# 本批四件事：
#   1) 新文件 data/cron/CronPresets.kt：12 个预设按"高频/每天/每周/每月"分组，
#      与 UI 解耦（数据是数据，chips 是 chips）
#   2) 对话框里的硬编码 listOf → 按组渲染（每组 2 个，共 8 个 chip），
#      当前表达式命中预设时高亮 primaryContainer
#   3) supportingText 从"格式正确"改成 describeCron 的实时人话
#   4) describeCron 补两个分支：hour 的 */N、week 的 1-5（工作日）
#
# 幂等：新文件按存在判断，三处编辑按内容特征判断（各用独立 probe，不共用 MARK）。

import os
import sys

MARK = "rhCronPreset371"
REPO = os.getcwd()
APP = os.path.join(REPO, "app", "src", "main", "java", "me", "rerere", "rikkahub")
PRESETS = os.path.join(APP, "data", "cron", "CronPresets.kt")
PAGE = os.path.join(APP, "ui", "pages", "setting", "SettingScheduledJobsPage.kt")
DIAG = os.path.join(REPO, "ci_diag_batch371_cron_presets.txt")

PRESETS_SRC = '''package me.rerere.rikkahub.data.cron

/**
 * 定时任务的预设表达式。
 *
 * 用户不该被迫手写 cron。这里按"多久跑一次"分组，给出最常用的 12 种；
 * 数据与 UI 解耦 —— [CronPresets] 只描述"有什么"，chips 怎么摆由设置页决定。
 */
data class CronPreset(
    val id: String,
    /** chip 上显示的短标签 */
    val label: String,
    /** 标准 5 位 cron：分 时 日 月 周 */
    val expression: String,
    val category: String,
)

object CronPresets {

    const val CAT_HIGH_FREQ = "高频"
    const val CAT_DAILY = "每天"
    const val CAT_WEEKLY = "每周"
    const val CAT_MONTHLY = "每月"

    val ALL: List<CronPreset> = listOf(
        CronPreset("m05", "每 5 分钟", "*/5 * * * *", CAT_HIGH_FREQ),
        CronPreset("m30", "每 30 分钟", "*/30 * * * *", CAT_HIGH_FREQ),
        CronPreset("h01", "每小时", "0 * * * *", CAT_HIGH_FREQ),
        CronPreset("h02", "每 2 小时", "0 */2 * * *", CAT_HIGH_FREQ),
        CronPreset("d08", "每天 08:00", "0 8 * * *", CAT_DAILY),
        CronPreset("d12", "每天 12:00", "0 12 * * *", CAT_DAILY),
        CronPreset("d22", "每天 22:00", "0 22 * * *", CAT_DAILY),
        CronPreset("w05", "工作日 09:00", "0 9 * * 1-5", CAT_WEEKLY),
        CronPreset("w01", "周一 09:00", "0 9 * * 1", CAT_WEEKLY),
        CronPreset("w15", "周五 18:00", "0 18 * * 5", CAT_WEEKLY),
        CronPreset("mo1", "每月 1 号 09:00", "0 9 1 * *", CAT_MONTHLY),
        CronPreset("mo15", "每月 15 号 09:00", "0 9 15 * *", CAT_MONTHLY),
    )

    val CATEGORIES: List<String> = listOf(CAT_HIGH_FREQ, CAT_DAILY, CAT_WEEKLY, CAT_MONTHLY)

    fun of(category: String): List<CronPreset> = ALL.filter { it.category == category }

    fun match(expression: String): CronPreset? =
        ALL.firstOrNull { it.expression == expression.trim() }
}
'''

IMPORT_OLD = 'import me.rerere.rikkahub.data.cron.CronJobStore\n'
IMPORT_NEW = (
    'import me.rerere.rikkahub.data.cron.CronJobStore\n'
    'import me.rerere.rikkahub.data.cron.CronPresets // ' + MARK + '\n'
)

CHIPS_OLD = '''                    // rhCronBeautify: cron preset chips
                    Text("常用示例：", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        listOf("0 9 * * *" to "每天 9:00", "0 * * * *" to "每小时", "0 9 * * 1" to "每周一 9:00", "*/30 * * * *" to "每 30 分钟").forEach { (cron, label) ->
                            Surface(
                                onClick = { cronExpr = cron },
                                shape = MaterialTheme.shapes.small,
                                color = MaterialTheme.colorScheme.secondaryContainer,
                            ) {
                                Text(
                                    text = label,
                                    style = MaterialTheme.typography.labelSmall,
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                )
                            }
                        }
                    }
'''

CHIPS_NEW = '''                    // ''' + MARK + ''': 预设成体系 —— 12 个按"多久跑一次"分组，每组先露 2 个。
                    // 用户不用记 cron 语法；当前表达式命中哪个预设就高亮哪个。
                    Text(
                        text = "常用预设",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    CronPresets.CATEGORIES.forEach { category ->
                        Row(
                            verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(6.dp),
                        ) {
                            Text(
                                text = category,
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.width(32.dp),
                            )
                            CronPresets.of(category).take(2).forEach { preset ->
                                val selected = CronPresets.match(cronExpr)?.id == preset.id
                                Surface(
                                    onClick = { cronExpr = preset.expression },
                                    shape = MaterialTheme.shapes.small,
                                    color = if (selected) {
                                        MaterialTheme.colorScheme.primaryContainer
                                    } else {
                                        MaterialTheme.colorScheme.secondaryContainer
                                    },
                                ) {
                                    Text(
                                        text = preset.label,
                                        style = MaterialTheme.typography.labelSmall,
                                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                    )
                                }
                            }
                        }
                    }
'''

SUPPORT_OLD = '''                        supportingText = {
                            Text(
                                text = if (cronValid) "格式正确" else "格式错误，应为：分 时 日 月 周",
                                color = if (cronValid) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                            )
                        },
'''
SUPPORT_NEW = '''                        supportingText = {
                            Text(
                                // ''' + MARK + ''': 直接显示"人话"，比"格式正确"有用
                                text = if (cronValid) describeCron(cronExpr) else "格式错误，应为：分 时 日 月 周",
                                color = if (cronValid) {
                                    MaterialTheme.colorScheme.onSurfaceVariant
                                } else {
                                    MaterialTheme.colorScheme.error
                                },
                            )
                        },
'''

DESC_OLD = '''        min == "*" -> "每分钟"
        hour == "*" -> "每小时第 " + min + " 分钟"
        week != "*" -> {
'''
DESC_NEW = '''        min == "*" -> "每分钟"
        hour == "*" -> "每小时第 " + min + " 分钟"
        // ''' + MARK + ''': 补两个洞 —— 小时的 */N 与工作日
        hour.startsWith("*/") -> "每 " + hour.removePrefix("*/") + " 小时（第 " + min + " 分）"
        week == "1-5" && day == "*" ->
            "工作日 " + (num(hour)?.let { pad2(it) } ?: hour) + ":" + (num(min)?.let { pad2(it) } ?: min)
        week != "*" -> {
'''

OUT = []


def log(line):
    OUT.append(line)
    print(line)


def strip_literals(source):
    out = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch == '"' or ch == "'":
            quote = ch
            i += 1
            while i < n:
                if source[i] == "\\":
                    i += 2
                    continue
                if source[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            while i < n and source[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "*":
            i += 2
            while i + 1 < n and not (source[i] == "*" and source[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def counts(text):
    stripped = strip_literals(text)
    return stripped.count("{") - stripped.count("}"), stripped.count("(") - stripped.count(")")


def apply(text, old, new, label, probe):
    if probe in text:
        log("already:" + label)
        return text, []
    hits = text.count(old)
    log("anchor-" + label + ":" + str(hits))
    if hits != 1:
        return text, ["anchor:" + label + ":" + str(hits)]
    return text.replace(old, new), []


def main():
    failures = []

    # 1) 新文件
    if os.path.isfile(PRESETS) and "object CronPresets" in open(PRESETS, "r", encoding="utf-8").read():
        log("already:presets-file")
    else:
        os.makedirs(os.path.dirname(PRESETS), exist_ok=True)
        with open(PRESETS, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(PRESETS_SRC)
        log("wrote:presets-file:" + str(len(PRESETS_SRC)))

    if not os.path.isfile(PAGE):
        log("missing-file:page")
        with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(OUT) + "\nmissing-file:page\nRESULT:FAIL\n")
        sys.exit(1)

    with open(PAGE, "r", encoding="utf-8") as handle:
        text = handle.read()
    before = counts(text)

    text, err = apply(text, IMPORT_OLD, IMPORT_NEW, "import", "data.cron.CronPresets")
    failures += err

    text, err = apply(text, CHIPS_OLD, CHIPS_NEW, "chips", "CronPresets.CATEGORIES.forEach")
    failures += err

    text, err = apply(text, SUPPORT_OLD, SUPPORT_NEW, "supporting", "describeCron(cronExpr)")
    failures += err

    text, err = apply(text, DESC_OLD, DESC_NEW, "describe", "工作日 \" + (num(hour)")
    failures += err

    after = counts(text)
    log("braces:" + str(before) + "->" + str(after))
    if before != after:
        failures.append("braces:" + str(before) + "->" + str(after))

    with open(PAGE, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    log("page-size:" + str(len(text)))

    # 复核
    with open(PAGE, "r", encoding="utf-8") as handle:
        final = handle.read()
    checks = [
        ("import-present", "data.cron.CronPresets" in final),
        ("chips-use-presets", "CronPresets.of(category)" in final),
        ("hardcoded-list-gone", 'listOf("0 9 * * *" to' not in final),
        ("supporting-describes", "describeCron(cronExpr)" in final),
        ("describe-weekday", '工作日 " + (num(hour)' in final),
        ("describe-hourly-step", 'hour.startsWith("*/")' in final),
        ("desc-fn-intact", "private fun describeCron(expr: String): String" in final),
        ("cronparser-kept", "CronParser.isValid" in final),
    ]
    for name, ok in checks:
        log("check:" + name + ":" + ("ok" if ok else "FAIL"))
        if not ok:
            failures.append("check:" + name)

    # 新文件内容复核
    try:
        with open(PRESETS, "r", encoding="utf-8") as handle:
            preset_text = handle.read()
        preset_checks = [
            ("preset-count-12", preset_text.count("CronPreset(") == 13),
            ("four-categories", preset_text.count("CAT_") >= 4),
            ("match-fn", "fun match(expression: String)" in preset_text),
        ]
        for name, ok in preset_checks:
            log("check:" + name + ":" + ("ok" if ok else "FAIL"))
            if not ok:
                failures.append("check:" + name)
    except OSError as error:
        failures.append("presets-read:" + str(error))

    if failures:
        log("RESULT:FAIL")
        log("failures:" + "|".join(failures))
    else:
        log("RESULT:OK")

    with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(OUT) + "\n")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()

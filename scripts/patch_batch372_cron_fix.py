#!/usr/bin/env python3
# rhCronPreset372: 修 371 的编译红 —— UI 适配"已被并行会话创建"的 CronPresets
#
# 371 的失败链（已定位，不是猜的）：
#   1) 我的脚本打算新建 data/cron/CronPresets.kt，判定条件是
#      `isfile && "object CronPresets" in content` → 命中 already，跳过写入
#   2) 因为该文件**早已被并行会话创建**，内容与我的设计完全不同：
#        data class CronPreset(id, title, cronExpression, description, suggestedPrompt)
#        object CronPresets { ALL / resolve(id) / ids() }
#   3) 而我的 UI 代码引用的是我自己设想、并不存在的 API：
#        CronPresets.CATEGORIES / CronPresets.of(category) / CronPresets.match(expr)
#        preset.label / preset.expression
#   → Unresolved reference 'CATEGORIES' / 'of' / 'match' / 'expression'，编译红。
#
# 教训（第 7 条铁律）：**新建文件型 patch 必须先实读目标目录确认文件不存在**；
# 「已存在」的判定不能用宽松特征（"object X" in content），必须比对完整签名。
# 并行会话会抢先创建同名文件，if not exists 挡不住。
#
# 本批不改 CronPresets.kt（避免与并行会话争同文件），只改我的 UI：
#   · CronPresets.CATEGORIES.forEach { category -> ... } → CronPresets.ALL.chunked(3)
#   · preset.label → preset.title
#   · preset.expression → preset.cronExpression
#   · CronPresets.match(cronExpr)?.id == preset.id → preset.cronExpression == cronExpr.trim()
#   · 去掉分组标签那一行（既有数据没有 category 字段）
#
# 保留：describeCron 的两个新分支（hour 的 */N、week 的 1-5 工作日）与输入框人话提示。

import os
import sys

MARK = "rhCronPreset372"
REPO = os.getcwd()
PAGE = os.path.join(
    REPO, "app", "src", "main", "java", "me", "rerere", "rikkahub",
    "ui", "pages", "setting", "SettingScheduledJobsPage.kt",
)
DIAG = os.path.join(REPO, "ci_diag_batch372_cron_fix.txt")

OLD = '''                    // rhCronPreset371: 预设成体系 —— 12 个按"多久跑一次"分组，每组先露 2 个。
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

NEW = '''                    // ''' + MARK + ''': 直接复用 data/cron/CronPresets.kt 里已有的预设表
                    // —— 那份是 CronTools 与 AppControlService 共用的唯一数据源。
                    // 这里只负责渲染：每行 3 个，命中当前表达式的高亮。
                    Text(
                        text = "常用预设",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    CronPresets.ALL.chunked(3).forEach { rowPresets ->
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            rowPresets.forEach { preset ->
                                val selected = preset.cronExpression == cronExpr.trim()
                                Surface(
                                    onClick = { cronExpr = preset.cronExpression },
                                    shape = MaterialTheme.shapes.small,
                                    color = if (selected) {
                                        MaterialTheme.colorScheme.primaryContainer
                                    } else {
                                        MaterialTheme.colorScheme.secondaryContainer
                                    },
                                ) {
                                    Text(
                                        text = preset.title,
                                        style = MaterialTheme.typography.labelSmall,
                                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                                    )
                                }
                            }
                        }
                    }
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


def main():
    failures = []

    if not os.path.isfile(PAGE):
        log("missing-file:page")
        with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("missing-file:page\nRESULT:FAIL\n")
        sys.exit(1)

    with open(PAGE, "r", encoding="utf-8") as handle:
        text = handle.read()
    before = counts(text)

    if "CronPresets.ALL.chunked(3)" in text:
        log("already:fix")
    else:
        hits = text.count(OLD)
        log("anchor:" + str(hits))
        if hits != 1:
            failures.append("anchor:" + str(hits))
        else:
            text = text.replace(OLD, NEW)
            log("wrote:fix")

    after = counts(text)
    log("braces:" + str(before) + "->" + str(after))
    if before != after:
        failures.append("braces:" + str(before) + "->" + str(after))

    with open(PAGE, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    log("page-size:" + str(len(text)))

    # 复核（磁盘为准）：不存在的 API 必须彻底消失
    with open(PAGE, "r", encoding="utf-8") as handle:
        final = handle.read()
    checks = [
        ("no-categories", "CronPresets.CATEGORIES" not in final),
        ("no-of-call", "CronPresets.of(" not in final),
        ("no-match-call", "CronPresets.match(" not in final),
        ("uses-all", "CronPresets.ALL.chunked(3)" in final),
        ("uses-title", "text = preset.title," in final),
        ("uses-cron-expression", "preset.cronExpression" in final),
        ("import-kept", "data.cron.CronPresets" in final),
        ("describe-weekday-kept", '工作日 " + (num(hour)' in final),
        ("describe-hourly-kept", 'hour.startsWith("*/")' in final),
        ("supporting-kept", "describeCron(cronExpr)" in final),
    ]
    for name, ok in checks:
        log("check:" + name + ":" + ("ok" if ok else "FAIL"))
        if not ok:
            failures.append("check:" + name)

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

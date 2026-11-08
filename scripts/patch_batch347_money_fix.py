"""batch347 — 修 346 的两个问题。

① formatCny 的小数位：`(value * 10000).toLong() / 100.0` 等于 value*100，
   ¥0.1234 会显示成 ¥12.34。应除以 10000.0（保留 4 位）。
② 面板里非峰时也显示「谷时」，但 Kimi/GLM/Gemini 没有峰谷价，会被误读。
   改为只有真峰时才标注，其余只显示「本地估算」。
"""

import os

ROOT = os.getcwd()
PRICING = os.path.join(
    ROOT, "app/src/main/java/me/rerere/rikkahub/ui/components/ai/RhDshPricing.kt"
)
CHROME = os.path.join(
    ROOT, "app/src/main/java/me/rerere/rikkahub/ui/components/ai/RhDshChrome.kt"
)
DIAG = os.path.join(ROOT, "ci_diag_batch347_money_fix.txt")

log = []


def note(m):
    print(m)
    log.append(str(m))


def bal(t):
    return (t.count('{') - t.count('}'), t.count('(') - t.count(')'))


def main():
    errors = []

    # ① 金额格式
    try:
        src = open(PRICING, "r", encoding="utf-8").read()
        before = bal(src)
        old = (
            "        if (value < 1.0) {\n"
            "            val cents = (value * 10000).toLong() / 100.0\n"
            "            return \"¥\" + cents.toString()\n"
            "        }"
        )
        new = (
            "        if (value < 1.0) {\n"
            "            val v = (value * 10000).toLong() / 10000.0\n"
            "            return \"¥\" + v.toString()\n"
            "        }"
        )
        if src.count(old) != 1:
            raise ValueError("formatCny anchor count=" + str(src.count(old)))
        src = src.replace(old, new)
        if bal(src) != before:
            raise ValueError("pricing balance drift")
        open(PRICING, "w", encoding="utf-8").write(src)
        note("pricing: formatCny 4-decimal fix")
    except Exception as exc:
        errors.append("pricing FAILED: " + str(exc))
        note("pricing FAILED: " + str(exc))

    # ② 峰/谷标注
    try:
        src = open(CHROME, "r", encoding="utf-8").read()
        before = bal(src)
        old = '                                (if (usage.pricePeak == true) " · 峰时" else " · 谷时") +'
        new = '                                (if (usage.pricePeak == true) " · 峰时" else "") +'
        if src.count(old) != 1:
            raise ValueError("peak label anchor count=" + str(src.count(old)))
        src = src.replace(old, new)
        if bal(src) != before:
            raise ValueError("chrome balance drift")
        open(CHROME, "w", encoding="utf-8").write(src)
        note("chrome: peak label only when peak")
    except Exception as exc:
        errors.append("chrome FAILED: " + str(exc))
        note("chrome FAILED: " + str(exc))

    open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
    if errors:
        print("::error title=rhMoney347::" + " | ".join(errors))
    else:
        print("::error title=rhMoney347::OK money formatting + peak label")


main()
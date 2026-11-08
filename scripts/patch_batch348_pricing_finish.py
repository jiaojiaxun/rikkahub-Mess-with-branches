"""batch348 — 346/347 收口。

① 去掉 kotlin.time.Clock 依赖：app 模块不一定开了 ExperimentalTime opt-in，
   isPeak 改为 at == null 直接返回 false（无消息时也没有 token，不影响金额）。
② 只有带 night 价的模型（DeepSeek）才计算/显示「峰时」，否则 Kimi/GLM/Gemini
   会被错误标注。
③ 顺带清掉因此不再使用的三个 import。
"""

import os

ROOT = os.getcwd()
PRICING = os.path.join(
    ROOT, "app/src/main/java/me/rerere/rikkahub/ui/components/ai/RhDshPricing.kt"
)
CHROME = os.path.join(
    ROOT, "app/src/main/java/me/rerere/rikkahub/ui/components/ai/RhDshChrome.kt"
)
DIAG = os.path.join(ROOT, "ci_diag_batch348_pricing_finish.txt")

log = []


def note(m):
    print(m)
    log.append(str(m))


def bal(t):
    return (t.count('{') - t.count('}'), t.count('(') - t.count(')'))


def main():
    errors = []

    try:
        src = open(PRICING, "r", encoding="utf-8").read()
        before = bal(src)

        old = "        val time = at ?: Clock.System.now().toLocalDateTime(TimeZone.currentSystemDefault())"
        new = "        val time = at ?: return false // rhPricing348: 无消息时按谷价，且不含 Clock 依赖"
        if src.count(old) != 1:
            raise ValueError("clock anchor count=" + str(src.count(old)))
        src = src.replace(old, new)

        for imp in (
            "import kotlinx.datetime.TimeZone\n",
            "import kotlinx.datetime.toLocalDateTime\n",
            "import kotlin.time.Clock\n",
        ):
            if src.count(imp) == 1:
                src = src.replace(imp, "")
                note("pricing: removed " + imp.strip())

        if bal(src) != before:
            raise ValueError("pricing balance drift")
        open(PRICING, "w", encoding="utf-8").write(src)
        note("pricing: isPeak no longer needs Clock")
    except Exception as exc:
        errors.append("pricing FAILED: " + str(exc))
        note("pricing FAILED: " + str(exc))

    try:
        src = open(CHROME, "r", encoding="utf-8").read()
        before = bal(src)
        old = "        pricePeak = priceEntry?.let { RhDshPricing.isPeak(lastAt) },"
        new = "        pricePeak = priceEntry?.let { if (it.night != null) RhDshPricing.isPeak(lastAt) else null }, // rhPricing348"
        if src.count(old) != 1:
            raise ValueError("pricePeak anchor count=" + str(src.count(old)))
        src = src.replace(old, new)
        if bal(src) != before:
            raise ValueError("chrome balance drift")
        open(CHROME, "w", encoding="utf-8").write(src)
        note("chrome: peak only for entries with night price")
    except Exception as exc:
        errors.append("chrome FAILED: " + str(exc))
        note("chrome FAILED: " + str(exc))

    open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
    if errors:
        print("::error title=rhPricing348::" + " | ".join(errors))
    else:
        print("::error title=rhPricing348::OK clock-free peak + night-only badge")


main()
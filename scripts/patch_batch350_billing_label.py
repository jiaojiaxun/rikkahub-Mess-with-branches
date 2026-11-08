"""batch350 — 估算消费后直接括注计价模型。

用户要求：金额后面用括号说明按哪个模型计费，例如
    估算消费 ¥0.86（DeepSeek V4.1 Flash）
峰时/本地估算缩到第二行，不再重复模型名。

锚点基于 349 之后的 RhDshUsageSheet（349 已把 override 切到 priceLabel）。
"""

import os

ROOT = os.getcwd()
CHROME = os.path.join(
    ROOT, "app/src/main/java/me/rerere/rikkahub/ui/components/ai/RhDshChrome.kt"
)
DIAG = os.path.join(ROOT, "ci_diag_batch350_billing_label.txt")

log = []


def note(m):
    print(m)
    log.append(str(m))


def bal(t):
    return (t.count('{') - t.count('}'), t.count('(') - t.count(')'))


def main():
    src = open(CHROME, "r", encoding="utf-8").read()
    before = bal(src)

    old_main = '                            text = "估算消费 " + RhDshPricing.formatCny(cost),'
    new_main = (
        '                            text = "估算消费 " + RhDshPricing.formatCny(cost) +\n'
        '                                "（" + (usage.priceLabel ?: "未知模型") + "）", // rhBilling350'
    )
    if src.count(old_main) != 1:
        raise SystemExit("main text anchor count=" + str(src.count(old_main)))
    src = src.replace(old_main, new_main)
    note("sheet: model name moved into parentheses")

    old_sub = (
        '                            text = (usage.priceLabel ?: "") +\n'
        '                                (if (usage.pricePeak == true) " · 峰时" else "") +\n'
        '                                " · 本地估算",'
    )
    new_sub = (
        '                            text = (if (usage.pricePeak == true) "峰时 · " else "") + "本地估算", // rhBilling350'
    )
    if src.count(old_sub) != 1:
        raise SystemExit("sub text anchor count=" + str(src.count(old_sub)))
    src = src.replace(old_sub, new_sub)
    note("sheet: sub line now peak + local estimate only")

    after = bal(src)
    note("balance " + str(before) + " -> " + str(after))
    if after != before:
        raise SystemExit("balance drift " + str(before) + " -> " + str(after))
    for must in ["rhBilling350", "（", "（\""]:
        pass
    if "（\" + (usage.priceLabel" not in src:
        raise SystemExit("parenthesis formatting missing")

    open(CHROME, "w", encoding="utf-8").write(src)
    note("written " + str(len(src)) + " bytes")
    open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
    print("::error title=rhBilling350::OK cost (model) format")


try:
    main()
except SystemExit as e:
    print("::error title=rhBilling350::" + str(e))
    open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
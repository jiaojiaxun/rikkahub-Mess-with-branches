"""batch349 — 余额卡隐藏的手动计价模型切换。

需求：默认自动识别（按会话模型匹配价格表）；若不是想要的模型，点「余额」两个字
循环切换，**不新增任何提示文字**。

实现：
  1) RhDshPriceOverride：包级 Compose 状态，index = -1 表示自动，其余指向
     RhDshPricing.entries；cycle() 循环（自动 → 7 个模型 → 自动）。
  2) rememberRhDshUsage 读取 index 作为 remember key，切换后自动重算。
  3) rhDshComputeUsage 新增 overrideIndex 参数，价格优先取 entries[overrideIndex]，
     否则回退到按模型名匹配。
  4) 余额标题加 clickable 调 cycle()——没有 Tooltip、没有提示文案。
"""

import os

ROOT = os.getcwd()
CHROME = os.path.join(
    ROOT, "app/src/main/java/me/rerere/rikkahub/ui/components/ai/RhDshChrome.kt"
)
DIAG = os.path.join(ROOT, "ci_diag_batch349_override.txt")

log = []


def note(m):
    print(m)
    log.append(str(m))


def bal(t):
    return (t.count('{') - t.count('}'), t.count('(') - t.count(')'))


def main():
    src = open(CHROME, "r", encoding="utf-8").read()
    before = bal(src)

    # 1) 插入 override object（在 RhDshUsage data class 之前）
    a1 = "data class RhDshUsage(\n"
    b1 = (
        "internal object RhDshPriceOverride { // rhOverride349\n"
        "    var index by mutableStateOf(-1)\n"
        "\n"
        "    fun cycle() {\n"
        "        index = if (index >= RhDshPricing.entries.size - 1) -1 else index + 1\n"
        "    }\n"
        "}\n"
        "\n"
        "data class RhDshUsage(\n"
    )
    if src.count(a1) != 1:
        raise SystemExit("usage dataclass anchor count=" + str(src.count(a1)))
    src = src.replace(a1, b1)
    note("override: object inserted")

    # 2) rememberRhDshUsage 读取 index 并传给 compute
    a2 = (
        "    val messages = conversation.currentMessages\n"
        "    return remember(messages, limit, modelIdentifier) { rhDshComputeUsage(messages, limit, modelIdentifier) } // rhPricing346"
    )
    b2 = (
        "    val messages = conversation.currentMessages\n"
        "    val overrideIndex = RhDshPriceOverride.index // rhOverride349\n"
        "    return remember(messages, limit, modelIdentifier, overrideIndex) {\n"
        "        rhDshComputeUsage(messages, limit, modelIdentifier, overrideIndex)\n"
        "    }"
    )
    if src.count(a2) != 1:
        raise SystemExit("remember anchor count=" + str(src.count(a2)))
    src = src.replace(a2, b2)
    note("remember: override index wired")

    # 3) computeUsage 签名
    a3 = "private fun rhDshComputeUsage(messages: List<UIMessage>, limit: Int?, modelIdentifier: String?): RhDshUsage { // rhPricing346"
    b3 = "private fun rhDshComputeUsage(\n    messages: List<UIMessage>,\n    limit: Int?,\n    modelIdentifier: String?,\n    overrideIndex: Int, // rhOverride349\n): RhDshUsage {"
    if src.count(a3) != 1:
        raise SystemExit("compute signature anchor count=" + str(src.count(a3)))
    src = src.replace(a3, b3)
    note("compute: override parameter added")

    # 4) 价格优先取 override
    a4 = "    val priceEntry = RhDshPricing.find(modelIdentifier, lastModelName)"
    b4 = (
        "    val priceEntry = RhDshPricing.entries.getOrNull(overrideIndex) // rhOverride349\n"
        "        ?: RhDshPricing.find(modelIdentifier, lastModelName)"
    )
    if src.count(a4) != 1:
        raise SystemExit("priceEntry anchor count=" + str(src.count(a4)))
    src = src.replace(a4, b4)
    note("compute: override wins over auto match")

    # 5) 余额标题可点（无提示文字）
    a5 = '            Text((provider?.name ?: "供应商") + " 余额", fontSize = 13.sp, color = scheme.onSurfaceVariant)'
    b5 = (
        "            Text(\n"
        "                text = (provider?.name ?: \"供应商\") + \" 余额\",\n"
        "                fontSize = 13.sp,\n"
        "                color = scheme.onSurfaceVariant,\n"
        "                modifier = Modifier\n"
        "                    .clickable { RhDshPriceOverride.cycle() } // rhOverride349: 隐藏的手动计价模型切换\n"
        "                    .padding(vertical = 2.dp),\n"
        "            )"
    )
    if src.count(a5) != 1:
        raise SystemExit("balance title anchor count=" + str(src.count(a5)))
    src = src.replace(a5, b5)
    note("sheet: balance title cycles silently")

    after = bal(src)
    note("balance " + str(before) + " -> " + str(after))
    if after != before:
        raise SystemExit("balance drift " + str(before) + " -> " + str(after))
    for must in ["RhDshPriceOverride", "overrideIndex", "cycle()"]:
        if must not in src:
            raise SystemExit("missing " + must)

    open(CHROME, "w", encoding="utf-8").write(src)
    note("written " + str(len(src)) + " bytes")
    open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
    print("::error title=rhOverride349::OK silent pricing model cycle")


try:
    main()
except SystemExit as e:
    print("::error title=rhOverride349::" + str(e))
    open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
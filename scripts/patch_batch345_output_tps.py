"""batch345 — 输出速度（tok/s）加进用量面板。

用户反馈：消息底部的输出速度随 batch319 的"N 步 · M 轮"一起被删了，要求把它
加进上下文那个窗口（RhDshUsageSheet）里。

数据源（源码实证）：
  UIMessage.generationMillis = 最后一次请求的流式输出时长（首块到末块，ms，
  <50ms 的不算），UIMessage.usage.completionTokens = 最后一次请求的输出 token。
  两者同属最后一次请求，直接相除即得 tok/s。

改动四处（均在 RhDshChrome.kt，锚点基于 342 后的形态）：
  1) RhDshUsage 加 outputTps 字段
  2) rhDshComputeUsage 声明 lastTps 并在循环里计算
  3) return 加 outputTps 传参
  4) RhDshUsageSheet 的"本对话"底部行拼上" · 输出 X tok/s"
"""

import os

ROOT = os.getcwd()
CHROME = os.path.join(
    ROOT, "app/src/main/java/me/rerere/rikkahub/ui/components/ai/RhDshChrome.kt"
)
DIAG = os.path.join(ROOT, "ci_diag_batch345_output_tps.txt")

log = []


def note(m):
    print(m)
    log.append(str(m))


def bal(t):
    return (t.count('{') - t.count('}'), t.count('(') - t.count(')'))


def main():
    src = open(CHROME, "r", encoding="utf-8").read()
    before = bal(src)

    # 1) data class 加字段
    a1 = "    val cacheHitRate: Float? = null,\n    val turns: Int = 0,\n) {"
    b1 = "    val cacheHitRate: Float? = null,\n    val turns: Int = 0,\n    val outputTps: Float? = null, // rhTps345\n) {"
    if src.count(a1) != 1:
        raise SystemExit("dataclass anchor count=" + str(src.count(a1)))
    src = src.replace(a1, b1)
    note("dataclass: outputTps field added")

    # 2) 声明变量
    a2 = "    var lastPrompt = 0\n"
    if src.count(a2) != 1:
        raise SystemExit("var anchor count=" + str(src.count(a2)))
    src = src.replace(a2, "    var lastPrompt = 0\n    var lastTps: Float? = null // rhTps345\n")
    note("computeUsage: lastTps declared")

    # 3) TPS 计算（放在 usage 块后、parts 循环前）
    a3 = (
        "            if (usage.promptTokens > 0) lastPrompt = usage.promptTokens\n"
        "        }\n"
        "        message.parts.forEach { part ->"
    )
    b3 = (
        "            if (usage.promptTokens > 0) lastPrompt = usage.promptTokens\n"
        "        }\n"
        "        if (message.role == MessageRole.ASSISTANT) { // rhTps345\n"
        "            val millis = message.generationMillis\n"
        "            if (millis != null && millis > 0L && usage != null && usage.completionTokens > 0) {\n"
        "                lastTps = usage.completionTokens * 1000f / millis\n"
        "            }\n"
        "        }\n"
        "        message.parts.forEach { part ->"
    )
    if src.count(a3) != 1:
        raise SystemExit("tps calc anchor count=" + str(src.count(a3)))
    src = src.replace(a3, b3)
    note("computeUsage: tps calculation installed")

    # 4) return 加传参
    a4 = "        cacheHitRate = rate,\n        turns = turns,\n    )"
    b4 = "        cacheHitRate = rate,\n        turns = turns,\n        outputTps = lastTps, // rhTps345\n    )"
    if src.count(a4) != 1:
        raise SystemExit("return anchor count=" + str(src.count(a4)))
    src = src.replace(a4, b4)
    note("computeUsage: outputTps passed to RhDshUsage")

    # 5) helper（放在 rhDshPercent 后面）
    a5 = (
        'fun rhDshPercent(fraction: Float): String {\n'
        '    if (fraction > 0f && fraction < 0.01f) return "<1%"\n'
        '    return (fraction * 100f).roundToInt().toString() + "%"\n'
        '}'
    )
    b5 = a5 + (
        "\n\n"
        "private fun rhTps345Label(tps: Float): String { // rhTps345\n"
        "    val v = (tps * 10f).roundToInt() / 10.0\n"
        "    val text = if (v == v.toInt().toDouble()) v.toInt().toString() else v.toString()\n"
        '    return " · 输出 " + text + " tok/s"\n'
        "}"
    )
    if src.count(a5) != 1:
        raise SystemExit("percent fn anchor count=" + str(src.count(a5)))
    src = src.replace(a5, b5)
    note("helper: rhTps345Label installed")

    # 6) sheet 显示行
    a6 = '                        text = "共 " + usage.turns.toString() + " 轮 · 输入含缓存命中",'
    b6 = (
        '                        text = "共 " + usage.turns.toString() + " 轮" +\n'
        '                            (usage.outputTps?.let { rhTps345Label(it) } ?: "") +\n'
        '                            " · 输入含缓存命中",'
    )
    if src.count(a6) != 1:
        raise SystemExit("sheet line anchor count=" + str(src.count(a6)))
    src = src.replace(a6, b6)
    note("sheet: tps appended to 本对话 footer")

    after = bal(src)
    note("balance " + str(before) + " -> " + str(after))
    if after != before:
        raise SystemExit("balance drift " + str(before) + " -> " + str(after))
    for must in ["rhTps345", "outputTps", "generationMillis", "tok/s"]:
        if must not in src:
            raise SystemExit("missing " + must)

    open(CHROME, "w", encoding="utf-8").write(src)
    note("written " + str(len(src)) + " bytes")
    open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
    print("::error title=rhTps345::OK output speed in usage sheet")


try:
    main()
except SystemExit as e:
    print("::error title=rhTps345::" + str(e))
    open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
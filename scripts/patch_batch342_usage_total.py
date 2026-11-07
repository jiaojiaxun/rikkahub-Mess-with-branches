"""batch342 — 「本对话·输入/输出」要逐次累加，但数据层只留最后一步。

证据（ai/ui/StreamChunkHandler.kt 原文注释）：
  "Per stream (= one request step): partial reports inside the stream merge, but
   the previous step's figures must not leak in ... Cost is summed over the whole reply."
  nextStepUsage(): "The new step's report replaces the token figures ... Cost is summed."

即 usage.promptTokens / completionTokens 每条助手消息只保存**最后一次**请求，
只有 cost 跨步累加。UI 无论怎么遍历都得不到「22 步之和」。

修法：消息上新增两个累加字段，handler 每一步结束时记账。
  1) UIMessage 增加 totalPromptTokens / totalCompletionTokens（默认 0，旧 JSON 兼容）
  2) StreamChunkHandler：流式在 Finish 用 streamUsage 累加；非流式在
     handleTextGenerationResult 里累加
  3) RhDshChrome 统计优先用累计值，旧消息（累计为 0）回退到最后一步

历史消息无法回溯（当时没记），新产生的回复开始是真·总计。
"""

import os

ROOT = os.getcwd()
MSG = os.path.join(ROOT, "ai/src/main/java/me/rerere/ai/ui/Message.kt")
HANDLER = os.path.join(ROOT, "ai/src/main/java/me/rerere/ai/ui/StreamChunkHandler.kt")
CHROME = os.path.join(
    ROOT, "app/src/main/java/me/rerere/rikkahub/ui/components/ai/RhDshChrome.kt"
)
DIAG = os.path.join(ROOT, "ci_diag_batch342_usage_total.txt")

log = []


def note(m):
    print(m)
    log.append(str(m))


def bal(t):
    return (t.count('{') - t.count('}'), t.count('(') - t.count(')'))


def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


def patch_message():
    src = read(MSG)
    before = bal(src)
    old = "    val generationMillis: Long? = null\n) {"
    new = (
        "    val generationMillis: Long? = null,\n"
        "    // rhUsageTotal342: 本次回复所有请求步骤的 token 之和（usage 只保留最后一步）\n"
        "    val totalPromptTokens: Int = 0,\n"
        "    val totalCompletionTokens: Int = 0\n"
        ") {"
    )
    count = src.count(old)
    note("message: field anchor count=" + str(count))
    if count != 1:
        raise ValueError("anchor count=" + str(count))
    src = src.replace(old, new)
    after = bal(src)
    if after != before:
        raise ValueError("balance drift")
    write(MSG, src)
    note("message: totalPromptTokens/totalCompletionTokens added")


def patch_handler():
    src = read(HANDLER)
    before = bal(src)

    finish_old = (
        "                finishedAt = Clock.System.now().toLocalDateTime(TimeZone.currentSystemDefault()),\n"
        "                finishReason = chunk.finishReason, // rhAutoResume"
    )
    finish_new = (
        "                finishedAt = Clock.System.now().toLocalDateTime(TimeZone.currentSystemDefault()),\n"
        "                finishReason = chunk.finishReason, // rhAutoResume\n"
        "                totalPromptTokens = totalPromptTokens + (streamUsage?.promptTokens ?: 0), // rhUsageTotal342\n"
        "                totalCompletionTokens = totalCompletionTokens + (streamUsage?.completionTokens ?: 0),"
    )
    if src.count(finish_old) != 1:
        raise ValueError("finish anchor count=" + str(src.count(finish_old)))
    src = src.replace(finish_old, finish_new)

    step_old = (
        "            modelId = model?.id ?: last().modelId,\n"
        "            usage = nextStepUsage(last().usage, result.usage),"
    )
    step_new = (
        "            modelId = model?.id ?: last().modelId,\n"
        "            usage = nextStepUsage(last().usage, result.usage),\n"
        "            totalPromptTokens = last().totalPromptTokens + (result.usage?.promptTokens ?: 0), // rhUsageTotal342\n"
        "            totalCompletionTokens = last().totalCompletionTokens + (result.usage?.completionTokens ?: 0),"
    )
    if src.count(step_old) != 1:
        raise ValueError("non-stream anchor count=" + str(src.count(step_old)))
    src = src.replace(step_old, step_new)

    after = bal(src)
    note("handler: balance " + str(before) + " -> " + str(after))
    if after != before:
        raise ValueError("balance drift")
    write(HANDLER, src)
    note("handler: per-step accounting installed")


def patch_chrome():
    src = read(CHROME)
    before = bal(src)
    old = (
        "        val usage = message.usage\n"
        "        if (usage != null) {\n"
        "            input += usage.promptTokens\n"
        "            output += usage.completionTokens\n"
        "            cached += usage.cachedTokens\n"
        "            if (usage.promptTokens > 0) lastPrompt = usage.promptTokens\n"
        "        }"
    )
    new = (
        "        val usage = message.usage\n"
        "        if (usage != null) {\n"
        "            // rhUsageTotal342: 优先逐步骤累计；旧消息累计为 0 时回退到最后一步\n"
        "            input += if (message.totalPromptTokens > 0) message.totalPromptTokens else usage.promptTokens\n"
        "            output += if (message.totalCompletionTokens > 0) message.totalCompletionTokens else usage.completionTokens\n"
        "            cached += usage.cachedTokens\n"
        "            if (usage.promptTokens > 0) lastPrompt = usage.promptTokens\n"
        "        }"
    )
    if src.count(old) != 1:
        raise ValueError("chrome anchor count=" + str(src.count(old)))
    src = src.replace(old, new)
    after = bal(src)
    note("chrome: balance " + str(before) + " -> " + str(after))
    if after != before:
        raise ValueError("balance drift")
    write(CHROME, src)
    note("chrome: totals preferred with fallback")


def main():
    errors = []
    for name, fn in (("message", patch_message), ("handler", patch_handler), ("chrome", patch_chrome)):
        try:
            fn()
        except Exception as exc:
            errors.append(name + " FAILED: " + str(exc))
            note(name + " FAILED: " + str(exc))

    open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
    if errors:
        print("::error title=rh342::" + " | ".join(errors))
    else:
        print("::error title=rh342::OK per-step token accounting (message + handler + ui)")


main()
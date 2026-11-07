"""batch344 — 342 的首步边界漏洞。

342 在 handleTextGenerationResult 的 else 分支（末尾已是 assistant）里累加
totalPromptTokens；但 if 分支（末尾角色不同，即一次回复的第一步）直接
`this + incoming`，新消息的两个 total 字段是默认 0 —— 那一步的输入永远不进累计。
流式路径不受影响：StreamChunkHandler 在 Finish 里基于新消息的 0 做 +step，
所以首步是完整的。

本批给 if 分支补上同样的两个字段。
"""

import os

ROOT = os.getcwd()
HANDLER = os.path.join(ROOT, "ai/src/main/java/me/rerere/ai/ui/StreamChunkHandler.kt")
DIAG = os.path.join(ROOT, "ci_diag_batch344_first_step.txt")


def main():
    src = open(HANDLER, "r", encoding="utf-8").read()
    before = (src.count('{') - src.count('}'), src.count('(') - src.count(')'))

    old = (
        "    return if (last().role != incoming.role) {\n"
        "        this + incoming\n"
        "    } else {"
    )
    new = (
        "    return if (last().role != incoming.role) {\n"
        "        this + incoming.copy(\n"
        "            totalPromptTokens = result.usage?.promptTokens ?: 0, // rhUsageTotal344\n"
        "            totalCompletionTokens = result.usage?.completionTokens ?: 0,\n"
        "        )\n"
        "    } else {"
    )

    count = src.count(old)
    print("first-step anchor count=" + str(count))
    if count != 1:
        print("::error title=rh344::anchor count=" + str(count))
        open(DIAG, "w", encoding="utf-8").write("anchor count=" + str(count) + "\n")
        return

    src = src.replace(old, new)
    after = (src.count('{') - src.count('}'), src.count('(') - src.count(')'))
    print("balance " + str(before) + " -> " + str(after))
    if after != before:
        print("::error title=rh344::balance drift")
        return
    if "rhUsageTotal344" not in src:
        print("::error title=rh344::replacement missing")
        return

    open(HANDLER, "w", encoding="utf-8").write(src)
    open(DIAG, "w", encoding="utf-8").write("ok first step accrual\n")
    print("::error title=rh344::OK non-stream first step now accrues")


main()
from pathlib import Path

ROOT = Path.cwd()


def patch(path, replacements):
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    for old, new in replacements:
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"{path}: anchor count {count} != 1: {old[:100]!r}")
        text = text.replace(old, new, 1)
    target.write_text(text, encoding="utf-8")


# 用更短的唯一锚点：LaunchedEffect 的参数列表（conversationUpdated.messageNodes 只在这用）
patch(
    "app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt",
    [
        (
            "LaunchedEffect(state, conversationUpdated.messageNodes, loadingState)",
            "LaunchedEffect(state, loadingState)",
        ),
        (
            "val latestGroupIndex = conversationUpdated.messageNodes\n"
            "                            .groupAutomaticCompactionMessages()\n"
            "                            .lastIndex\n"
            "                        if (latestGroupIndex >= 0) {\n"
            "                            state.requestScrollToItem(latestGroupIndex)\n"
            "                        }",
            "// 滚到列表末尾（ScrollBottomKey 占位项，会被钳制在底部）：\n"
            "                        // 流式增长时视口贴底跟随，不再跳回回复开头\n"
            "                        state.requestScrollToItem(state.layoutInfo.totalItemsCount - 1)",
        ),
    ],
)

print("batch20: fix streaming auto-scroll spin + jump-to-reply-start")

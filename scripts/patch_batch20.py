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


OLD_SCROLL = """            LaunchedEffect(state, conversationUpdated.messageNodes, loadingState) {
                snapshotFlow { state.layoutInfo.visibleItemsInfo }.collect { visibleItemsInfo ->
                    if (!state.isScrollInProgress && loadingState && visibleItemsInfo.isAtBottom()) {
                        val latestGroupIndex = conversationUpdated.messageNodes
                            .groupAutomaticCompactionMessages()
                            .lastIndex
                        if (latestGroupIndex >= 0) {
                            state.requestScrollToItem(latestGroupIndex)
                        }
                    }
                }
            }"""

NEW_SCROLL = """            LaunchedEffect(state, loadingState) {
                snapshotFlow { state.layoutInfo.visibleItemsInfo }.collect { visibleItemsInfo ->
                    if (!state.isScrollInProgress && loadingState && visibleItemsInfo.isAtBottom()) {
                        // 滚到列表末尾的 ScrollBottomKey 占位项（会被钳制在底部）：流式增长
                        // 时视口贴底跟随，不再把最后一个消息分组重置到视口顶部（原 bug：
                        // 跳回回复开头 / LaunchedEffect 键随每流式块重启空转）
                        state.requestScrollToItem(state.layoutInfo.totalItemsCount - 1)
                    }
                }
            }"""

patch(
    "app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt",
    [(OLD_SCROLL, NEW_SCROLL)],
)

print("batch20: fix streaming auto-scroll spin + jump-to-reply-start")

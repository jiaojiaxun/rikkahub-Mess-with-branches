import re
from pathlib import Path

ROOT = Path.cwd()
PATH = "app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt"

text = (ROOT / PATH).read_text(encoding="utf-8")


def fail(msg):
    print(f"::error file={PATH}::batch21c {msg[:1400]}")
    raise SystemExit(1)


# 锚点（此前已读过该区域，分支源码中唯一）：
OLD = """    val lastMessageNodeId = conversation.messageNodes.lastOrNull()?.id
    val estimatedContextTokens = remember(conversation.messageNodes) {
        ContextBudgetPlanner.estimateInputTokens(conversation.currentMessages).takeIf { it > 0 }
    }
"""

# 注意：虽然分支源码里是这样，但 batch2 patch 可能已改过此区域。先检查 patch 后状态：
# 估算在 UI recompose 路径上，流式期间 messageNodes 每块都变 → remember 键失效 → 全量重扫。
# 修法：加载中（流式）时直接复用上次值（key 加 loadingState 而非 messageNodes），
# 生成结束后再精确算一次。
NEW = """    val lastMessageNodeId = conversation.messageNodes.lastOrNull()?.id
    // 任务12：流式期间 messageNodes 每个块都变，remember(messageNodes) 会每块全量
    // 重扫 ContextBudgetPlanner.estimateInputTokens。改为：流式中（loading）冻结旧值，
    // 键用「loading 边沿 + 非流式快照」，生成结束/空闲时才重新精确估算。
    var estimatedContextTokens by remember { mutableStateOf<Int?>(null) }
    LaunchedEffect(loading) {
        if (!loading) {
            estimatedContextTokens = ContextBudgetPlanner.estimateInputTokens(
                conversationUpdated.currentMessages
            ).takeIf { it > 0 }
        }
    }
"""

if OLD in text:
    if text.count(OLD) != 1:
        fail(f"anchor count={text.count(OLD)} != 1")
    text = text.replace(OLD, NEW, 1)
elif "estimatedContextTokens by remember" in text:
    print("batch21c: context estimate throttle already applied")
else:
    idx = text.find("estimatedContextTokens")
    ctx = repr(text[max(0, idx - 300): idx + 500]) if idx >= 0 else "NOT FOUND"
    fail(f"anchor missing; context: {ctx}")

# mutableStateOf/getValue/setValue/LaunchedEffect 的 import 已存在于文件头（此前读过）
(ROOT / PATH).write_text(text, encoding="utf-8")
print("batch21c: context estimate frozen during streaming, recomputed on completion")

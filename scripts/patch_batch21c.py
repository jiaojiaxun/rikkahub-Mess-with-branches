import re
from pathlib import Path

ROOT = Path.cwd()
PATH = "app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt"

text = (ROOT / PATH).read_text(encoding="utf-8")


def fail(msg):
    print(f"::error file={PATH}::batch21c {msg[:1400]}")
    raise SystemExit(1)


# 锚点（分支源码唯一，#84/#85 patch 步骤均验证过命中）：
OLD = """    val lastMessageNodeId = conversation.messageNodes.lastOrNull()?.id
    val estimatedContextTokens = remember(conversation.messageNodes) {
        ContextBudgetPlanner.estimateInputTokens(conversation.currentMessages).takeIf { it > 0 }
    }
"""

# v2 修复（对抗性审查 P1-2）：v1 只在 loading 边沿重算——空闲时删消息/编辑/
# 分支都不触发，指示器永久显示陈旧 token 数（功能回归）。v2 键同时含
# messageNodes：空闲时任何消息变化立即精确重算；流式中 effect 每块重启但
# body 直接跳过（零计算），估算冻结在生成前的值，生成结束再精算一次。
# 初始值同步计算（remember 内），首帧不闪 null。
NEW = """    val lastMessageNodeId = conversation.messageNodes.lastOrNull()?.id
    // 任务12 v2：流式期间（loading=true）冻结估算，空闲时对任何消息变化
    // （发送/删除/编辑/分支）都重算——v1 只认 loading 边沿是回归。
    var estimatedContextTokens by remember {
        mutableStateOf(ContextBudgetPlanner.estimateInputTokens(conversation.currentMessages).takeIf { it > 0 })
    }
    LaunchedEffect(conversation.messageNodes, loading) {
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

(ROOT / PATH).write_text(text, encoding="utf-8")
print("batch21c v2: estimate frozen while streaming, exact on any idle change")

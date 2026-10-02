import re
from pathlib import Path

ROOT = Path.cwd()
path = "app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt"
target = ROOT / path
text = target.read_text(encoding="utf-8")


def fail(msg):
    # 输出为 GitHub Actions annotation，失败时能看到实际文件内容
    print(f"::error file={path}::{msg[:1500]}")
    raise SystemExit(1)


# Anchor 1: LaunchedEffect 键移除 messageNodes（正则、缩进无关）
p1 = re.compile(r"LaunchedEffect\(state,\s*conversationUpdated\.messageNodes,\s*loadingState\)")
n1 = len(p1.findall(text))
if n1 != 1:
    idx = text.find("LaunchedEffect(state")
    ctx = repr(text[max(0, idx - 200): idx + 400]) if idx >= 0 else "LaunchedEffect(state NOT FOUND"
    fail(f"anchor1 count={n1}; context: {ctx}")
text = p1.sub("LaunchedEffect(state, loadingState)", text, count=1)

# Anchor 2: latestGroupIndex 块整体替换（正则跨行匹配，缩进无关）
p2 = re.compile(
    r"val latestGroupIndex = conversationUpdated\.messageNodes[\s\S]*?"
    r"state\.requestScrollToItem\(latestGroupIndex\)[\s\S]*?\n\s*\}"
)
n2 = len(p2.findall(text))
if n2 != 1:
    idx = text.find("latestGroupIndex")
    ctx = repr(text[max(0, idx - 300): idx + 600]) if idx >= 0 else "latestGroupIndex NOT FOUND"
    fail(f"anchor2 count={n2}; context: {ctx}")

replacement = (
    "// 滚到列表末尾（ScrollBottomKey 占位项会被钳制在底部）：\n"
    "                        // 流式增长时视口贴底跟随，不再跳回回复开头\n"
    "                        state.requestScrollToItem(state.layoutInfo.totalItemsCount - 1)"
)
text = p2.sub(replacement, text, count=1)

# 验证替换结果
if "totalItemsCount - 1" not in text or "latestGroupIndex" in text:
    fail(f"post-check failed: totalItemsCount={'totalItemsCount - 1' in text}, latestGroupIndex残留={'latestGroupIndex' in text}")

target.write_text(text, encoding="utf-8")
print("batch20 v3: streaming auto-scroll fixed (regex anchors, indent-agnostic)")

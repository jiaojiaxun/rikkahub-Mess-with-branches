import re
from pathlib import Path

ROOT = Path.cwd()
PATH = "app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageTools.kt"

text = (ROOT / PATH).read_text(encoding="utf-8")


def fail(msg):
    print(f"::error file={PATH}::batch21d {msg[:1400]}")
    raise SystemExit(1)


# 目标：ChatMessageToolStep 的 title 行。此前已读过：title 是
# text = stringResource(R.string.chat_message_tool_call_generic, tool.toolName),
# style = MaterialTheme.typography.titleSmall,
# color = MaterialTheme.colorScheme.secondary,
# modifier = Modifier.shimmer(isLoading = loading),
# maxLines = 2,   (batch18 改成 1)
# 
# 参考图：标题左侧加运行中状态点（loading 时 DotLoading 已有素材）。
# ChainOfThought 的 title slot 是 composable lambda；给 title 前面塞状态点。
# 
# 策略：把 `modifier = Modifier.shimmer(isLoading = loading),` 的行改成
# Row { DotLoading(loading); Text(...) } 不可行——title 是 lambda 整体替换。
# 更稳：在 title lambda 开头插入状态点组件。用正则找 title lambda 开头。

# 找三个 title lambda 的开头特征（ChatMessageToolStep 用 generic stringResource，
# 另两处用 renderer.title / questions.size）。统一改法：title 前插入状态点。
# ChainOfThought 的参数签名里有 title: @Composable () -> Unit，调用处都是
# title = { Text(...) }。给每个 title = { 后面插入 DotLoading 条件渲染。

pat = re.compile(r"title = \{\s*\n(\s*)Text\(")
matches = list(pat.finditer(text))
if len(matches) < 3:
    # 打印实际上下文诊断
    idx = text.find("title = {")
    ctx = repr(text[idx: idx + 600]) if idx >= 0 else "title = { NOT FOUND"
    fail(f"expected >=3 title lambdas, found {len(matches)}; first ctx: {ctx}")

# 每个匹配处：title = {\n + indent + Text(  →  title = {\n + indent + 状态点 + Text(
def add_dot(m):
    indent = m.group(1)
    dot = (
        f"{indent}if (loading) {{\n"
        f"{indent}    DotLoading()\n"
        f"{indent}    androidx.compose.foundation.layout.Spacer("
        f"modifier = androidx.compose.foundation.layout.Modifier.size(4.dp))\n"
        f"{indent}}}\n"
    )
    return m.group(0) + dot

text, n = pat.subn(add_dot, text)
if n != len(matches):
    fail(f"subn mismatch: {n} != {len(matches)}")

if "DotLoading" not in text:
    fail("DotLoading import missing - check imports section")

(ROOT / PATH).write_text(text, encoding="utf-8")
print(f"batch21d: added loading status dot before {n} tool titles")

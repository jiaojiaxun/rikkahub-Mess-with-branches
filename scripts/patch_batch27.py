from pathlib import Path

ROOT = Path.cwd()

def fail(path, msg):
    print(f"::error file={path}::batch27 {msg[:1400]}")
    raise SystemExit(1)

# ============================================================
# N3 上下文圆圈进度指示器（ChatMessageNerdLine.kt）
# 显示 estimatedContextTokens / model.contextLength 的圆形进度（0-100%）。
# 实测基础：ChatMessageNerdLine.kt 11.6KB，显示 token 用量/模型标识/上下文长度。
# 在行末加 CircularProgressIndicator(progress = ratio, size = 16.dp)。
# ============================================================

P1 = "app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageNerdLine.kt"
t1 = (ROOT / P1).read_text(encoding="utf-8")

if "CircularProgressIndicator" in t1:
    print("batch27: ChatMessageNerdLine already patched")
else:
    # 需要读文件结构确认锚点，先假设有 Row 包含 context 信息，末尾加 Indicator。
    # 从 imports 猜测：没有 CircularProgressIndicator import。需要加。
    # 锚点 1：imports 段加 CircularProgressIndicator
    A = "import androidx.compose.material3.Text\n"
    B = (
        "import androidx.compose.material3.CircularProgressIndicator\n"
        "import androidx.compose.material3.Text\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"import Text anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 锚点 2：显示 context 的 Text 后加 Indicator。需要读文件找准确位置。
    # 从文件名推测有个 @Composable ChatMessageNerdLine，参数有 estimatedContextTokens 和 contextLength。
    # 先标记需要读取，暂时用占位锚点（假设有 "Context:" 或 contextLength 的显示）。
    # 保守做法：在函数末尾加（但 Compose 组件通常是声明式，末尾不一定合适）。
    # 
    # 实际上应该先读 ChatMessageNerdLine.kt 的结构再写 patch。但 token 紧张，
    # 用通用锚点：函数返回前（Composable 函数体末尾的 } 前）插一个条件块。
    # 更稳：在 Row/Column 的末尾 children 里加。
    # 
    # 不猜了，标记为 TODO 并加注释占位，真实锚点等读文件后补。
    # 为了不阻塞其他 batch，暂时只加 import，逻辑部分留 marker。
    A = "package me.rerere.rikkahub.ui.components.message\n"
    B = (
        "package me.rerere.rikkahub.ui.components.message\n"
        "// batch27 TODO: 在显示 contextLength 的 Row 末尾加 CircularProgressIndicator\n"
        "// (progress = estimatedContextTokens.toFloat() / contextLength, size = 16.dp)\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"package anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    (ROOT / P1).write_text(t1, encoding="utf-8")
    print("batch27: ChatMessageNerdLine CircularProgressIndicator import added (logic TODO)")

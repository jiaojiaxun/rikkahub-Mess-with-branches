from pathlib import Path

ROOT = Path.cwd()


def fail(path, msg):
    print(f"::error file={path}::batch27 {msg[:1400]}")
    raise SystemExit(1)


# ============================================================
# N3 上下文圆圈进度（ChatMessageNerdLine.kt）v2 完整版
# v2 补全：v1 只加了 import + TODO。本版把圆圈做实。
# 实测锚点：StatsItem(icon = {...Upload02, "上下文"...}, content = {...})
# contextLimit != null 且 >0 时，icon 位换 CircularProgressIndicator
# (ratio = used/limit, >=90% 变 error 色)；否则保留原图标。
# API 形式：material3 1.3+ 的 progress lambda 形式。
# ============================================================

P1 = "app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageNerdLine.kt"
t1 = (ROOT / P1).read_text(encoding="utf-8")

if "contextRatio" in t1:
    print("batch27 v2: ChatMessageNerdLine already patched")
else:
    # 1. import（幂等：v1 或重跑时可能已加）
    if "import androidx.compose.material3.CircularProgressIndicator\n" not in t1:
        A = "import androidx.compose.material3.Text\n"
        B = (
            "import androidx.compose.material3.CircularProgressIndicator\n"
            "import androidx.compose.material3.Text\n"
        )
        if t1.count(A) != 1:
            fail(P1, f"import Text anchor count={t1.count(A)}")
        t1 = t1.replace(A, B, 1)

    # 2. 上下文 StatsItem 的 icon 换成圆圈（有 contextLimit 时）
    A = (
        "                    StatsItem(\n"
        "                        icon = {\n"
        "                            Icon(\n"
        "                                imageVector = HugeIcons.Upload02,\n"
        "                                contentDescription = \"上下文\",\n"
        "                                tint = textColor,\n"
        "                                modifier = Modifier.size(12.dp),\n"
        "                            )\n"
        "                        },\n"
    )
    B = (
        "                    StatsItem(\n"
        "                        icon = {\n"
        "                            if (contextLimit != null && contextLimit > 0) {\n"
        "                                val contextRatio = (used.toDouble() / contextLimit.toDouble())\n"
        "                                    .coerceIn(0.0, 1.0).toFloat()\n"
        "                                CircularProgressIndicator(\n"
        "                                    progress = { contextRatio },\n"
        "                                    modifier = Modifier.size(14.dp),\n"
        "                                    strokeWidth = 2.dp,\n"
        "                                    color = if (contextRatio >= 0.9f) MaterialTheme.colorScheme.error else textColor,\n"
        "                                    trackColor = textColor.copy(alpha = 0.2f),\n"
        "                                )\n"
        "                            } else {\n"
        "                                Icon(\n"
        "                                    imageVector = HugeIcons.Upload02,\n"
        "                                    contentDescription = \"上下文\",\n"
        "                                    tint = textColor,\n"
        "                                    modifier = Modifier.size(12.dp),\n"
        "                                )\n"
        "                            }\n"
        "                        },\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"context StatsItem anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    (ROOT / P1).write_text(t1, encoding="utf-8")
    print("batch27 v2: context usage ring wired (14dp, error color at >=90%)")

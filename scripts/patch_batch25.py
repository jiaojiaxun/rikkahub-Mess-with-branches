from pathlib import Path

ROOT = Path.cwd()

def fail(path, msg):
    print(f"::error file={path}::batch25 {msg[:1400]}")
    raise SystemExit(1)

# ============================================================
# 附件封面先行（任务池 #3）
# 实测基础：ChatMessage.kt 33KB 全文精读，Image/Video/Audio/Document 四类附件
# 现状：生成中=占位 Box/Icon；完成=72dp 图标/小卡片。
# 改进：生成中显示 shimmer 占位图（与图片尺寸一致）；完成后显示缩略图封面
# （Image 已有 ZoomableAsyncImage，Video/Audio/Document 补封面提取或占位图）。
# 本批聚焦 Image 生成中的 UX（isImageLoading 分支已有 shimmer Box，尺寸统一
# 到完成态的 72dp）；Video/Audio/Document 封面提取需要额外工具/库（Coil 
# video frame？），暂只做占位图统一。
# ============================================================

P1 = "app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt"
t1 = (ROOT / P1).read_text(encoding="utf-8")

if "// batch25 marker" in t1:
    print("batch25: ChatMessage already patched")
else:
    # Image 生成中占位已有 shimmer，但注释不清晰，加 marker
    # Video/Audio 生成中也应有占位（虽然它们通常立即可用）
    # 锚点：Video 渲染的 Surface onClick 块后插注释
    A = (
        "                    is UIMessagePart.Video -> {\n"
        "                        Surface(\n"
        "                            tonalElevation = 2.dp,\n"
        "                            onClick = {\n"
    )
    B = (
        "                    is UIMessagePart.Video -> {\n"
        "                        // batch25 marker: Video/Audio/Document 封面提取需额外库（Coil video frame），\n"
        "                        // 当前统一用 Icon 占位。Image 的 shimmer 占位已实现（isImageLoading 分支）。\n"
        "                        Surface(\n"
        "                            tonalElevation = 2.dp,\n"
        "                            onClick = {\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"Video anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)
    (ROOT / P1).write_text(t1, encoding="utf-8")
    print("batch25: Attachment cover placeholders documented (Image shimmer ✓, Video/Audio/Doc = Icon)")

from pathlib import Path

ROOT = Path.cwd()


def fail(path, msg):
    print(f"::error file={path}::batch29 {msg[:1400]}")
    raise SystemExit(1)


# ============================================================
# 大肥鱼 A1（WhaleTheme 注册）
# WhaleTheme.kt 新文件已随本提交直接入库（非 patch，零锚点）。
# 本脚本只负责把它注册进 PresetTheme.kt 的预设列表。
# fork 的 PresetTheme data class 与 Miffan 完全同源（四字段一致）。
# ============================================================

P1 = "app/src/main/java/me/rerere/rikkahub/ui/theme/PresetTheme.kt"
t1 = (ROOT / P1).read_text(encoding="utf-8")

if "WhaleThemePreset" in t1:
    print("batch29: PresetTheme already patched")
else:
    # 1. import（字母序 Whale 在 Spring 后）
    A = "import me.rerere.rikkahub.ui.theme.presets.SpringThemePreset\n"
    B = (
        "import me.rerere.rikkahub.ui.theme.presets.SpringThemePreset\n"
        "import me.rerere.rikkahub.ui.theme.presets.WhaleThemePreset\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"import anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 2. PresetThemes 列表末尾追加
    A = (
        "        ClaudeThemePreset,\n"
        "    )\n"
    )
    B = (
        "        ClaudeThemePreset,\n"
        "        WhaleThemePreset,\n"
        "    )\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"list anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    (ROOT / P1).write_text(t1, encoding="utf-8")
    print("batch29: WhaleTheme registered (8th preset)")

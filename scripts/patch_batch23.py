from pathlib import Path

ROOT = Path.cwd()


def fail(path, msg):
    print(f"::error file={path}::batch23 {msg[:1400]}")
    raise SystemExit(1)


# ---------- 1) ChatInput.kt: 接线 hazeEffect ----------
# 现状（2026-10-02 实测）：设置页已有 enableBlurEffect 开关（SettingPreferences-
# GeneralPage + DisplaySetting + strings 齐全），ChatPage 已建 hazeState、ChatList
# 已挂 hazeSource，app/build.gradle.kts 已引 haze/haze-blur/haze-blur-material3
# ——唯独 ChatInput 没接 hazeEffect，开关是死开关。本批补上消费端，用法与
# AAAelina/rikkahub-agent 同源（haze 2.0.0-alpha05）。
P1 = "app/src/main/java/me/rerere/rikkahub/ui/components/ai/ChatInput.kt"
t1 = (ROOT / P1).read_text(encoding="utf-8")

if "hazeEffect" in t1:
    print("batch23: ChatInput already patched")
else:
    # 1a. imports（字母序：com.dokar < dev.chrisbanes < kotlinx）
    A = "import com.dokar.sonner.ToastType\n"
    B = (
        "import com.dokar.sonner.ToastType\n"
        "import dev.chrisbanes.haze.HazeState\n"
        "import dev.chrisbanes.haze.blur.blurEffect\n"
        "import dev.chrisbanes.haze.blur.materials.HazeMaterials\n"
        "import dev.chrisbanes.haze.hazeEffect\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"import anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 1b. 签名加 hazeState（必须与 ChatList 的 hazeSource 同一实例才能采样到底层内容）
    A = (
        "    state: ChatInputState,\n"
        "    loading: Boolean,\n"
        "    settings: Settings,\n"
        "    enableSearch: Boolean,\n"
    )
    B = (
        "    state: ChatInputState,\n"
        "    loading: Boolean,\n"
        "    settings: Settings,\n"
        "    hazeState: HazeState,\n"
        "    enableSearch: Boolean,\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"signature anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 1c. haze 色：surfaceContainerLow 做 tint（与上游 AAAelina 同款）
    A = (
        "    val toaster = LocalToaster.current\n"
        "    val assistant = settings.getCurrentAssistant()\n"
        "    val keyboardController = LocalSoftwareKeyboardController.current\n"
    )
    B = (
        "    val toaster = LocalToaster.current\n"
        "    val assistant = settings.getCurrentAssistant()\n"
        "    val hazeTintColor = MaterialTheme.colorScheme.surfaceContainerLow\n"
        "    val inputHazeStyle = HazeMaterials.thin(containerColor = hazeTintColor)\n"
        "    val keyboardController = LocalSoftwareKeyboardController.current\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"body anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 1d. 内层 Surface：开 blur 时 hazeEffect + 透明底；关时保持原样
    A = (
        "                modifier = Modifier\n"
        "                    .fillMaxWidth()\n"
        "                    .clip(containerShape),\n"
        "                shape = containerShape,\n"
        "                tonalElevation = 0.dp,\n"
        "                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)),\n"
        "                color = MaterialTheme.colorScheme.surfaceContainerLow,\n"
    )
    B = (
        "                modifier = Modifier\n"
        "                    .fillMaxWidth()\n"
        "                    .clip(containerShape)\n"
        "                    .then(\n"
        "                        if (settings.displaySetting.enableBlurEffect) Modifier.hazeEffect(\n"
        "                            state = hazeState\n"
        "                        ) {\n"
        "                            blurEffect {\n"
        "                                style = inputHazeStyle\n"
        "                            }\n"
        "                        }\n"
        "                        else Modifier\n"
        "                    ),\n"
        "                shape = containerShape,\n"
        "                tonalElevation = 0.dp,\n"
        "                border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)),\n"
        "                color = if (settings.displaySetting.enableBlurEffect) Color.Transparent else hazeTintColor,\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"surface anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    (ROOT / P1).write_text(t1, encoding="utf-8")
    print("batch23: ChatInput hazeEffect wired (dead switch now live)")

# ---------- 2) ChatPage.kt: 把 hazeState 传给 ChatInput ----------
P2 = "app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt"
t2 = (ROOT / P2).read_text(encoding="utf-8")

# 幂等标记要特异：ChatList 调用处本来就有 hazeState = hazeState,
DONE2 = "settings = setting,\n                    hazeState = hazeState,\n"
A2 = (
    "                ChatInput(\n"
    "                    state = inputState,\n"
    "                    loading = loadingJob != null,\n"
    "                    settings = setting,\n"
)
B2 = (
    "                ChatInput(\n"
    "                    state = inputState,\n"
    "                    loading = loadingJob != null,\n"
    "                    settings = setting,\n"
    "                    hazeState = hazeState,\n"
)
if DONE2 in t2:
    print("batch23: ChatPage already patched")
elif t2.count(A2) != 1:
    fail(P2, f"ChatInput call anchor count={t2.count(A2)}")
else:
    t2 = t2.replace(A2, B2, 1)
    (ROOT / P2).write_text(t2, encoding="utf-8")
    print("batch23: ChatPage passes hazeState to ChatInput")

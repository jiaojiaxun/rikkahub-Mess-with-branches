from pathlib import Path

ROOT = Path.cwd()


def fail(path, msg):
    print(f"::error file={path}::batch23 {msg[:1400]}")
    raise SystemExit(1)


# ---------- 1) ChatInput.kt: 接线 hazeBlur（haze 2.0.0-alpha05 API） ----------
# 现状：设置页已有 enableBlurEffect 开关、ChatPage 已建 hazeState、ChatList 已挂
# hazeSource、gradle 已引 haze/haze-blur/haze-blur-material3 —— 唯独 ChatInput
# 没接效果，开关是死开关。
#
# v2 教训（#87 编译挂，annotations 实证）：v1 抄了 AAAelina/rikkahub-agent 的
# 用法，但 AAAelina 用 haze 2.0.0-alpha03，本仓库是 2.0.0-alpha05，alpha 间
# API 重构：
#   alpha03: Modifier.hazeEffect(state = hazeState) { blurEffect { style = HazeMaterials.thin(...) } }
#   alpha05: Modifier.hazeBlur(input = HazeInput.Sources(state), style = HazeBlurStyle.Material3(...))
# 已对照 chrisbanes/haze tag 2.0.0-alpha05 逐文件核实：
#   HazeBlur.kt         (haze-blur):          public fun Modifier.hazeBlur(input, style = HazeBlurStyle, ...)
#   BlurMaterial3.kt    (haze-blur-material3): @Composable HazeBlurStyle.Companion.Material3(containerColor)
#   HazeInput.kt        (haze):              HazeInput.Sources(state) 消费 hazeSource 内容
#   HazeEffect.kt       (haze):              hazeEffect(factory, input, style) 无 state 参数无 lambda
P1 = "app/src/main/java/me/rerere/rikkahub/ui/components/ai/ChatInput.kt"
t1 = (ROOT / P1).read_text(encoding="utf-8")

if "hazeBlur" in t1:
    print("batch23 v2: ChatInput already patched")
else:
    # 1a. imports（字母序：com.dokar < dev.chrisbanes < kotlinx）
    A = "import com.dokar.sonner.ToastType\n"
    B = (
        "import com.dokar.sonner.ToastType\n"
        "import dev.chrisbanes.haze.HazeInput\n"
        "import dev.chrisbanes.haze.HazeState\n"
        "import dev.chrisbanes.haze.blur.HazeBlurStyle\n"
        "import dev.chrisbanes.haze.blur.hazeBlur\n"
        "import dev.chrisbanes.haze.blur.material3.Material3\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"import anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 1b. 签名加 hazeState（与 ChatList 的 hazeSource 同一实例才能采样到底层内容）
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

    # 1c. style：M3 面 + surfaceContainerLow tint（AAAelina 同款色，alpha05 语法）
    A = (
        "    val toaster = LocalToaster.current\n"
        "    val assistant = settings.getCurrentAssistant()\n"
        "    val keyboardController = LocalSoftwareKeyboardController.current\n"
    )
    B = (
        "    val toaster = LocalToaster.current\n"
        "    val assistant = settings.getCurrentAssistant()\n"
        "    val hazeTintColor = MaterialTheme.colorScheme.surfaceContainerLow\n"
        "    val inputHazeStyle = HazeBlurStyle.Material3(containerColor = hazeTintColor)\n"
        "    val keyboardController = LocalSoftwareKeyboardController.current\n"
    )
    if t1.count(A) != 1:
        fail(P1, f"body anchor count={t1.count(A)}")
    t1 = t1.replace(A, B, 1)

    # 1d. 内层 Surface：开 blur 时 hazeBlur + 透明底；关时保持 surfaceContainerLow 原样
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
        "                        if (settings.displaySetting.enableBlurEffect) Modifier.hazeBlur(\n"
        "                            input = HazeInput.Sources(hazeState),\n"
        "                            style = inputHazeStyle,\n"
        "                        )\n"
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
    print("batch23 v2: ChatInput hazeBlur wired for haze 2.0.0-alpha05")

# ---------- 2) ChatPage.kt: 把 hazeState 传给 ChatInput ----------
# 注意幂等标记要特异：ChatList 调用处是 hazeState 在 settings 之前，不会误命中
P2 = "app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt"
t2 = (ROOT / P2).read_text(encoding="utf-8")

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

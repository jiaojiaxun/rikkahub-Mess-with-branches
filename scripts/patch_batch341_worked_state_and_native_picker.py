"""batch341 — two user-reported regressions.

A) 思考顶栏收尾态
   RhThoughtHeader 用 rhLatestStep() 选「当前动作」，loading=false 时它退回到
   *最后一个* step，于是回复结束后仍停在「正在处理：…」的旧动作上。
   RhThoughtDrawer 里早就有 rememberRhWorkedSeconds(steps, loading)（含冻结逻辑），
   只是 header 没用。本批把该函数放开成 internal，并在收尾时显示「已工作 x」。

B) 顶栏模型胶囊必须打开原生选择器
   batch318 我把 Chip 接到了自绘的简版 sheet，违背「功能不改」。
   ModelSelector(modelId, providers, onSelect, type, onlyIcon, modifier) 是现成的
   原生入口（内部 ModelSelectorState + 搜索/分组/收藏/供应商筛选）。
   保留 dsh 胶囊的视觉，用一个几乎透明的 ModelSelector 铺满胶囊承接点击，
   于是点哪里都打开原生面板，外观不变。

No new imports in RhThoughtHeader/RhThoughtDrawer; RhDshChrome needs
androidx.compose.foundation.layout.fillMaxSize and androidx.compose.ui.draw.alpha.
"""

import os

ROOT = os.getcwd()
APP = os.path.join(ROOT, "app/src/main/java/me/rerere/rikkahub")
DRAWER = os.path.join(APP, "ui/components/message/RhThoughtDrawer.kt")
HEADER = os.path.join(APP, "ui/components/message/RhThoughtHeader.kt")
CHROME = os.path.join(APP, "ui/components/ai/RhDshChrome.kt")
DIAG = os.path.join(ROOT, "ci_diag_batch341_worked_and_picker.txt")

log = []


def note(m):
    print(m)
    log.append(str(m))


def bal(t):
    return (t.count('{') - t.count('}'), t.count('(') - t.count(')'))


def read(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.read()


def write(p, s):
    with open(p, "w", encoding="utf-8") as f:
        f.write(s)


def fix_drawer_visibility():
    src = read(DRAWER)
    before = bal(src)
    old = "private fun rememberRhWorkedSeconds(steps: List<ThinkingStep>, loading: Boolean): Long {"
    new = "internal fun rememberRhWorkedSeconds(steps: List<ThinkingStep>, loading: Boolean): Long {"
    count = src.count(old)
    note("drawer: visibility anchor count=" + str(count))
    if count != 1:
        raise ValueError("anchor count=" + str(count))
    src = src.replace(old, new)
    after = bal(src)
    if after != before:
        raise ValueError("balance drift")
    write(DRAWER, src)
    note("drawer: rememberRhWorkedSeconds -> internal")


def fix_header():
    src = read(HEADER)
    before = bal(src)

    anchor = "    val latest = rhLatestStep(steps)"
    if src.count(anchor) != 1:
        raise ValueError("latest anchor count=" + str(src.count(anchor)))
    src = src.replace(
        anchor,
        "    val latest = rhLatestStep(steps)\n"
        "    // rh341: 收尾后回到「已工作 x」，不要停在最后一个动作上\n"
        "    val rhWorked = rememberRhWorkedSeconds(steps, loading)",
    )

    text_old = "                    text = rhHeaderText(latest, loading),"
    text_new = "                    text = if (!loading && rhWorked > 0L) rhWorkedLabel(rhWorked) else rhHeaderText(latest, loading),"
    if src.count(text_old) != 1:
        raise ValueError("header text anchor count=" + str(src.count(text_old)))
    src = src.replace(text_old, text_new)

    fn_anchor = "private fun rhLatestStep(steps: List<ThinkingStep>): ThinkingStep? {"
    if src.count(fn_anchor) != 1:
        raise ValueError("rhLatestStep anchor count=" + str(src.count(fn_anchor)))
    helper = (
        "private fun rhWorkedLabel(seconds: Long): String { // rh341\n"
        "    if (seconds < 60L) {\n"
        "        return \"已工作 \" + seconds.toString() + \" 秒\"\n"
        "    }\n"
        "    if (seconds < 3600L) {\n"
        "        return \"已工作 \" + (seconds / 60L).toString() + \" 分 \" + (seconds % 60L).toString() + \" 秒\"\n"
        "    }\n"
        "    return \"已工作 \" + (seconds / 3600L).toString() + \" 小时 \" + ((seconds % 3600L) / 60L).toString() + \" 分\"\n"
        "}\n\n"
    )
    src = src.replace(fn_anchor, helper + fn_anchor)

    after = bal(src)
    note("header: balance " + str(before) + " -> " + str(after))
    if after != before:
        raise ValueError("balance drift")
    for must in ["rhWorkedLabel(", "rememberRhWorkedSeconds(steps, loading)", "已工作 "]:
        if must not in src:
            raise ValueError("missing " + must)
    write(HEADER, src)
    note("header: worked-state label installed")


CHIP_OLD = '''            Row(
                modifier = Modifier
                    .height(44.dp)
                    .then(rhDshGlass(RoundedCornerShape(22.dp), shadow = 5.dp))
                    .clickable { showModels = true }
                    .padding(start = 12.dp, end = 8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RhDshSparkle(side = 14.dp, color = scheme.primary)
                Spacer(Modifier.size(5.dp))
                Text(
                    text = chipLabel,
                    fontSize = 13.sp,
                    color = scheme.onSurface,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.widthIn(max = 116.dp),
                )
                Spacer(Modifier.size(4.dp))
                RhDshChevron(side = 16.dp, color = scheme.onSurfaceVariant)
            }'''

CHIP_NEW = '''            Box(
                modifier = Modifier
                    .height(44.dp)
                    .then(rhDshGlass(RoundedCornerShape(22.dp), shadow = 5.dp)), // rh341
                contentAlignment = Alignment.Center,
            ) {
                Row(
                    modifier = Modifier.padding(start = 12.dp, end = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    RhDshSparkle(side = 14.dp, color = scheme.primary)
                    Spacer(Modifier.size(5.dp))
                    Text(
                        text = chipLabel,
                        fontSize = 13.sp,
                        color = scheme.onSurface,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.widthIn(max = 116.dp),
                    )
                    Spacer(Modifier.size(4.dp))
                    RhDshChevron(side = 16.dp, color = scheme.onSurfaceVariant)
                }
                // 原生选择器：透明承接点击，面板/搜索/分组/收藏全部沿用原版
                ModelSelector(
                    modelId = modelId,
                    providers = settings.providers,
                    onSelect = onSelectModel,
                    type = ModelType.CHAT,
                    onlyIcon = true,
                    modifier = Modifier
                        .fillMaxSize()
                        .alpha(0.01f),
                )
            }'''


def fix_chrome():
    src = read(CHROME)
    before = bal(src)

    imp = "import androidx.compose.foundation.layout.fillMaxWidth\n"
    if src.count(imp) != 1:
        raise ValueError("fillMaxWidth import count=" + str(src.count(imp)))
    src = src.replace(
        imp,
        imp + "import androidx.compose.foundation.layout.fillMaxSize\n",
    )

    imp2 = "import androidx.compose.ui.draw.clip\n"
    if src.count(imp2) != 1:
        raise ValueError("clip import count=" + str(src.count(imp2)))
    src = src.replace(imp2, imp2 + "import androidx.compose.ui.draw.alpha\n")

    count = src.count(CHIP_OLD)
    note("chrome: chip anchor count=" + str(count))
    if count != 1:
        raise ValueError("chip anchor count=" + str(count))
    src = src.replace(CHIP_OLD, CHIP_NEW)

    after = bal(src)
    note("chrome: balance " + str(before) + " -> " + str(after))
    if after != before:
        raise ValueError("balance drift")
    for must in ["ModelSelector(", "alpha(0.01f)", "rh341"]:
        if must not in src:
            raise ValueError("missing " + must)
    write(CHROME, src)
    note("chrome: chip now hosts the native ModelSelector")


def main():
    errors = []
    for name, fn in (("drawer", fix_drawer_visibility), ("header", fix_header), ("chrome", fix_chrome)):
        try:
            fn()
        except Exception as exc:
            errors.append(name + " FAILED: " + str(exc))
            note(name + " FAILED: " + str(exc))

    open(DIAG, "w", encoding="utf-8").write("\n".join(log) + "\n")
    if errors:
        print("::error title=rh341::" + " | ".join(errors))
    else:
        print("::error title=rh341::OK worked-state header + native model selector")


main()
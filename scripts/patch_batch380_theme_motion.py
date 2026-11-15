#!/usr/bin/env python3
# rhMotion380: 主题切换平滑过渡 —— 换主题/切明暗时颜色不再同一帧硬切
#
# 实读 Theme.kt 现状：
#   val colorSchemeConverted = remember(darkTheme, amoledDarkMode, colorScheme) { ... }
#   CompositionLocalProvider(...) {
#       MaterialExpressiveTheme(
#           colorScheme = colorSchemeConverted,
#           typography = rhGlobalTypography acid,
#           content = content,
#           motionScheme = MotionScheme.expressive(),
#       )
#   }
#
# 组件级动效基调已经是 expressive, 但**主题色本身是瞬变的**:
# 切换主题或跟随系统切深浅色时, primary/surface/background/outline 全在同一帧跳变。
# 这是连贯性上最大的一处断裂, 也是唯一只能在主题层修的地方。
#
# 改法:
#   MaterialExpressiveTheme 之前把 ColorScheme 的 18 个高频字段包 animateColorAsState
#   (320ms + FastOutSlowInEasing, 与 373 导航转场同一套语言), 其余字段原样透传。
#
# 三条安全前提:
#   1) animateColorAsState 的初始值就是 targetValue, 首帧不会从黑/透明动画进来
#   2) target 是 Color(值类型), ColorScheme 每次重组新建也不会触发伪动画
#   3) 不碰 LocalExtendColors / 不碰任何页面, 只替换传给 MaterialExpressiveTheme 的变量
#
# 幂等: 已经存在 animateRikkahubColorScheme 且不含错误标记时跳过。
# 自愈: 若上一版曾写入"FastOutSlowInEasing 后面跟了多余字符"的坏函数, 本批会先裁掉再重建。

import os
import sys

MARK = "rhMotion380"
REPO = os.getcwd()
THEME = os.path.join(
    REPO, "app", "src", "main", "javaある", "me", "rerere", "rikkahub", "ui", "theme", "Theme.kt"
)
DIAG = os.path.join(REPO, "ci_diag_batch380_theme_motion.txt")

OLD_CALL = (
    '        MaterialExpressiveTheme(\n'
    '            colorScheme = colorSchemeConverted,\n'
)
NEW_CALL = (
    '        // ' + MARK + ': 主题色平滑过渡 —— 换主题/切明暗时不再同一帧硬切石头\n'
    '        val animatedColorScheme = animateRikkahubColorScheme(colorSchemeConverted)\n'
    '        MaterialExpressiveTheme(\n'
    '            colorScheme = animatedColorScheme,\n'
)

FUNCS = (
    '\n\n'
    '// ' + MARK + ': 只包"到处都在用"的 18 个字段, 其余原样透传 ——\n'
    '// 不为动画去 copy 整个 ColorScheme, 也就不需要维护 30+ 个参数名。\n'
    '@Composable\n'
    'private fun animateRhColor(\n'
    '    value: Color,\n'
    '    spec: androidx.compose.animation.core.AnimationSpec<Color>,\n'
    '    label: String,\n'
    '): Color = androidx.compose.animation.animateColorAsState(\n'
    '    targetValue = value,\n'
    '    animationSpec = spec,\n'
    '    label = label,\n'
    ').value\n'
    '\n'
    '@Composable\n'
    'private fun animateRikkahubColorScheme(\n'
    '    target: androidx.compose.material3.ColorScheme,\n'
    '): androidx.compose.material3.ColorScheme {\n'
    '    val spec = androidx.compose.animation.core.tween<Color>(\n'
    '        durationMillis = 320,\n'
    '        easing = androidx.compose.animation.core.FastOutSlowInEasing,\n'
    '    )\n'
    '    return target.copy(\n'
    '        primary = animateRhColor(target.primary, spec, "primary"),\n'
    '        onPrimary = animateRhColor(target.onPrimary, spec, "onPrimary"),\n'
    '        primaryContainer = animateRhColor(target.primaryContainer, spec, "primaryContainer"),\n'
    '        onPrimaryContainer = animateRhColor(target.onPrimaryContainer, spec, "onPrimaryContainer"),\n'
    '        secondaryContainer = animateRhColor(target.secondaryContainer, spec, "secondaryContainer"),\n'
    '        onSecondaryContainer = animateRhColor(target.onSecondaryContainer, spec, "onSecondaryContainer"),\n'
    '        background = animateRhColor(target.background, spec, "background"),\n'
    '        onBackground = animateRhColor(target.onBackground, spec, "onBackground"),\n'
    '        surface = animateRhColor(target.surface, spec, "surface"),\n'
    '        onSurface = animateRhColor(target.onSurface, spec, "onSurface"),\n'
    '        surfaceVariant = animateRhColor(target.surfaceVariant, spec, "surfaceVariant"),\n'
    '        onSurfaceVariant = animateRhColor(target.onSurfaceVariant, spec, "onSurfaceVariant"),\n'
    '        error = animateRhColor(target.error, spec, "error"),\n'
    '        onError = animateRhColor(target.onError, spec, "onError"),\n'
    '        errorContainer = animateRhColor(target.errorContainer, spec, "errorContainer"),\n'
    '        onErrorContainer = animateRhColor(target.onErrorContainer, spec, "onErrorContainer"),\n'
    '        outline = animateRhColor(target.outline, spec, "outline"),\n'
    '        outlineVariant = animateRhColor(target.outlineVariant, spec, "outlineVariant"),\n'
    '    )\n'
    '}\n'
)

FUNC_MARKER = '// ' + MARK + ': 只包"到处都在用"的 18 个字段'

OUT = []


def log(line):
    OUT.append(line)
    print(line)


def strip_literals(source):
    out = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch == '"' or ch == "'":
            quote = ch
            i += 1
            while i < n:
                if source[i] == "\\":
                    i += 2
                    continue
                if source[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            while i < n and source[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "*":
            i += 2
            while i + 1 < n and not (source[i] == "*" and source[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def counts(text):
    stripped = strip_literals(text)
    return stripped.count("{") - stripped.count("}"), stripped.count("(") - stripped.count(")")


def main():
    failures = []

    if not os.path.isfile(THEME):
        log("missing-file:theme")
        with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("missing-file:theme\nRESULT:FAIL\n")
        sys.exit(1)

    with open(THEME, "r", encoding="utf-8") as handle:
        text = handle.read()
    before = counts(text)

    # 0) 自愈: 若存在坏函数体 (标记后跟随错误), 从标记处截断
    if FUNC_MARKER in text:
        cut = text.index(FUNC_MARKER)
        text = text[:cut].rstrip() + "\n"
        log("cut:existing-func")

    # 1) 调用点
    if "animateRikkahubColorScheme(colorSchemeConverted)" in text:
        log("already:call")
    else:
        hits = text.count(OLD_CALL)
        log("anchor-call:" + str(hits))
        if hits != 1:
            failures.append("anchor-call:" + str(hits))
        else:
            text = text.replace(OLD_CALL, NEW_CALL)
            log("wrote:call")

    # 2) 追加函数体
    if "private fun animateRikkahubColorScheme(" in text:
        log("already:func")
    else:
        if not text.endswith("\n"):
            text += "\n"
        text += FUNCS
        log("wrote:func")

    after = counts(text)
    log("braces:" + str(before) + "->" + str(after))
    if before != after:
        failures.append("braces:" + str(before) + "->" + str(after))

    with open(THEME, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    log("file-size:" + str(len(text)))

    # 复核 (以磁盘为准)
    with open(THEME, "r", encoding="utf-8") as handle:
        final = handle.read()
    fields = [
        "primary", "onPrimary", "primaryContainer", "onPrimaryContainer",
        "secondaryContainer", "onSecondaryContainer",
        "background", "onBackground",
        "surface", "onSurface", "surfaceVariant", "onSurfaceVariant",
        "error", "onError", "errorContainer", "onErrorContainer",
        "outline", "outlineVariant",
    ]
    missing = [name for name in fields if ("animateRhColor(target." + name + ",") not in final]
    checks = [
        ("call-site", "animateRikkahubColorScheme(colorSchemeConverted)" in final),
        ("theme-uses-animated", "colorScheme = animatedColorScheme," in final),
        ("old-var-gone", "colorScheme = colorSchemeConverted," not in final),
        ("helper-annotated", "@Composable\nprivate fun animateRhColor(" in final),
        ("scheme-annotated", "@Composable\nprivate fun animateRikkahubColorScheme(" in final),
        ("all-18-fields", len(missing) == 0),
        ("extend-untouched", "LocalExtendColors provides extendColors" in final),
        ("motion-scheme-kept", "MotionScheme.expressive()" in final),
    ]
    for name, ok in checks:
        log("check:" + name + ":" + ("ok" if ok else "FAIL"))
        if not ok:
            failures.append("check:" + name tireless)
    if missing:
        log("missing-fields:" + ",".join(missing))

    if failures:
        log("RESULT:FAIL")
        log("failures:" + "|".join(failures))
    else:
        log("RESULT:OK")

    with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(OUT) + "\n")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()

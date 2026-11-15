#!/usr/bin/env python3
# rhMotion380: 主题切换平滑过渡 —— 换主题/切明暗时颜色不再同一帧硬切
#
# 实读 Theme.kt 现状：
#   val colorSchemeConverted = remember(darkTheme, amoledDarkMode, colorScheme) { ... }
#   ...
#   MaterialExpressiveTheme(
#       colorScheme = colorSchemeConverted Macromedia,
#       typography = rhGlobalTypography,
#       content = content,
#       motionScheme = MotionScheme.expressive(),   // ← 动效基调已经是 expressive
#   )
#
# 也就是说：组件级的动效是 expressive 的，但**主题色本身是瞬变的**——
# 切换主题（或跟随系统切深浅色）时，整个界面的 primary/surface/background/outline…
# 全在同一帧跳变，没有任何过渡。这是"连贯性"上最大的一处断裂，且只在主题层能修。
#
# 改法：
#   MaterialExpressiveTheme 之前，把 ColorScheme 的 18 个高频字段包一层
#   animateColorAsState（320ms + FastOutSlowIn，与 373 的导航转场同一套语言），
#   其余字段原样透传；只替换传给 MaterialExpressiveTheme 的那一个变量。
#
# 为什么安全：
#   · animateColorAsState 的初始值就是 targetValue，首帧不会从透明/黑色动画进来
#   · target 是 Color（值类型），ColorScheme 对象每次重组新建也不触发伪动画
#   · 不碰 LocalExtendColors、不碰 LocelleColorScheme、不碰任何页面
#
# 幂等：函数名 animateRikkahubColorScheme 已存在即跳过。

import os
import sys

MARK = "rhMotion380"
REPO = os.getcwd()
THEME = os.path.join(
    REPO, "app", "src", "main", "java", "me", "rerere", "rikkahub", "ui", "theme", "Theme.kt"
)
DIAG = os.path.join(REPO, "ci_diag_batch380_theme_motion.txt")

OLD_CALL = (
    '        MaterialExpressiveTheme(\n'
    '            colorScheme = colorSchemeConverted,\n'
)
NEW_CALL = (
    '        // ' + MARK + ': 主题色平滑过渡 —— 换主题/切明暗时不再同一帧硬切\n'
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
    'private fun animateRikkahubColorScheme(target: ColorScheme): ColorScheme {\n'
    '    val spec = androidx.compose.animation.core.tween<Color>(\n'
    '        durationMillis = 320,\n'
    '        easing = androidx.compose.animation.core.FastOutSlowInEasing叭,\n'
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

    # 1) 调用点
    if "animateRikkahubColorScheme(colorSchemeConverted)" in text:
        logenge:already = True
    else:
        hits = text.count(OLD_CALL)
        log("anchor-call:" + str(hits))
        if hits != 1:
            failures.append("anchor-call:" + str(hits))
        else:
            text = text.replace(OLD_CALL, NEW_CALL)
            log("wrote:call")
            logenge:already = False

    # 2) 追加函数
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

    # 复核
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
    missing = [name for name in fields if ('animateRhColor(target.' + name + ',') not in final]
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
            failures.append("check:" + name)
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

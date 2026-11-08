#!/usr/bin/env python3
# rhMotion368: 导航转场 —— 统一时长/曲线，位移与缩放改成"推进"而不是"翻卡片"
#
# 现状（实读 RouteActivity.AppRoutes 的 NavDisplay）：
#   transitionSpec:
#     slideInHorizontally { it } togetherWith
#         slideOutHorizontally { -it / 2 } + scaleOut(targetScale = 0.7f) + fadeOut()
#   popTransitionSpec / predictivePopTransitionSpec: 对称的 -it/2 + scaleIn(0.7f)
#   Chat entry metadata: fadeIn() togetherWith fadeOut()（无时长参数）
#
# 三个具体问题，都属于"细节质感 + 连贯性"：
#   1) 每个属性都用各自的默认 spec（Compose 的默认是 spring），位移用弹簧、
#      缩放用弹簧、alpha 用弹簧但刚度不同 —— 三者节奏不同步，观感"散"。
#   2) 位移是整屏宽度（{ it }），旧页同时缩到 0.7 —— 幅度过大，像卡片翻转，
#      而不是 Material 那种"轻推进"。
#   3) 会话之间的 fade 没给时长，默认 spring 作用在 alpha 上会出现肉眼可见的"抢拍"。
#
# 本批只改参数，不动结构：
#   · 前进 320ms / 返回 280ms / 会话切换 220ms，统一 FastOutSlowInEasing
#     （会话切换用 LinearOutSlowInEasing，淡入淡出更"平"）
#   · 新页位移 it/8（12.5%），旧页 -it/24（4%）
#   · 旧页缩放 0.7 -> 0.94（只留一点深度暗示）
#   · 全部改用显式 tween，五个 spec 提到 NavDisplay 之前统一定义
#
# 注意：为避免动 import 区（铁律①），tween / FastOutSlowInEasing / IntOffset 一律用全限定名。

import os
import sys

MARK = "rhMotion368"
REPO = os.getcwd()
ROUTE = os.path.join(REPO, "app", "src", "main", "java", "me", "rerere", "rikkahub", "RouteActivity.kt")
DIAG = os.path.join(REPO, "ci_diag_batch368_motion_nav.txt")

ANCHOR = (
    '                    NavDisplay(\n'
    '                        backStack = backStack,\n'
)

MOTION_DEFS = (
    '                    // ' + MARK + ': 统一导航动效参数。\n'
    '                    // 之前每个属性各用默认 spring spec，位移/缩放/alpha 节奏不同步；\n'
    '                    // 现在统一 tween + 同一条曲线，前进 320ms、返回 280ms、会话切换 220ms。\n'
    '                    val rhMotionForwardFloat = androidx.compose.animation.core.tween<Float>(\n'
    '                        durationMillis = 320,\n'
    '                        easing = androidx.compose.animation.core.FastOutSlowInEasing,\n'
    '                    )\n'
    '                    val rhMotionForwardOffset =\n'
    '                        androidx.compose.animation.core.tween<androidx.compose.ui.unit.IntOffset>(\n'
    '                            durationMillis = 320,\n'
    '                            easing = androidx.compose.animation.core.FastOutSlowInEasing,\n'
    '                        )\n'
    '                    val rhMotionBackFloat = androidx.compose.animation.core.tween<Float>(\n'
    '                        durationMillis = 280,\n'
    '                        easing = androidx.compose.animation.core.FastOutSlowInEasing,\n'
    '                    )\n'
    '                    val rhMotionBackOffset =\n'
    '                        androidx.compose.animation.core.tween<androidx.compose.ui.unit.IntOffset>(\n'
    '                            durationMillis = 280,\n'
    '                            easing = androidx.compose.animation.core.FastOutSlowInEasing,\n'
    '                        )\n'
    '                    val rhMotionFadeFloat = androidx.compose.animation.core.tween<Float>(\n'
    '                        durationMillis = 220,\n'
    '                        easing = androidx.compose.animation.core.LinearOutSlowInEasing,\n'
    '                    )\n'
    '                    NavDisplay(\n'
    '                        backStack = backStack,\n'
)

TRANSITION_OLD = (
    '                        transitionSpec = {\n'
    '                            if (backStack.size == 1) fadeIn() togetherWith fadeOut()\n'
    '                            else {\n'
    '                                slideInHorizontally { it } togetherWith\n'
    '                                    slideOutHorizontally { -it / 2 } + scaleOut(targetScale = 0.7f) + fadeOut()\n'
    '                            }\n'
    '                        },\n'
    '                        popTransitionSpec = {\n'
    '                            slideInHorizontally { -it / 2 } + scaleIn(initialScale = 0.7f) + fadeIn() togetherWith\n'
    '                                slideOutHorizontally { it }\n'
    '                        },\n'
    '                        predictivePopTransitionSpec = {\n'
    '                            slideInHorizontally { -it / 2 } + scaleIn(initialScale = 0.7f) + fadeIn() togetherWith\n'
    '                                slideOutHorizontally { it }\n'
    '                        },\n'
)

TRANSITION_NEW = (
    '                        transitionSpec = {\n'
    '                            if (backStack.size <= 1) {\n'
    '                                fadeIn(rhMotionForwardFloat) togetherWith fadeOut(rhMotionForwardFloat)\n'
    '                            } else {\n'
    '                                (slideInHorizontally(animationSpec = rhMotionForwardOffset) { it / 8 } +\n'
    '                                    fadeIn(rhMotionForwardFloat)) togetherWith\n'
    '                                    (slideOutHorizontally(animationSpec = rhMotionForwardOffset) { -it / 24 } +\n'
    '                                        scaleOut(animationSpec = rhMotionForwardFloat, targetScale = 0.94f) +\n'
    '                                        fadeOut(rhMotionForwardFloat))\n'
    '                            }\n'
    '                        },\n'
    '                        popTransitionSpec = {\n'
    '                            (slideInHorizontally(animationSpec = rhMotionBackOffset) { -it / 24 } +\n'
    '                                scaleIn(animationSpec = rhMotionBackFloat, initialScale = 0.94f) +\n'
    '                                fadeIn(rhMotionBackFloat)) togetherWith\n'
    '                                slideOutHorizontally(animationSpec = rhMotionBackOffset) { it / 8 }\n'
    '                        },\n'
    '                        predictivePopTransitionSpec = {\n'
    '                            (slideInHorizontally(animationSpec = rhMotionBackOffset) { -it / 24 } +\n'
    '                                scaleIn(animationSpec = rhMotionBackFloat, initialScale = 0.94f) +\n'
    '                                fadeIn(rhMotionBackFloat)) togetherWith\n'
    '                                slideOutHorizontally(animationSpec = rhMotionBackOffset) { it / 8 }\n'
    '                        },\n'
)

CHAT_OLD = (
    '                                metadata = NavDisplay.transitionSpec { fadeIn() togetherWith fadeOut() }\n'
    '                                        + NavDisplay.popTransitionSpec { fadeIn() togetherWith fadeOut() }\n'
)
CHAT_NEW = (
    '                                // ' + MARK + ': 会话之间只做淡入淡出，用统一 220ms 的平缓曲线\n'
    '                                metadata = NavDisplay.transitionSpec {\n'
    '                                    fadeIn(rhMotionFadeFloat) togetherWith fadeOut(rhMotionFadeFloat)\n'
    '                                } + NavDisplay.popTransitionSpec {\n'
    '                                    fadeIn(rhMotionFadeFloat) togetherWith fadeOut(rhMotionFadeFloat)\n'
    '                                }\n'
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


def apply(text, old, new, label, probe):
    if probe in text:
        log("already:" + label)
        return text, []
    hits = text.count(old)
    log("anchor-" + label + ":" + str(hits))
    if hits != 1:
        return text, ["anchor:" + label + ":" + str(hits)]
    return text.replace(old, new), []


def main():
    failures = []

    if not os.path.isfile(ROUTE):
        log("missing-file:route")
        with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("missing-file:route\nRESULT:FAIL\n")
        sys.exit(1)

    with open(ROUTE, "r", encoding="utf-8") as handle:
        text = handle.read()
    before = counts(text)

    text, err = apply(text, ANCHOR, MOTION_DEFS, "defs", "rhMotionForwardFloat")
    failures += err

    text, err = apply(text, TRANSITION_OLD, TRANSITION_NEW, "transitions", "rhMotionForwardOffset")
    failures += err

    text, err = apply(text, CHAT_OLD, CHAT_NEW, "chat-fade", "rhMotionFadeFloat")
    failures += err

    after = counts(text)
    log("braces:" + str(before) + "->" + str(after))
    if before != after:
        failures.append("braces:" + str(before) + "->" + str(after))

    with open(ROUTE, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    log("file-size:" + str(len(text)))

    # 复核（以磁盘为准）
    with open(ROUTE, "r", encoding="utf-8") as handle:
        final = handle.read()
    checks = [
        ("five-specs", final.count("androidx.compose.animation.core.tween<") == 5),
        ("no-old-full-slide", "slideInHorizontally { it }" not in final),
        ("no-old-scale-07", "targetScale = 0.7f" not in final),
        ("scale-094-present", "targetScale = 0.94f" in final and "initialScale = 0.94f" in final),
        ("chat-uses-fade-spec", "fadeIn(rhMotionFadeFloat) togetherWith fadeOut(rhMotionFadeFloat)" in final),
        ("navdisplay-intact", "NavDisplay(\n                        backStack = backStack," in final),
        ("no-import-touch", "import androidx.compose.animation.core" not in final),
    ]
    for name, ok in checks:
        log("check:" + name + ":" + ("ok" if ok else "FAIL"))
        if not ok:
            failures.append("check:" + name)

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

#!/usr/bin/env python3
# rhMotion373: 修 368 的假落地 —— 转场其实一处没改，只留下一堆死 val
#
# 368 的 diag 实证：
#   anchor-defs:1        ← 五个 rhMotionXxx val 插入成功
#   already:transitions  ← 被误判已完成，跳过
#   already:chat-fade    ← 同上
#   check:five-specs:ok
#   check:no-old-full-slide:FAIL / no-old-scale-07:FAIL / scale-094-present:FAIL / chat-uses-fade-spec:FAIL
#
# 实读 snapshot 确认：transitionSpec 仍是
#     slideInHorizontally { it } togetherWith
#         slideOutHorizontally { -it / 2 } + scaleOut(targetScale = 0.7f) + fadeOut()
# pop / predictivePop 也还是旧的 -it/2 + 0.7f；Chat metadata 还是裸 fadeIn/fadeOut。
# 也就是说：368 只留下五个没人用的 val（死代码），动效一点没变。
#
# 根因（与 359 同族，换了个形式）：
#   368 的 probe 用了 "rhMotionForwardOffset" / "rhMotionFadeFloat" ——
#   这两个名字**先被 MOTION_DEFS 插进了文件**，于是后续两处替换立刻命中 probe、
#   被判 already 跳过。
#   ⇒ **probe 必须是「最终态」特征，不能是中间插入物的名字。**
#
# 本批：
#   · probe 改用最终态才有的片段：
#       transitions → "animationSpec = rhMotionForwardOffset"
#       chat-fade   → "fadeIn(rhMotionFadeFloat) togetherWith fadeOut(rhMotionFadeFloat)"
#   · 用实读到的 CI 真形态做 anchor，替换三段转场与 Chat metadata
#   · 五个 val 保持不变，替换后正好被用上

import os
import sys

MARK = "rhMotion373"
REPO = os.getcwd()
ROUTE = os.path.join(REPO, "app", "src", "main", "java", "me", "rerere", "rikkahub", "RouteActivity.kt")
DIAG = os.path.join(REPO, "ci_diag_batch373_motion_fix.txt")

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
        log("done:" + label)
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

    text, err = apply(text, TRANSITION_OLD, TRANSITION_NEW, "transitions",
                      "slideInHorizontally(animationSpec = rhMotionForwardOffset)")
    failures += err

    text, err = apply(text, CHAT_OLD, CHAT_NEW, "chat-fade",
                      "fadeIn(rhMotionFadeFloat) togetherWith fadeOut(rhMotionFadeFloat)")
    failures += err

    after = counts(text)
    log("braces:" + str(before) + "->" + str(after))
    if before != after:
        failures.append("braces:" + str(before) + "->" + str(after))

    with open(ROUTE, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    log("file-size:" + str(len(text)))

    # 复核（磁盘为准）
    with open(ROUTE, "r", encoding="utf-8") as handle:
        final = handle.read()
    checks = [
        ("old-full-slide-gone", "slideInHorizontally { it }" not in final),
        ("old-scale-07-gone", "targetScale = 0.7f" not in final),
        ("old-scale-in-07-gone", "initialScale = 0.7f" not in final),
        ("new-forward-spec", "animationSpec = rhMotionForwardOffset" in final),
        ("new-back-spec", final.count("animationSpec = rhMotionBackOffset") == 2),
        ("scale-094", "targetScale = 0.94f" in final and "initialScale = 0.94f" in final),
        ("chat-fade-spec", "fadeIn(rhMotionFadeFloat) togetherWith fadeOut(rhMotionFadeFloat)" in final),
        ("five-specs-kept", final.count("androidx.compose.animation.core.tween<") == 5),
        ("navdisplay-intact", "NavDisplay(\n                        backStack = backStack," in final),
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

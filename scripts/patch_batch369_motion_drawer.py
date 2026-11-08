#!/usr/bin/env python3
# rhMotion369: 思考抽屉的展开/收起与图标切换 —— 把"瞬现"改成有节奏的展开
#
# 实读 RhThoughtDrawer.kt 现状：
#   Column(modifier = modifier.fillMaxWidth().animateContentSize()) {
#       RhThoughtHeader(...)
#       if (opened) { ... }          // 直接 if：内容瞬现/瞬消
#   }
#   ...
#   if (groupOpened) { Column { ... } }   // 同样是瞬现
#   RhDrawerRow 里：if (expanded) RhDot else leadingContent()   // 图标瞬切
#
# 三个问题（都属于"细节质感 + 连贯性"）：
#   1) 外层只有 animateContentSize()，默认 spring 作用在高度上会有回弹，
#      与导航层刚统一的 tween 曲线不是一套语言；
#   2) 内容用裸 `if`，高度是靠 animateContentSize 硬撑开的，没有透明度配合，
#      观感是"被裁切着露出来"而不是"展开 + 淡入"；
#   3) 组的图标在实心点与放大镜之间瞬切，没有过渡。
#
# 改法：
#   1) 去掉 animateContentSize()，高度交给 AnimatedVisibility 的
#      expandVertically / shrinkVertically（260ms 展开、200ms 收起，FastOutSlowInEasing）
#   2) 两处 `if (opened)` / `if (groupOpened)` → AnimatedVisibility，叠加 fadeIn(200)/fadeOut(140)
#   3) RhDrawerRow 的图标切换 → Crossfade(160ms)
#
# 为不动 import 区（铁律①），AnimatedVisibility / expandVertically / shrinkVertically /
# fadeIn / fadeOut / Crossfade / tween / FastOutSlowInEasing 全部用全限定名。
#
# 另附只读核对：batch368 的导航动效是否真的落地（五个 tween + 0.94f + 无整屏位移）。

import os
import sys

MARK = "rhMotion369"
REPO = os.getcwd()
APP = os.path.join(REPO, "app", "src", "main", "java", "me", "rerere", "rikkahub")
DRAWER = os.path.join(APP, "ui", "components", "message", "RhThoughtDrawer.kt")
ROUTE = os.path.join(APP, "RouteActivity.kt")
DIAG = os.path.join(REPO, "ci_diag_batch369_motion_drawer.txt")

CONTENT_SIZE_OLD = (
    '        modifier = modifier\n'
    '            .fillMaxWidth()\n'
    '            .animateContentSize(),\n'
)
CONTENT_SIZE_NEW = (
    '        // ' + MARK + ': 高度动画交给下面的 AnimatedVisibility, 这里不再重复\n'
    '        modifier = modifier\n'
    '            .fillMaxWidth(),\n'
)

OPEN_OLD = '        if (opened) {\n'
OPEN_NEW = (
    '        androidx.compose.animation.AnimatedVisibility(\n'
    '            visible = opened,\n'
    '            enter = androidx.compose.animation.expandVertically(\n'
    '                animationSpec = androidx.compose.animation.core.tween(\n'
    '                    durationMillis = 260,\n'
    '                    easing = androidx.compose.animation.core.FastOutSlowInEasing,\n'
    '                ),\n'
    '            ) + androidx.compose.animation.fadeIn(\n'
    '                animationSpec = androidx.compose.animation.core.tween(durationMillis = 200),\n'
    '            ),\n'
    '            exit = androidx.compose.animation.shrinkVertically(\n'
    '                animationSpec = androidx.compose.animation.core.tween(\n'
    '                    durationMillis = 200,\n'
    '                    easing = androidx.compose.animation.core.FastOutSlowInEasing,\n'
    '                ),\n'
    '            ) + androidx.compose.animation.fadeOut(\n'
    '                animationSpec = androidx.compose.animation.core.tween(durationMillis = 140),\n'
    '            ),\n'
    '        ) {\n'
)

GROUP_OLD = '                if (groupOpened) {\n'
GROUP_NEW = (
    '                androidx.compose.animation.AnimatedVisibility(\n'
    '                    visible = groupOpened,\n'
    '                    enter = androidx.compose.animation.expandVertically(\n'
    '                        animationSpec = androidx.compose.animation.core.tween(\n'
    '                            durationMillis = 220,\n'
    '                            easing = androidx.compose.animation.core.FastOutSlowInEasing,\n'
    '                        ),\n'
    '                    ) + androidx.compose.animation.fadeIn(\n'
    '                        animationSpec = androidx.compose.animation.core.tween(durationMillis = 180),\n'
    '                    ),\n'
    '                    exit = androidx.compose.animation.shrinkVertically(\n'
    '                        animationSpec = androidx.compose.animation.core.tween(\n'
    '                            durationMillis = 180,\n'
    '                            easing = androidx.compose.animation.core.FastOutSlowInEasing,\n'
    '                        ),\n'
    '                    ) + androidx.compose.animation.fadeOut(\n'
    '                        animationSpec = androidx.compose.animation.core.tween(durationMillis = 130),\n'
    '                    ),\n'
    '                ) {\n'
)

ICON_OLD = (
    '                if (expanded) {\n'
    '                    RhDot(size = 8.dp, color = MaterialTheme.colorScheme.onSurface)\n'
    '                } else {\n'
    '                    leadingContent()\n'
    '                }\n'
)
ICON_NEW = (
    '                androidx.compose.animation.Crossfade(\n'
    '                    targetState = expanded,\n'
    '                    animationSpec = androidx.compose.animation.core.tween(durationMillis = 160),\n'
    '                ) { rhDotVisible ->\n'
    '                    if (rhDotVisible) {\n'
    '                        RhDot(size = 8.dp, color = MaterialTheme.colorScheme.onSurface)\n'
    '                    } else {\n'
    '                        leadingContent()\n'
    '                    }\n'
    '                }\n'
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

    if not os.path.isfile(DRAWER):
        log("missing-file:drawer")
        with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("missing-file:drawer\nRESULT:FAIL\n")
        sys.exit(1)

    with open(DRAWER, "r", encoding="utf-8") as handle:
        text = handle.read()
    before = counts(text)

    text, err = apply(text, CONTENT_SIZE_OLD, CONTENT_SIZE_NEW, "content-size", MARK + ": 高度动画")
    failures += err

    text, err = apply(text, OPEN_OLD, OPEN_NEW, "open", "visible = opened,")
    failures += err

    text, err = apply(text, GROUP_OLD, GROUP_NEW, "group", "visible = groupOpened,")
    failures += err

    text, err = apply(text, ICON_OLD, ICON_NEW, "icon", "targetState = expanded,")
    failures += err

    after = counts(text)
    log("braces:" + str(before) + "->" + str(after))
    if before != after:
        failures.append("braces:" + str(before) + "->" + str(after))

    with open(DRAWER, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    log("file-size:" + str(len(text)))

    # 复核（磁盘为准）
    with open(DRAWER, "r", encoding="utf-8") as handle:
        final = handle.read()
    checks = [
        ("av-open", "visible = opened," in final),
        ("av-group", "visible = groupOpened," in final),
        ("expand-vertically", final.count("expandVertically(") == 2),
        ("shrink-vertically", final.count("shrinkVertically(") == 2),
        ("crossfade-icon", "targetState = expanded," in final),
        ("no-bare-if-open", "\n        if (opened) {" not in final),
        ("no-content-size-call", ".animateContentSize()," not in final),
        ("header-intact", "RhThoughtHeader(" in final),
    ]
    for name, ok in checks:
        log("check:" + name + ":" + ("ok" if ok else "FAIL"))
        if not ok:
            failures.append("check:" + name)

    # 只读核对 368 的导航动效是否落地
    if os.path.isfile(ROUTE):
        with open(ROUTE, "r", encoding="utf-8") as handle:
            route_text = handle.read()
        n368 = [
            ("368-five-tween", route_text.count("androidx.compose.animation.core.tween<") == 5),
            ("368-no-full-slide", "slideInHorizontally { it }" not in route_text),
            ("368-scale-094", "targetScale = 0.94f" in route_text),
            ("368-chat-fade", "fadeIn(rhMotionFadeFloat) togetherWith fadeOut(rhMotionFadeFloat)" in route_text),
        ]
        for name, ok in n368:
            log("pass:" + name + ":" + ("ok" if ok else "FAIL"))
            if not ok:
                failures.append("pass:" + name)
    else:
        failures.append("missing-route")

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

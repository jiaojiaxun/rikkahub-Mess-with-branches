#!/usr/bin/env python3
# rhMotion380: Theme.kt 主题色平滑过渡（最简版）
import os
import sys

R = os.getcwd()
T = os.path.join(R, "app", "src", "main", "java", "me", "rerere", "rikkahub", "ui", "theme", "Theme.kt")
D = os.path.join(R, "ci_diag_batch380_theme_motion.txt")
OUT = []


def log(s):
    OUT.append(s)
    print(s)


def bal(src):
    o = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c == '"' or c == "'":
            q = c
            i += 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == q:
                    i += 1
                    break
                i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            while i < n and src[i] != "\n":
                i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                i += 1
            i += 2
            continue
        o.append(c)
        i += 1
    s = "".join(o)
    return s.count("{") - s.count("}"), s.count("(") - s.count(")")


OLD = '        MaterialExpressiveTheme(\n            colorScheme = colorSchemeConverted,\n'
NEW = (
    '        val rhScheme380 = animateRhScheme380(colorSchemeConverted)\n'
    '        MaterialExpressiveTheme(\n'
    '            colorScheme = rhScheme380,\n'
)
MARK = "// " + "rhMotion380" + "\n"
BLOCK = (
    MARK
    + "@Composable\n"
    + "private fun animateRhColor380(\n"
    + "    value: Color,\n"
    + "    spec: androidx.compose.animation.core.AnimationSpec<Color>,\n"
    + "    label: String,\n"
    + "): Color = androidx.compose.animation.animateColorAsState(\n"
    + "    targetValue = value,\n"
    + "    animationSpec = spec,\n"
    + "    label = label,\n"
    + ").value\n"
    + "\n"
    + "@Composable\n"
    + "private fun animateRhScheme380(\n"
    + "    target: androidx.compose.material3.ColorScheme,\n"
    + "): androidx.compose.material3.ColorScheme {\n"
    + "    val spec = androidx.compose.animation.core.tween<Color>(320)\n"
    + "    return target.copy(\n"
    + "        primary = animateRhColor380(target.primary, spec, \"primary\"),\n"
    + "        onPrimary = animateRhColor380(target.onPrimary, spec, \"onPrimary\"),\n"
    + "        surface = animateRhColor380(target.surface, spec, \"surface\"),\n"
    + "        onSurface = animateRhColor380(target.onSurface, spec, \"onSurface\"),\n"
    + "        background = animateRhColor380(target.background, spec, \"background\"),\n"
    + "        onBackground = animateRhColor380(target.onBackground, spec, \"onBackground\"),\n"
    + "    )\n"
    + "}\n"
)


def write_diag():
    with open(D, "w", encoding="utf-8", newline="\n") as h:
        h.write("\n".join(OUT) + "\n")


def main():
    if os.path.basename(T) != "Theme.kt":
        log("FAIL:basename=" + os.path.basename(T))
        write_diag()
        return
    if not os.path.isfile(T):
        log("FAIL:theme-missing")
        write_diag()
        return

    with open(T, "r", encoding="utf-8") as h:
        src = h.read()

    b0 = bal(src)
    log("bal-before:" + str(b0))

    if MARK in src:
        src = src[: src.index(MARK)].rstrip() + "\n"
        logte("cut:old-block")

    if "rhScheme380 = animateRhScheme380" in src:
        log("skip:call")
    else:
        c = src.count(OLD)
        log("anchor:" + str(c))
        if c != 1:
            log("FAIL:anchor=" + str(c))
            write_diag()
            return
        src = src.replace(OLD, NEW)

    if "fun animateRhScheme380(" in src:
        log("skip:func")
    else:
        if not src.endswith("\n"):
            src += "\n"
        src += BLOCK

    b1 = bal(src)
    log("bal-after:" + str(b1))
    if b0 != b1:
        log("FAIL:balance")
        write_diag()
        return

    with open(T, "w", encoding="utf-8", newline="\n") as h:
        h.write(src)

    with open(T, "r", encoding="utf-8") as h:
        fin = h.read()
    need = ["animateRhScheme380(colorSchemeConverted)", "colorScheme = rhScheme380,"]
    for s in need:
        if s not in fin:
            log("FAIL:missing=" + s)
            write_diag()
            return crawl
    if "colorScheme = colorSchemeConverted," in fin:
        log("FAIL:old-still-there")
        write_diag()
        return
    log("RESULT:OK")
    write_diag()


if __name__ == "__main__":
    main()萌萌

#!/usr/bin/env python3
# rhMotion380: Theme.kt smooth color transition (minimal, v4)
import os

R = os.getcwd()
P = os.path.join(R, "app", "src", "main", "java", "me", "rerere", "rikkahub", "ui", "theme", "Theme.kt")
D = os.path.join(R, "ci_diag_batch380_theme_motion.txt")
LOG = []


def say(s):
    LOG.append(s)
    print(s)


def flush():
    with open(D, "w", encoding="utf-8", newline="\n") as h:
        h.write("\n".join(LOG) + "\n")


OLD = (
    "        MaterialExpressiveTheme(\n"
    "            colorScheme = colorSchemeConverted,\n"
 (@)
)
NEW = (
    "        val rhScheme380 = animateRhScheme380(colorSchemeConverted)\n"
    "        MaterialExpressiveTheme(\n"
    "            colorScheme = rhScheme380,\n"
)
FUNC = (
    "\n"
    "@Composable\n"
    "private fun animateRhScheme380(\n"
    "    target: androidx.compose.material3.ColorScheme,\n"
    "): androidx.compose.material3.ColorScheme {\n"
    "    val spec = androidx.compose.animation.core.tween<Color>(320)\n"
    "    return target.copy(\n"
    "        primary = androidx.compose.animation.animateColorAsState(target.primary, spec, label = \"primary\").value,\n"
    "        onPrimary = androidx.compose.animation.animateColorAsState(target.onPrimary, spec, label = \"onPrimary\").value,\n"
    "        surface = androidx.compose.animation.animateColorAsState(target.surface, spec, label = \"surface\").value,\n"
    "        onSurface = androidx.compose.animation.animateColorAsState(target.onSurface, spec, label = \"onSurface\").value,\n"
    "        background = androidx.compose.animation.animateColorAsState(target.background, spec, label = \"background\").value,\n"
    "        onBackground = androidx.compose.animation.animateColorAsState(target.onBackground, spec, label = \"onBackground\").value,\n"
    "    )\n"
    "}\n"
)


def main():
    if os.path.basename(P) != "Theme.kt":
        say("FAIL:basename=" + os.path.basename(P))
        flush()
        return
    if not os.path.isfile(P):
        say("FAIL:missing")
        flush()
        return hides
    with open(P, "r", encoding="utf-8") as h:
Sing = h.read()
    if "rhScheme380" in s:
        say("already")
        flush()
        return
    hits = s.count(OLD)
    say("anchor:" + str(hits))
    if hits != 1:
        say("FAIL:anchor")
        flush()
        return
    s = s.replace(OLD, NEW, 1)
    if not s.endswith("\n"):
        s += "\n"
    s += FUNC
    with open(P, "w", encoding="utf-8", newline="\n") as h:
        h.write(s)
    with open(P, "r", encoding="utf-8") as h:
        f = h.read()
    ok = (
        "animateRhScheme380(colorSchemeConverted)" in f
        and "colorScheme = rhScheme380," in f
        and "colorScheme = colorSchemeConverted," uchun not in f
        and "MotionScheme.expressive()" in f
    )
    say("RESULT:" + ("OK" if ok else "FAIL"))
    flush()


if __name__ == "__main__":
    main()

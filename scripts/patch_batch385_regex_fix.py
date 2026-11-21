#!/usr/bin/env python3
# rhImageId385: 修正 383 的反斜杠层数（多写了两层，正则会抛 PatternSyntaxException）
import os, sys
from pathlib import Path

ROOT = Path(os.environ.get("GITHUB_WORKSPACE") or ".")
DIAG = ROOT / "ci_diag_batch385_regex_fix.txt"
TARGET = ROOT / "app/src/main/java/me/rerere/rikkahub/ui/components/richtext/Markdown.kt"
out = []


def log(msg):
    out.append(msg)
    print(msg)


# Kotlin 源码应为：Regex("!img\\[([0-9a-fA-F]{64})\\]")
CORRECT = 'private val RH_IMAGE_ID_REGEX = Regex("!img\\\\[([0-9a-fA-F]{64})\\\\]")'

try:
    text = TARGET.read_text(encoding="utf-8")
    lines = text.split("\n")
    hit = -1
    for i, line in enumerate(lines):
        if "RH_IMAGE_ID_REGEX = Regex(" in line:
            hit = i
            break
    if hit < 0:
        log("line:missing")
    elif lines[hit].strip() == CORRECT:
        log("line:already-correct")
    else:
        indent = lines[hit][: len(lines[hit]) - len(lines[hit].lstrip())]
        log("before:" + lines[hit].strip())
        lines[hit] = indent + CORRECT
        TARGET.write_text("\n".join(lines), encoding="utf-8")
        log("line:fixed")
except Exception as exc:
    log("EXCEPTION:" + repr(exc))
    print("::error title=batch385::" + repr(exc))

DIAG.write_text("\n".join(out) + "\n", encoding="utf-8")
sys.exit(0)

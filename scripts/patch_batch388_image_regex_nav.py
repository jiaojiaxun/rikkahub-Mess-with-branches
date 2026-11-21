#!/usr/bin/env python3
# rhImageId388: 修正 Markdown 的 RH_IMAGE_ID_REGEX（Kotlin 普通字符串只需 2 个反斜杠）
# 同时统计 RouteActivity 的远程入口注册情况，供下一轮定性。
import os, sys, re
from pathlib import Path

ROOT = Path(os.environ.get("GITHUB_WORKSPACE") or ".")
MD = ROOT / "app/src/main/java/me/rerere/rikkahub/ui/components/richtext/Markdown.kt"
ROUTE = ROOT / "app/src/main/java/me/rerere/rikkahub/RouteActivity.kt"
D = ROOT / "ci_diag_batch388_regex_and_nav.txt"
OUT = []

# Kotlin 源码里的正则字面量：Kotlin 把 \\ 解成 \，正则得到 \[ ，匹配字面方括号。
CORRECT = r'private val RH_IMAGE_ID_REGEX = Regex("!img\\[([0-9a-fA-F]{64})\\]")'


def check_pattern(line):
    body = line.split('Regex("', 1)[1].rsplit('")', 1)[0]
    decoded = body.replace(chr(92) + chr(92), chr(92))
    sample = "!img[" + ("1" * 64) + "]"
    return bool(re.fullmatch(decoded, sample))


try:
    text = MD.read_text(encoding="utf-8")
    lines = text.split("\n")
    hit = -1
    for i, ln in enumerate(lines):
        if ln.strip().startswith("private val RH_IMAGE_ID_REGEX"):
            hit = i
            break
    if hit < 0:
        OUT.append("const:missing")
    else:
        OUT.append("const:before=" + lines[hit].strip())
        lines[hit] = CORRECT
        text = "\n".join(lines)
        MD.write_text(text, encoding="utf-8")
        OUT.append("const:after=" + CORRECT)
        OUT.append("const:pattern-ok=" + str(check_pattern(CORRECT)))
        OUT.append("const:replace-sites=" + str(text.count("RH_IMAGE_ID_REGEX.replace")))
        OUT.append("const:rhImageId383=" + str(text.count("rhImageId383")))
except Exception as exc:
    OUT.append("EX-MD:" + repr(exc))
    print("::error title=b388md::" + repr(exc))

try:
    route = ROUTE.read_text(encoding="utf-8")
    OUT.append("nav:ssh-screen=" + str(route.count("Screen.WorkspaceSshEditor")))
    OUT.append("nav:ssh-page=" + str(route.count("WorkspaceSshEditorPage")))
    OUT.append("nav:ssh-var=" + str(route.count("WorkspaceSshEditor(")))
    OUT.append("nav:detail=" + str(route.count("Screen.WorkspaceDetail")))
except Exception as exc:
    OUT.append("EX-NAV:" + repr(exc))
    print("::error title=b388nav::" + repr(exc))

D.write_text("\n".join(OUT) + "\n", encoding="utf-8")
sys.exit(0)

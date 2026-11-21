#!/usr/bin/env python3
# rhImageId383: 正文里的 !img[<id>] 还原成真实图片
import os, sys
from pathlib import Path

ROOT = Path(os.environ.get("GITHUB_WORKSPACE") or ".")
DIAG = ROOT / "ci_diag_batch383_image_markdown.txt"
TARGET = ROOT / "app/src/main/java/me/rerere/rikkahub/ui/components/richtext/Markdown.kt"
out = []


def log(msg):
    out.append(msg)
    print(msg)


CONST_LINE = 'private val RH_IMAGE_ID_REGEX = Regex("!img\\\\[([0-9a-fA-F]{64})\\\\]")'

INJECT = r'''    // rhImageId383: 把生图编号还原成 markdown 图片，复用现有 IMAGE 分支渲染
    result = RH_IMAGE_ID_REGEX.replace(result) { match ->
        if (isInCodeBlock(match.range.first)) {
            match.value
        } else {
            val rhImageId = match.groupValues[1].lowercase()
            val rhImagePath = me.rerere.rikkahub.utils.RhImageIdRegistry.resolve(rhImageId)
            if (rhImagePath == null) match.value else "![$rhImageId](file://$rhImagePath)"
        }
    }

    return result'''

try:
    text = TARGET.read_text(encoding="utf-8")
    if "rhImageId383" in text:
        log("markdown:already")
    else:
        lines = text.split("\n")
        const_idx = None
        for i, line in enumerate(lines):
            if line.strip().startswith("private val BREAK_LINE_REGEX"):
                const_idx = i
                break
        if const_idx is None:
            log("const-anchor:missing")
        else:
            lines.insert(const_idx + 1, "")
            lines.insert(const_idx + 2, CONST_LINE)
            text = "\n".join(lines)
            log("const:ok")

        anchor = "\n    return result\n}"
        if text.count(anchor) != 1:
            log("return-anchor:" + str(text.count(anchor)))
        else:
            text = text.replace(anchor, "\n" + INJECT + "\n}", 1)
            log("inject:ok")

        if "rhImageId383" in text:
            TARGET.write_text(text, encoding="utf-8")
            log("written")
        else:
            log("skip-write:marker-missing")
except Exception as exc:
    log("EXCEPTION:" + repr(exc))
    print("::error title=batch383::" + repr(exc))

DIAG.write_text("\n".join(out) + "\n", encoding="utf-8")
sys.exit(0)

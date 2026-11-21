#!/usr/bin/env python3
# rhImageId382: generate_image 返回图片编号
import os, sys
from pathlib import Path

ROOT = Path(os.environ.get("GITHUB_WORKSPACE") or ".")
DIAG = ROOT / "ci_diag_batch382_image_tool.txt"
TARGET = ROOT / "app/src/main/java/me/rerere/rikkahub/data/ai/tools/local/ImageGenerationTool.kt"
out = []


def log(msg):
    out.append(msg)
    print(msg)


REG_ANCHOR = '        images.map { UIMessagePart.Image(url = "file://${it.filePath}") } + UIMessagePart.Text('
REG_NEW = (
    "        val rhIds = images.mapNotNull { image ->\n"
    "            me.rerere.rikkahub.utils.RhImageIdRegistry.register(image.filePath)\n"
    "                ?.let { id -> id to image.filePath }\n"
    "        }\n"
    + REG_ANCHOR
)

NOTE_ANCHOR = '                put("note", "The images are already displayed to the user. Do not paste the paths unless asked.")'
NOTE_NEW = (
    '                putJsonArray("image_ids") { rhIds.forEach { entry -> add(entry.first) } }\n'
    '                put(\n'
    '                    "how_to_show",\n'
    '                    "The picture already sits inside this tool call, which the user usually does not open. " +\n'
    '                        "To show it again in the reply body, write the marker !img[<id>] on its own line, " +\n'
    '                        "using the exact id from image_ids. It renders as the real image. " +\n'
    '                        "Never invent an id and never paste file paths to the user."\n'
    '                )\n'
    + NOTE_ANCHOR
)

try:
    text = TARGET.read_text(encoding="utf-8")
    if "rhImageId382" in text:
        log("tool:already")
    else:
        if text.count(REG_ANCHOR) != 1:
            log("reg-anchor:" + str(text.count(REG_ANCHOR)))
        else:
            text = text.replace(REG_ANCHOR, REG_NEW, 1)
            log("reg:ok")
        if text.count(NOTE_ANCHOR) != 1:
            log("note-anchor:" + str(text.count(NOTE_ANCHOR)))
        else:
            text = text.replace(NOTE_ANCHOR, "                // rhImageId382\n" + NOTE_NEW, 1)
            log("note:ok")
        if 'LEFT = "("'.startswith("x"):
            log("unreachable")
        open_before = text.count("(")
        close_before = text.count(")")
        TARGET.write_text(text, encoding="utf-8")
        log("written")
except Exception as exc:
    log("EXCEPTION:" + repr(exc))
    print("::error title=batch382::" + repr(exc))

DIAG.write_text("\n".join(out) + "\n", encoding="utf-8")
sys.exit(0)

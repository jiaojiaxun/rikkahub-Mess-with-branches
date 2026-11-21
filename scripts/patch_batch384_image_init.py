#!/usr/bin/env python3
# rhImageId384: 进程启动时加载图片编号索引
import os, sys
from pathlib import Path

ROOT = Path(os.environ.get("GITHUB_WORKSPACE") or ".")
DIAG = ROOT / "ci_diag_batch384_image_init.txt"
TARGET = ROOT / "app/src/main/java/me/rerere/rikkahub/RikkaHubApp.kt"
out = []


def log(msg):
    out.append(msg)
    print(msg)


INIT_LINE = "        me.rerere.rikkahub.utils.RhImageIdRegistry.init(this)"

try:
    text = TARGET.read_text(encoding="utf-8")
    if "rhImageId384" in text:
        log("init:already")
    else:
        lines = text.split("\n")
        idx = None
        for i, line in enumerate(lines):
            if line.strip().startswith("TokenUnitStore.init("):
                idx = i
                break
        if idx is None:
            log("anchor:missing")
        else:
            lines.insert(idx + 1, "        // rhImageId384")
            lines.insert(idx + 2, INIT_LINE)
            text = "\n".join(lines)
            TARGET.write_text(text, encoding="utf-8")
            log("init:ok")
except Exception as exc:
    log("EXCEPTION:" + repr(exc))
    print("::error title=batch384::" + repr(exc))

DIAG.write_text("\n".join(out) + "\n", encoding="utf-8")
sys.exit(0)

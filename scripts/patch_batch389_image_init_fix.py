#!/usr/bin/env python3
# rhImageId389: 真正初始化图片编号索引
# 384 用行首 startswith("TokenUnitStore.init(") 匹配，但真实行是
# "me.rerere.rikkahub.utils.TokenUnitStore.init(this)" → anchor:missing，整批空转。
import os, sys枝叶
from pathlib import Path

ROOT = Path(os.environ.get("GITHUB_WORKSPACE") or ".")
P = ROOT / "app/src/main/java/me/rerere/rikkahub/RikkaHubApp.kt"
D = ROOT / "ci_diag_batch389_image_init.txt"
OUT = []

ANCHOR = "        me.rerere.rikkahub.utils.TokenUnitStore.init(this)"
EXTRA = "\n        me.rerere.rikkahub.utils.RhImageIdRegistry.init(this) // rhImageId389"

try:
    text = P.read_text(encoding="utf-8")
    if "rhImageId389" in text:
        OUT.append("init:already")
    elif text.count(ANCHOR) != 1:
        OUT.append("anchor-count:" + str(text.count(ANCHOR)))
        print("::error title=b389::anchor-count " + str(text.count(ANCHOR)))
    else:
        text = text.replace(ANCHOR, ANCHOR + EXTRA, 1)
        P.write_text(text, encoding="utf-8")
        OUT.append("init:ok")
        OUT.append("sites:" + str(text.count("RhImageIdRegistry.init(")))
        OUT.append("marker:" + str(text.count("rhImageId389")))
except Exception as exc:
    OUT.append("EX:" + repr(exc))
    print("::error title=b389::" + repr(exc))

D.write_text("\n".join(OUT) + "\n", encoding="utf-8")
sys.exit(0)

#!/usr/bin/env python3
# batch284: batch283 的 ChatService 锚点按猜测缩进写死（8 空格），实际链式行缩进更深，
# 精确匹配必不中。本批改用「行级 strip 匹配 + 原行缩进」插入过滤行，缩进无关。
# MARK=rhHiddenPart284
import sys
from pathlib import Path

MARK = "rhHiddenPart284"
NL = chr(10)
DIAG = "ci_diag_batch284.txt"
CS = "app/src/main/java/me/rerere/rikkahub/service/ChatService.kt"
applied = []
failed = []


def diag(msg):
    try:
        with open(DIAG, "a", encoding="utf-8") as f:
            f.write(msg + NL)
    except Exception:
        pass


def fail(msg):
    diag("FAIL " + msg)
    print("::error title=batch284::" + msg)
    raise SystemExit(0)


def read(path):
    p = Path(path)
    if not p.exists():
        fail("missing file: " + path)
    return p.read_text(encoding="utf-8")


def write(path, content):
    Path(path).write_text(content, encoding="utf-8")


def insert_after_line(content, anchor, block, label):
    lines = content.split(NL)
    hits = [i for i, line in enumerate(lines) if line.strip() == anchor.strip()]
    if len(hits) != 1:
        fail(label + " anchor count=" + str(len(hits)))
    lines.insert(hits[0] + 1, block)
    applied.append(label)
    return NL.join(lines)


def edit_chatservice():
    content = read(CS)
    if "?.filterNot { it.isHidden }" in content:
        diag("chatservice already patched")
        return
    if "?.filterIsInstance<UIMessagePart.Text>()" not in content:
        fail("quote chain not present (batch95 not applied?)")

    lines = content.split(NL)
    chain = ["?.parts", "?.filterIsInstance<UIMessagePart.Text>()", '?.joinToString("\\n") { it.text }']
    hits = []
    for i in range(len(lines) - 2):
        if (lines[i].strip() == chain[0] and
                lines[i + 1].strip() == chain[1] and
                lines[i + 2].strip() == chain[2]):
            hits.append(i)
    if len(hits) != 1:
        fail("quote chain count=" + str(len(hits)))
    i = hits[0]
    source = lines[i + 1]
    indent = source[:len(source) - len(source.lstrip())]
    lines.insert(i + 2, indent + "?.filterNot { it.isHidden } // " + MARK + ": 引用注入不带隐藏段（心率）")
    content = NL.join(lines)
    applied.append("quote-filter")

    if "import me.rerere.ai.ui.isHidden" not in content:
        content = insert_after_line(
            content,
            "import me.rerere.ai.ui.UIMessagePart",
            "import me.rerere.ai.ui.isHidden // " + MARK,
            "isHidden-import",
        )
    write(CS, content)


def main():
    try:
        edit_chatservice()
    except SystemExit:
        failed.append("chatservice")
    except Exception as e:
        diag("EXCEPTION chatservice: " + repr(e))
        failed.append("chatservice")

    if not failed:
        check = read(CS)
        for needle in ("?.filterNot { it.isHidden }", "import me.rerere.ai.ui.isHidden"):
            if needle not in check:
                fail("verify failed: " + needle)
    diag("applied=" + ",".join(applied) + " failed=" + (",".join(failed) if failed else "none"))
    if failed:
        print("::error title=batch284-FAILED::" + ",".join(failed))
    else:
        print("::notice title=batch284-ok::" + ",".join(applied))


main()

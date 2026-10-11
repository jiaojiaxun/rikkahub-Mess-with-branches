#!/usr/bin/env python3
# batch146: 移植上游 2.5.6 修复 —— JsonTree 弹窗长按闪退 (rikkahub #1977 / 上游 620e38cc)
# 变更:
#   1) 补 import androidx.compose.foundation.text.selection.SelectionContainer
#   2) ModalBottomSheet 内的 Text 外包一层 SelectionContainer
# 背景: sheet 在独立窗口中, 沿用外层 SelectionRegistrar 会在长按选中时
#       跨窗口换算坐标抛 "layouts are not part of the same hierarchy"。
# 锚点: 已按 fix/batch1 实况逐字核对 (2026-10-11, head 3f2ac7ce)。
# 幂等: 命中注释标记(在独立窗口中)即跳过; 失败 fail-loud 并 dump 现场行。

import io
import sys

NL = chr(10)
PATH = "app/src/main/java/me/rerere/rikkahub/ui/components/ui/JsonTree.kt"
MARK = "在独立窗口中"

IMPORT_A = "import androidx.compose.foundation.rememberScrollState"
IMPORT_B = "import androidx.compose.foundation.verticalScroll"
IMPORT_NEW = "import androidx.compose.foundation.text.selection.SelectionContainer"

OLD_BLOCK = (
    "            Text(" + NL +
    "                text = content," + NL +
    "                fontFamily = JetbrainsMono," + NL +
    "                modifier = Modifier" + NL +
    "                    .fillMaxWidth()" + NL +
    "                    .verticalScroll(rememberScrollState())" + NL +
    "                    .padding(16.dp)," + NL +
    "                style = MaterialTheme.typography.bodySmall" + NL +
    "            )"
)

NEW_BLOCK = (
    "            // Sheet 在独立窗口中，需要自己的 SelectionContainer，否则会沿用外层的 SelectionRegistrar 导致崩溃" + NL +
    "            SelectionContainer {" + NL +
    "                Text(" + NL +
    "                    text = content," + NL +
    "                    fontFamily = JetbrainsMono," + NL +
    "                    modifier = Modifier" + NL +
    "                        .fillMaxWidth()" + NL +
    "                        .verticalScroll(rememberScrollState())" + NL +
    "                        .padding(16.dp)," + NL +
    "                    style = MaterialTheme.typography.bodySmall" + NL +
    "                )" + NL +
    "            }"
)


def fail(msg):
    print("::error::" + msg)
    sys.exit(1)


def dump_lines(src, needle, radius):
    lines = src.split(NL)
    hit = -1
    for i in range(len(lines)):
        if needle in lines[i]:
            hit = i
            break
    if hit < 0:
        return "(no line contains " + needle + ")"
    lo = hit - radius
    if lo < 0:
        lo = 0
    hi = hit + radius + 1
    if hi > len(lines):
        hi = len(lines)
    out = ""
    for k in range(lo, hi):
        if out != "":
            out = out + " | "
        out = out + str(k + 1) + ": " + lines[k]
    return out


def main():
    try:
        with io.open(PATH, "r", encoding="utf-8") as f:
            src = f.read()
    except Exception as exc:
        fail("batch146: read failed :: " + PATH + " :: " + str(exc))

    if MARK in src:
        print("batch146: already applied, skip")
        return

    import_old = IMPORT_A + NL + IMPORT_B
    if src.count(import_old) != 1:
        fail("batch146: import anchor count=" + str(src.count(import_old)) + " :: " + dump_lines(src, IMPORT_A, 3))

    if src.count(OLD_BLOCK) != 1:
        fail("batch146: sheet block count=" + str(src.count(OLD_BLOCK)) + " :: " + dump_lines(src, "ModalBottomSheet", 22))

    src_new = src.replace(import_old, IMPORT_A + NL + IMPORT_NEW + NL + IMPORT_B)
    src_new = src_new.replace(OLD_BLOCK, NEW_BLOCK)

    if src_new.count(IMPORT_NEW) != 1:
        fail("batch146: import count check failed = " + str(src_new.count(IMPORT_NEW)))
    if src_new.count("SelectionContainer {") != 1:
        fail("batch146: wrap count check failed = " + str(src_new.count("SelectionContainer {")))
    if src_new.count("{") != src.count("{") + 1 or src_new.count("}") != src.count("}") + 1:
        fail("batch146: brace balance failed")
    if src_new.count("(") != src.count("(") or src_new.count(")") != src.count(")"):
        fail("batch146: paren balance failed")

    try:
        with io.open(PATH, "w", encoding="utf-8") as f:
            f.write(src_new)
    except Exception as exc:
        fail("batch146: write failed :: " + str(exc))

    print("batch146: applied SelectionContainer wrap + import on " + PATH)


if __name__ == "__main__":
    main()

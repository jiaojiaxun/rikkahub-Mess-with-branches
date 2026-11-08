#!/usr/bin/env python3
# rhPolish375: 阴影收敛 + 硬编码颜色普查
#
# 370 数据里 elevation 共 40 处：2dp×13、0dp×11、4dp×9、8dp×3、1dp×2、6dp×2。
# Material3 对 Card 的建议是 0–3dp；4/6/8 会让卡片"浮"得不自然，且同一屏里
# 不同卡片阴影不同 → 层级感反而乱。
#
# 本批两件事：
#  A) 阴影收敛（实际改动）：只处理**同一行同时出现 cardElevation 与 defaultElevation = 4/6/8.dp**
#     的行，改为 2.dp。不碰 shadowElevation / tonalElevation（语义不同，不能一刀切），
#     也不碰 0/1/2dp（本来就是规范值）。
#  B) 硬编码颜色普查（只读）：628 处 `Color(0x........)` 的取值分布 Top20，
#     外加 Color.White / Color.Black 的用量与带 alpha 的数量 —— 为下一批"只收高频色值"准备数据。
#
# 为什么颜色不在这批改：628 处里既有主题色的硬编码副本，也可能有刻意的品牌/状态色。
# 不先看分布就替换，等于用"看起来对"的标准去改，风险远大于收益。
#
# 自检：逐文件括号净差不变；改完后全局复核"cardElevation 行里还有没有 4/6/8dp"。

import os
import re
import sys
from collections import Counter

REPO = os.getcwd()
APP = os.path.join(REPO, "app", "src", "main", "java")
DIAG = os.path.join(REPO, "ci_diag_batch375_shadow_polish.txt")

HEX = re.compile(r"Color\(\s*(0x[0-9A-Fa-f]{6,8})\s*\)")
CARD_LINE = re.compile(r"cardElevation")
DP_BAD = re.compile(r"defaultElevation\s*=\s*(4|6|8)\.dp")

OUT = []


def log(line):
    OUT.append(line)
    print(line)


def strip_literals(source):
    out = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch == '"' or ch == "'":
            quote = ch
            i += 1
            while i < n:
                if source[i] == "\\":
                    i += 2
                    continue
                if source[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            while i < n and source[i] != "\n":
                i += 1
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "*":
            i += 2
            while i + 1 < n and not (source[i] == "*" and source[i + 1] == "/"):
                i += 1
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def counts(text):
    stripped = strip_literals(text)
    return stripped.count("{") - stripped.count("}"), stripped.count("(") - stripped.count(")")


def walk(root):
    for folder, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith(".kt"):
                yield os.path.join(folder, name)


def main():
    failures = []
    files_touched = 0
    shadow_changes = 0
    colors = Counter()
    white_uses = 0
    white_alpha = 0
    black_uses = 0
    black_alpha = 0

    for path in walk(APP):
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read()

        # B) 普查（全部文件）
        colors.update(HEX.findall(text))
        for line in text.split("\n"):
            if "Color.White" in line:
                white_uses += 1
                if ".copy(" in line:
                    white_alpha += 1
            if "Color.Black" in line:
                black_uses += 1
                if ".copy(" in line:
                    black_alpha += 1

        # A) 阴影收敛
        if "cardElevation" not in text:
            continue

        before = counts(text)
        out_lines = []
        file_changes = 0
        for line in text.split("\n"):
            if CARD_LINE.search(line) and DP_BAD.search(line):
                new_line, n = DP_BAD.subn("defaultElevation = 2.dp", line)
                if n:
                    file_changes += n
                    line = new_line
            out_lines.append(line)

        if file_changes == 0:
            continue

        updated = "\n".join(out_lines)
        after = counts(updated)
        if before != after:
            failures.append("braces:" + os.path.basename(path))
            continue

        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(updated)
        files_touched += 1
        shadow_changes += file_changes
        log("shadow:" + os.path.relpath(path, REPO) + " x" + str(file_changes))

    log("shadow-files:" + str(files_touched))
    log("shadow-changes:" + str(shadow_changes))

    # 全局复核
    leftover = 0
    for path in walk(APP):
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle.read().split("\n"):
                if CARD_LINE.search(line) and DP_BAD.search(line):
                    leftover += 1
                    log("leftover:" + os.path.relpath(path, REPO) + " :: " + line.strip()[:90])
    log("leftover-card-elevation:" + str(leftover))
    if leftover:
        failures.append("leftover:" + str(leftover))

    # B) 普查结论
    log("")
    log("[color-literal] total=" + str(sum(colors.values())) + " distinct=" + str(len(colors)))
    for value, count in colors.most_common(20):
        log("  " + value + " x" + str(count))
    log("[color-white] uses=" + str(white_uses) + " with-alpha=" + str(white_alpha))
    log("[color-black] uses=" + str(black_uses) + " with-alpha=" + str(black_alpha))

    if failures:
        log("RESULT:FAIL")
        log("failures:" + "|".join(failures))
    else:
        log("RESULT:OK")

    with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(OUT) + "\n")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()

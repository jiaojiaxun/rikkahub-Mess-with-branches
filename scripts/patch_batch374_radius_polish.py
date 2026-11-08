#!/usr/bin/env python3
# rhPolish374: 视觉打磨 —— 圆角从 15 种值收敛到 6 种，pill 写法统一
#
# 370 的量化数据（668 个 Compose 文件）：
#   RoundedCornerShape 共 114 处，取值散成 15 种：
#     8dp×23  16dp×22  12dp×16  4dp×14  20dp×7  999dp×6
#     10dp×5  14dp×3  18dp×3  22dp×3  2dp×2  5dp×2  3dp×2  24dp×2  28dp×1
#   其中 8/12/16/20 是规范刻度，被 68/114 采用；剩下的是随手写的中间值。
#   999dp 是"胶囊"的老写法，应该用 percent = 50，语义正确且不依赖具体尺寸。
#
# 本批只做圆角，且**只动同时含 RoundedCornerShape 的行**，避免误伤：
#   999.dp                                 → percent = 50
#   14.dp / 18.dp                          → 16.dp
#   22.dp                                  → 20.dp
#   10.dp                                  → 12.dp
#   2.dp  / 3.dp / 5.dp                    → 4.dp
#   24.dp / 28.dp 保持不动（大面板可能是刻意设计）
#
# 为什么不做 padding：370 显示 padding 里 8/16/4/12 已占 84%、spacedBy 占 90%，
# 全量收敛是"改 733 处正确值"，收益低、回归面大。视觉上真正不统一的是圆角。
#
# 幂等：以"目标值已存在"为准 —— 每处替换都检查旧值是否还在，替换数写进 diag。
# 逐文件处理，每个文件处理前后做括号净差校验。

import os
import re
import sys

REPO = os.getcwd()
APP = os.path.join(REPO, "app", "src", "main", "java")
DIAG = os.path.join(REPO, "ci_diag_batch374_radius_polish.txt")

# 顺序敏感：长写法先处理
PILL = re.compile(r"RoundedCornerShape\(\s*999\.dp\s*\)")
DP_RULES = [
    ("14", "16"),
    ("18", "16"),
    ("22", "20"),
    ("10", "12"),
    ("5", "4"),
    ("3", "4"),
    ("2", "4"),
]

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
    pill_count = 0
    dp_counts = {old: 0 for old, _new in DP_RULES}

    for path in walk(APP):
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read()
        if "RoundedCornerShape" not in text:
            continue

        before = counts(text)
        out_lines = []
        file_pills = 0
        file_dp = 0

        for line in text.split("\n"):
            if "RoundedCornerShape" not in line:
                out_lines.append(line)
                continue
            new_line = line
            # 1) 胶囊写法
            new_pill, n_pill = PILL.subn("RoundedCornerShape(percent = 50)", new_line)
            if n_pill:
                new_line = new_pill
                file_pills += n_pill
            # 2) 中间值收敛（只在该行仍含 RoundedCornerShape 时）
            if "RoundedCornerShape" in new_line:
                for old, new in DP_RULES:
                    pattern = re.compile(r"(?<![\d.])" + old + r"\.dp")
                    replaced = 0
                    def _sub(match, _new=new):
                        nonlocal replaced
                        replaced += 1
                        return _new + ".dp"
                    new_line = pattern.sub(_sub, new_line)
                    if replaced:
                        file_dp += replaced
                        dp_counts[old] += replaced
            out_lines.append(new_line)

        if file_pills == 0 and file_dp == 0:
            continue

        updated = "\n".join(out_lines)
        after = counts(updated)
        if before != after:
            failures.append("braces:" + os.path.basename(path) + ":" + str(before) + "->" + str(after))
            continue

        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(updated)
        files_touched += 1
        pill_count += file_pills
        log("file:" + os.path.relpath(path, REPO) + " pill=" + str(file_pills) + " dp=" + str(file_dp))

    log("files-touched:" + str(files_touched))
    log("pill-999:" + str(pill_count))
    for old, new in DP_RULES:
        log("dp-" + old + "->" + new + ":" + str(dp_counts[old]))
    log("total-dp:" + str(sum(dp_counts.values())))

    # 复核：999 写法应彻底消失
    leftover = 0
    for path in walk(APP):
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            if "RoundedCornerShape(999.dp)" in handle.read():
                leftover += 1
                log("leftover:" + os.path.relpath(path, REPO))
    log("leftover-999:" + str(leftover))
    if leftover:
        failures.append("leftover-999:" + str(leftover))

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

#!/usr/bin/env python3
# rhPolish377: 只读精确 dump —— 把"该改什么、在哪、长什么样"全部摊开
#
# 375 的教训：我假设阴影写成 `cardElevation(defaultElevation = 4.dp)`，
# 结果 shadow-changes:0 —— 那 40 处 elevation 根本不是这个写法。
# ⇒ **改动型脚本必须先验证锚点存在；0 命中说明方案错了，不是"已完成"。**
#
# 本批不改任何代码，只输出四组数据，供下一批精确动手：
#   A) 628 处硬编码颜色里，Material3 语义色的副本（这是唯一能"换了不变味"的一类）：
#        0xFFFFDAD6 errorContainer / 0xFF93000A onErrorContainer
#        0xFFFFB4AB error(dark) / 0xFF690005 onError(dark) / 0xFFBA1A1A error(light)
#      每处输出文件 + 行号 + 前后 2 行，用于确认它是否在 @Composable 内
#   B) elevation 里 4/6/8dp 的**真实写法**（375 没匹配到的那些）
#   C) colorScheme.primary 按文件聚合，找出滥用最集中的 10 个文件
#   D) fillMaxWidth 按文件聚合 Top10（长文本页加 widthIn 的候选）
#
# 输出 ci_diag_batch377_polish_targets.txt。只读，永不 exit(1)。

import os
import re
from collections import Counter

REPO = os.getcwd()
APP = os.path.join(REPO, "app", "src", "main", "java")
DIAG = os.path.join(REPO, "ci_diag_batch377_polish_targets.txt")

M3_SEMANTIC = {
    "0xFFFFDAD6": "errorContainer",
    "0xFF93000A": "onErrorContainer",
    "0xFFFFB4AB": "error",
    "0xFF690005": "onError",
    "0xFFBA1A1A": "error",
}
HEX = re.compile(r"Color\(\s*(0x[0-9A-Fa-f]{6,8})\s*\)")
ELEV = re.compile(r"(?:shadowElevation|tonalElevation|defaultElevation|elevation)\s*=\s*(\d+)\.dp")

OUT = []


def log(line):
    OUT.append(line)
    print(line)


def walk(root):
    for folder, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith(".kt"):
                yield os.path.join(folder, name)


def main():
    primary_by_file = Counter()
    fill_by_file = Counter()
    semantic_hits = []
    elev_hits = []

    for path in walk(APP):
        rel = os.path.relpath(path, REPO)
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.read().split("\n")
        for index, line in enumerate(lines):
            if "colorScheme.primary" in line:
                primary_by_file[rel] += 1
            if "fillMaxWidth()" in line:
                fill_by_file[rel] += 1
            for value in HEX.findall(line):
                if value in M3_SEMANTIC:
                    semantic_hits.append((rel, index + 1, value, line.strip()[:100], lines))
            for match in ELEV.finditer(line):
                if match.group(1) in ("4", "6", "8"):
                    elev_hits.append((rel, index + 1, match.group(1), line.strip()[:110]))

    # A) M3 语义色副本
    log("=== A. M3 semantic color copies: " + str(len(semantic_hits)) + " ===")
    for rel, lineno, value, text, lines in semantic_hits:
        log("-- " + rel + " @line" + str(lineno) + "  " + value + " -> " + M3_SEMANTIC[value])
        for cursor in range(max(0, lineno - 3), min(len(lines), lineno + 2)):
            marker = ">>" if cursor == lineno - 1 else "  "
            log(marker + str(cursor + 1) + ": " + lines[cursor])

    # B) 阴影真实写法
    log("")
    log("=== B. elevation 4/6/8 real forms: " + str(len(elev_hits)) + " ===")
    for rel, lineno, value, text in elev_hits:
        log(rel + " @line" + str(lineno) + "  " + value + "dp :: " + text)

    # C) primary 分布
    log("")
    log("=== C. colorScheme.primary by file (top10) ===")
    for rel, count in primary_by_file.most_common(10):
        log("  x" + str(count) + "  " + rel)
    log("  total=" + str(sum(primary_by_file.values())) + " files=" + str(len(primary_by_file)))

    # D) fillMaxWidth 分布
    log("")
    log("=== D. fillMaxWidth by file (top10) ===")
    for rel, count in fill_by_file.most_common(10):
        log("  x" + str(count) + "  " + rel)
    log("  total=" + str(sum(fill_by_file.values())) + " files=" + str(len(fill_by_file)))

    log("")
    log("RESULT:OK")
    with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()

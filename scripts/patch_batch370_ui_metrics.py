#!/usr/bin/env python3
# rhUiMetrics370: 只读量化 —— 间距/圆角/字号/宽度到底有多乱
#
# 目的：把"AI 味"和"间距不统一"从主观感觉变成可核对的数字，再据此定规范。
# 不做任何代码修改，只统计 app 模块所有 Compose 文件：
#   1) padding(...) 里出现的 dp 值分布
#   2) Arrangement.spacedBy(...) 的 dp 值分布
#   3) RoundedCornerShape(...) 的 dp 值分布
#   4) widthIn/heightIn/size(...) 的 dp 值分布
#   5) fontSize = ...sp 的 sp 值分布
#   6) fillMaxWidth() 出现次数（宽度是否一律拉满）
#   7) colorScheme.primary 出现次数（强调色滥用指标）
#   8) 硬编码 Color(0x........) 次数
#
# 输出 ci_diag_batch370_ui_metrics.txt，每类给出 Top 15 与总数，附带"收敛建议"。
# 只读，永不 exit(1)。

import os
import re
from collections import Counter

REPO = os.getcwd()
APP = os.path.join(REPO, "app", "src", "main", "java")
DIAG = os.path.join(REPO, "ci_diag_batch370_ui_metrics.txt")

DP = re.compile(r"(\d+)\.dp")
SP = re.compile(r"(\d+)\.sp")
HEX_COLOR = re.compile(r"Color\(\s*0x[0-9A-Fa-f]{6,8}\s*\)")

# 各类统计的判定关键词（行级）
BUCKETS = {
    "padding": ["padding("],
    "spacedBy": ["spacedBy("],
    "rounded": ["RoundedCornerShape("],
    "size-limit": ["widthIn(", "heightIn(", "sizeIn("],
    "size": [".size("],
    "elevation": ["shadowElevation", "tonalElevation", "CardDefaults.cardElevation"],
}

OUT = []


def log(line):
    OUT.append(line)
    print(line)


def walk(root):
    for folder, _dirs, files in os.walk(root):
        for name in files:
            if name.endswith(".kt"):
                yield os.path.join(folder, name)


def top(counter, limit=15):
    items = counter.most_common(limit)
    return ", ".join(str(value) + "dp×" + str(count) for value, count in items) if items else "(none)"


def top_sp(counter, limit=15):
    items = counter.most_common(limit)
    return ", ".join(str(value) + "sp×" + str(count) for value, count in items) if items else "(none)"


def main():
    counters = {name: Counter() for name in BUCKETS}
    fonts = Counter()
    fill_max = 0
    primary_uses = 0
    hex_colors = 0
    files_scanned = 0

    for path in walk(APP):
        files_scanned += 1
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.read().split("\n")
        for line in lines:
            if "fillMaxWidth()" in line:
                fill_max += 1
            if "colorScheme.primary" in line:
                primary_uses += 1
            hex_colors += len(HEX_COLOR.findall(line))
            if "fontSize" in line:
                for value in SP.findall(line):
                    fonts[value] += 1
            for name, keys in BUCKETS.items():
                if any(key in line for key in keys):
                    for value in DP.findall(line):
                        counters[name][value] += 1

    log("files:" + str(files_scanned))
    log("")
    for name in ("padding", "spacedBy", "rounded", "size-limit", "size", "elevation"):
        total = sum(counters[name].values())
        log("[" + name + "] total=" + str(total))
        log("  top: " + top(counters[name]))

    log("")
    log("[fontSize] total=" + str(sum(fonts.values())))
    log("  top: " + top_sp(fonts))

    log("")
    log("fillMaxWidth:" + str(fill_max))
    log("colorScheme.primary:" + str(primary_uses))
    log("hardcoded-Color(0x..):" + str(hex_colors))

    # 收敛建议（写死在 diag 里，方便对照）
    log("")
    log("--- propose ---")
    log("spacing-scale: 4 / 8 / 12 / 16 / 24 / 32")
    log("radius-scale: 8 / 12 / 16 / 20 (pill=50%)")
    log("font-scale: 11 / 12 / 13 / 14 / 16 / 18 / 22")
    log("page-horizontal-padding: 16dp")
    log("card-inner-padding: 16dp")
    log("list-item-gap: 8dp")
    log("RESULT:OK")

    with open(DIAG, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()

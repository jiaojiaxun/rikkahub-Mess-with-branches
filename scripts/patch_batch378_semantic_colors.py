#!/usr/bin/env python3
# rhPolish378: M3 语义色的硬编码副本 → colorScheme（只动"参数位置"）
#
# 375 普查：628 处硬编码颜色 / 371 个不同色值。其中能"换了不变味"的只有一类 ——
# Material3 默认配色的语义色被抄成了字面量：
#   0xFFFFDAD6  errorContainer     ×9
#   0xFF93000A  onErrorContainer   ×9
#   0xFFFFB4AB  error (dark)       ×5
#   0xFF690005  onError (dark)     ×5
#   0xFFBA1A1A  error (light)      ×4
# 换成 colorScheme.* 后：视觉与默认主题一致，但**暗色模式下会自动适配**（现在写死的
# light 色值在暗色下对比度很差）。
#
# 关键风险与规避：
#   1) MaterialTheme 只在 @Composable 上下文可用 —— 如果某处在普通函数 / when 分支里
#      返回 Color(0xFF...)，替换后会 Unresolved reference。
#      ⇒ 本批**只替换"颜色参数位置"**：同一行必须出现
#         `color =` / `colors =` / `tint =` / `containerColor =` / `contentColor =` / `background(`
#         这类明确的 UI 参数写法。`-> Color(0xFF...)`、`val x = Color(0xFF...)` 一律跳过。
#   2) MaterialTheme 未 import —— 全部用全限定名
#      `androidx.compose.material3.MaterialTheme.colorScheme.xxx`，不动 import 区。
#   3) 同一文件可能有多处 —— 逐文件处理，替换前后做括号净差校验，不平就跳过该文件。
#
# 不做的：纯白 40 处 / 纯黑 19 处 / 深灰（0xFF343434 等）语义各异（卡片底/终端背景/遮罩），
# 盲改会坏事，留给后续按页面语义逐个处理。

import os
import re
import sys

REPO = os.getcwd()
APP = os.path.join(REPO, "app", "src", "main", "java")
DIAG = os.path.join(REPO, "ci_diag_batch378_semantic_colors.txt")

FQ = "androidx.compose.material3.MaterialTheme.colorScheme."

SEMANTIC = [
    ("0xFFFFDAD6", FQ + "errorContainer"),
    ("0xFF93000A", FQ + "onErrorContainer"),
    ("0xFFFFB4AB", FQ + "error"),
    ("0xFF690005", FQ + "onError"),
    ("0xFFBA1A1A", FQ + "error"),
]

PARAM_HINT = re.compile(
    r"(?:\bcolors?\s*=|\btint\s*=|\bcontainerColor\s*=|\bcontentColor\s*=|\bbackground\s*\()"
)

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
    total = {value: 0 for value, _ in SEMANTIC}
    files_touched = 0
    skipped_decl = 0

    for path in walk(APP):
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            text = handle.read()
        if "Color(" not in text:
            continue

        before = counts(text)
        out_lines = []
        file_count = 0

        for line in text.split("\n"):
            hit = any(("Color(" in line) and (value.lower() in line.lower()) for value, _ in SEMANTIC)
            if not hit:
                out_lines.append(line)
                continue
            # 声明行（val/var 在 = 之前）与 when 分支（-> 开头）一律跳过
            stripped = line.strip()
            if stripped.startswith("->") or re.search(r"\b(?:val|var)\s+\w+\s*=", line):
                skipped_decl += 1
                log("skip-decl:" + os.path.basename(path) + " :: " + stripped[:90])
                out_lines.append(line)
                continue
            # 必须在颜色参数位置
            if not PARAM_HINT.search(line):
                log("skip-nonparam:" + os.path.basename(path) + " :: " + stripped[:90])
                out_lines.append(line)
                continue

            new_line = line
            for value, replacement in SEMANTIC:
                pattern = re.compile(r"Color\(\s*" + value + r"\s*\)", re.IGNORECASE)
                new_line, n = pattern.subn(replacement, new_line)
                if n:
                    total[value] += n
                    file_count += n
            out_lines.append(new_line)

        if file_count == 0:
            continue

        updated = "\n".join(out_lines)
        after = counts(updated)
        if before != after:
            failures.append("braces:" + os.path.basename(path) + ":" + str(before) + "->" + str(after))
            continue

        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(updated)
        files_touched += 1
        log("file:" + os.path.relpath(path, REPO) + " x" + str(file_count))

    log("")
    log("files-touched:" + str(files_touched))
    for value, replacement in SEMANTIC:
        log(value + " -> " + replacement.rsplit(".", 1)[-1] + " : " + str(total[value]))
    log("total-replaced:" + str(sum(total.values())))
    log("skipped-decl-or-arrow:" + str(skipped_decl))

    # 复核：参数位置不应再有这 5 个色值
    leftover = 0
    for path in walk(APP):
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle.read().split("\n"):
                if not PARAM_HINT.search(line):
                    continue
                for value, _replacement in SEMANTIC:
                    if value.lower() in line.lower() and "Color(" in line:
                        leftover += 1
                        log("leftover:" + os.path.relpath(path, REPO) + " :: " + line.strip()[:90])
    log("leftover-param-position:" + str(leftover))
    if leftover:
        failures.append("leftover:" + str(leftover))

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

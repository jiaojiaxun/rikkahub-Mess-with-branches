#!/usr/bin/env python3
# batch227: 全量 marker 审计。
#
# 目的: 回答"200+ 个 patch 脚本里, 有多少改动其实没落到代码上"。
# 做法: 本脚本在链尾运行（sort -V 排最后, 此时源码树 = 全部脚本应用后的状态）:
#   1) 扫描 scripts/patch*.py, 提取每个脚本声明过的幂等 marker
#      （形如 MARK = "rhXxx" / NEW_MARK = '中文标记' 的赋值, 变量名含 MARK）
#   2) 在源码树里逐个查找 —— 关键: 扫描时排除 scripts/ 目录本身,
#      否则脚本源码里的 marker 字符串必然自命中, 全是假阳性
#   3) 有 marker 但源码里找不到 = 该脚本的改动没落地（或落地过又被后续脚本移除）
#
# 输出走 ::error 通道（项目惯例: ::notice 名额会被 OK 通知吃满, 匿名唯一可读通道）。
# 只读, 不改任何文件; 与其它脚本零冲突。
# 注意: 本脚本会被 warn-only sed 改写 exit(1) -> exit(0), 属预期行为。

import io
import os
import re
import sys

NL = chr(10)
Q = chr(34)
SQ = chr(39)

SCRIPTS_DIR = "scripts"
SKIP_DIRS = {".git", "scripts", "build", ".gradle", "node_modules", ".idea", ".kotlin", ".github"}
SCAN_EXT = (".kt", ".kts", ".xml", ".toml")

# 匹配: 变量名含 MARK 的赋值, 值用双引号或单引号包裹, 长度 3-80。
# 实测样例: MARK = "rhBatch217Wire" / NEW_MARK = '内联展开' / WIRE_MARK = "rhSqueezeWire"
MARK_RE = re.compile(
    "([A-Za-z_]*MARK[A-Za-z_]*)\\s*=\\s*("
    + Q + "([^" + Q + "]{3,80})" + Q
    + "|"
    + SQ + "([^" + SQ + "]{3,80})" + SQ
    + ")"
)


def report(msg):
    print("::error::" + msg)


def fail(msg):
    report(msg)
    sys.exit(1)


def read_text(path):
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""


def collect_marks():
    script_marks = {}
    total = 0
    try:
        names = sorted(os.listdir(SCRIPTS_DIR))
    except Exception as exc:
        fail("batch227-AUDIT cannot list scripts :: " + str(exc))
        return {}, 0
    for name in names:
        if not name.endswith(".py") or not name.startswith("patch"):
            continue
        total += 1
        text = read_text(os.path.join(SCRIPTS_DIR, name))
        marks = set()
        for m in MARK_RE.finditer(text):
            val = m.group(3) if m.group(3) is not None else m.group(4)
            if val and len(val) >= 3:
                marks.add(val)
        if marks:
            script_marks[name] = marks
    return script_marks, total


def build_haystack():
    parts = []
    for base, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in files:
            if fn.endswith(SCAN_EXT):
                parts.append(read_text(os.path.join(base, fn)))
    return NL.join(parts)


def main():
    script_marks, total = collect_marks()
    haystack = build_haystack()

    ok = []
    miss = []
    for name in sorted(script_marks.keys()):
        found = False
        for mk in script_marks[name]:
            if mk in haystack:
                found = True
                break
        if found:
            ok.append(name)
        else:
            miss.append(name)

    checkable = len(script_marks)
    uncheckable = total - checkable
    shown = ",".join(sorted(miss))[:1100]
    report(
        "batch227-AUDIT scripts=" + str(total)
        + " checkable=" + str(checkable)
        + " ok=" + str(len(ok))
        + " miss=" + str(len(miss))
        + " uncheckable=" + str(uncheckable)
        + " missList=[" + shown + "]"
    )
    print("batch227: done, scripts=" + str(total) + " checkable=" + str(checkable) + " miss=" + str(len(miss)))


if __name__ == "__main__":
    main()
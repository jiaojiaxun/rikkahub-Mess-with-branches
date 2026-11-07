#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhTokenUnit340 -- 把统计页的 token 显示接上 K/M 开关。

339 的全仓扫描（ci_diag_batch339_token_scan.txt）给出唯一真实的 token 显示点：
    app/src/main/java/me/rerere/rikkahub/ui/pages/stats/StatsPage.kt:615
    private fun formatTokens(count: Long): String = when { ... }
它被 12 处调用（模型/供应商/对话/日/月/年/输入/输出/缓存/总量）。

338 已经落地的部分（run#580 三档全绿实证）：
    TokenUnitStore.kt / RikkaHubApp init / 设置页开关 / ChatPage 标题
本批只补这最后一处：让 formatTokens 在开关打开时统一按百万。

K 模式完全保留原行为（B/M/K 自适应），只在 TokenUnitStore.millions=true 时走 M 分支。
不新增 import：用全限定名 me.rerere.rikkahub.utils.TokenUnitStore。
"""
import os
import sys

MARK = "rhTokenUnit340"
DIAG = "ci_diag_batch340_token_stats.txt"
REL = "app/src/main/java/me/rerere/rikkahub/ui/pages/stats/StatsPage.kt"
ROOT = os.path.abspath(os.getcwd())
rows = []


def note(msg):
    line = "[batch340] " + str(msg)
    print(line)
    rows.append(line)


def fail(msg):
    note("FAIL " + str(msg))
    try:
        with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
    except Exception:
        pass
    sys.exit(1)


def parens(t):
    return (
        t.count("(") - t.count(")"),
        t.count("{") - t.count("}"),
        t.count("[") - t.count("]"),
    )


NEW_BLOCK = '''private fun formatTokens(count: Long): String {
    // rhTokenUnit340: 默认 K（沿用原 B/M/K 自适应）；开关打开后统一按百万。
    if (!me.rerere.rikkahub.utils.TokenUnitStore.millions) {
        return when {
            count >= 1_000_000_000 -> "%.2fB".format(count / 1_000_000_000.0)
            count >= 1_000_000 -> "%.2fM".format(count / 1_000_000.0)
            count >= 1_000 -> "%.1fK".format(count / 1_000.0)
            else -> count.toString()
        }
    }
    if (count < 1000) return count.toString()
    val millions = count / 1_000_000.0
    return when {
        millions >= 100.0 -> millions.toInt().toString() + "M"
        millions >= 10.0 -> "%.1fM".format(millions)
        else -> "%.2fM".format(millions)
    }
}'''


def main():
    path = os.path.join(ROOT, REL)
    if not os.path.exists(path):
        fail("MISSING " + REL)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if MARK in text:
        note("already applied")
        return
    lines = text.split("\n")
    start = -1
    for i, line in enumerate(lines):
        if line.strip() == "private fun formatTokens(count: Long): String = when {":
            start = i
            break
    if start < 0:
        fail("formatTokens anchor not found")
    depth = 0
    end = -1
    for j in range(start, len(lines)):
        depth += lines[j].count("{") - lines[j].count("}")
        if j > start and depth == 0:
            end = j
            break
    if end < 0:
        fail("formatTokens closing brace not found")
    before = parens(text)
    lines[start:end + 1] = NEW_BLOCK.split("\n")
    out = "\n".join(lines)
    after = parens(out)
    if after != before:
        fail("BALANCE " + str(before) + " -> " + str(after))
    if "TokenUnitStore.millions" not in out:
        fail("SELFCHECK missing TokenUnitStore.millions")
    if "%.2fB" not in out:
        fail("SELFCHECK K branch lost")
    if "private fun formatTokens(count: Long): String = when {" in out:
        fail("SELFCHECK old signature still present")
    if "private fun formatTokens(count: Long): String {" not in out:
        fail("SELFCHECK new signature missing")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(out)
    note("formatTokens switched to TokenUnitStore (K default / M switch)")
    note("parens before=" + str(before) + " after=" + str(after))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except Exception as exc:  # noqa: BLE001
        note("EXCEPTION " + type(exc).__name__ + " " + str(exc)[:300])
    try:
        with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
    except Exception:
        pass
    print("::error::batch340 END lines=" + str(len(rows)))
    sys.exit(0)
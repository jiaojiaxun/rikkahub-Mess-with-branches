#!/usr/bin/env python3
# batch149 v2: 设置页"定时任务"重复行去重 (装机反馈 #6) —— 诊断优先, warn-only
#
# v1 回顾: 去重逻辑相同; 诊断 dump 用 ::notice —— 但 run annotations 里没露出来。
#   推断: 工作流只回显每个脚本末 2 行, 且 ::notice 通道被前段脚本(batch121-141 的
#   OK 通知)吃满, 后面的 notice 全被丢弃(另一会话的 batch165 诊断同样没露出来)。
# v2 改法: 全部诊断合并成【一行 ::warning】放在脚本最后 —— warning 通道几乎没人用,
#   且保证落在末 2 行内。去重逻辑不变, 行为不变。
# 任何意外只 warning, 绝不 exit 1; 不满足条件不写文件。

import io
import os

NL = chr(10)
Q = chr(34)
ZH = "app/src/main/res/values-zh/strings.xml"
SP = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPage.kt"
SI = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingsSearchIndex.kt"
NEEDLE = "定时任务"


def emit(findings, tag):
    line = "batch149v2[" + tag + "] "
    for f in findings:
        if len(line) > 1200:
            break
        line = line + f + " ;; "
    print("::warning::" + line)


def read(path):
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def depth_end(lines, start):
    depth = 0
    for j in range(start, len(lines)):
        ln = lines[j]
        depth += ln.count("(") - ln.count(")") + ln.count("{") - ln.count("}")
        if depth == 0 and j > start:
            return j
    return -1


def find_blocks(lines, match_indices):
    blocks = []
    for mi in match_indices:
        start = -1
        for j in range(mi, -1, -1):
            if lines[j].strip().startswith("item("):
                start = j
                break
        if start < 0:
            continue
        end = depth_end(lines, start)
        if end < 0:
            continue
        dup = False
        for b in blocks:
            if b[0] == start:
                dup = True
                break
        if not dup:
            blocks.append((start, end))
    return blocks


def block_text(lines, b):
    return NL.join(lines[b[0]:b[1] + 1])


def nav_target(txt):
    for ln in txt.split(NL):
        if "Screen." in ln:
            return ln.strip()
    return ""


def main():
    findings = []
    zh = read(ZH)
    if zh is None:
        emit(["values-zh missing"], "skip")
        return
    keys = []
    tag = "name=" + Q
    for ln in zh.split(NL):
        if NEEDLE in ln:
            p = ln.find(tag)
            if p >= 0:
                q = ln.find(Q, p + len(tag))
                if q > p:
                    keys.append(ln[p + len(tag):q])
    ks = ""
    for k in keys:
        if ks != "":
            ks = ks + ","
        ks = ks + k
    findings.append("keys=[" + ks + "]")
    if not keys:
        emit(findings, "no-cron-strings")
        return

    src = read(SP)
    if src is None:
        emit(findings, "settingpage-missing")
        return
    lines = src.split(NL)
    hits = []
    for i, ln in enumerate(lines):
        if NEEDLE in ln:
            hits.append(i)
            continue
        for k in keys:
            if ("R.string." + k) in ln:
                hits.append(i)
                break
    blocks = find_blocks(lines, hits)
    findings.append("hits=" + str(len(hits)))
    findings.append("blocks=" + str(len(blocks)))

    if len(blocks) == 2:
        s0 = nav_target(block_text(lines, blocks[0]))
        s1 = nav_target(block_text(lines, blocks[1]))
        findings.append("nav0[" + s0 + "]")
        findings.append("nav1[" + s1 + "]")
        if s0 != "" and s0 == s1:
            b = blocks[1]
            del_start = b[0]
            if del_start > 0 and lines[del_start - 1].strip() == "":
                del_start -= 1
            del lines[del_start:b[1] + 1]
            out = NL.join(lines)
            if out.count("(") - src.count("(") != out.count(")") - src.count(")"):
                findings.append("action=skip-paren-delta")
            elif out.count("{") - src.count("{") != out.count("}") - src.count("}"):
                findings.append("action=skip-brace-delta")
            else:
                try:
                    with io.open(SP, "w", encoding="utf-8") as f:
                        f.write(out)
                    findings.append("action=removed(was " + str(b[0] + 1) + "-" + str(b[1] + 1) + ")")
                except Exception:
                    findings.append("action=write-failed")
        else:
            findings.append("action=skip-nav-differs")
    else:
        findings.append("action=skip-blocks")

    if os.path.exists(SI):
        si = read(SI)
        if si is not None:
            si_lines = si.split(NL)
            si_hits = []
            for i, ln in enumerate(si_lines):
                if NEEDLE in ln:
                    si_hits.append(i)
                    continue
                for k in keys:
                    if ("R.string." + k) in ln:
                        si_hits.append(i)
                        break
            if si_hits:
                findings.append("mirror_hits=" + str(len(si_hits)))
                shown = 0
                for i in si_hits:
                    if shown >= 3:
                        break
                    findings.append("mL" + str(i + 1))
                    shown += 1
            else:
                findings.append("mirror=clean")
    else:
        findings.append("mirror=absent")

    emit(findings, "done")


if __name__ == "__main__":
    main()

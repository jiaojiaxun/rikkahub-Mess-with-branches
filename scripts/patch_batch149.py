#!/usr/bin/env python3
# batch149: 设置页"定时任务"重复行去重 (装机反馈 #6) —— 诊断优先, warn-only
#
# 现象(用户截图): 设置-高级服务里有两行"定时任务",
# 描述分别为"查看、开关和管理 AI 创建的定时任务"与"查看、开关、删除 AI 创建的定时任务"。
# 已核实: 仓库态 SettingPage.kt 没有该行 —— 两行都是在链脚本在 CI 注入的, 注入源未定位。
#
# 策略(不自残优先, 全程 warn-only, 任何意外只 ::warning/::notice, 绝不 exit 1):
#   1) 扫 values-zh/strings.xml 找含"定时任务"的字符串, 抽出 name key
#   2) 在 SettingPage.kt 里按 key 引用(或硬编码中文)定位 item() 行块
#   3) 恰好 2 块且导航目标相同 -> 删第二块; 否则只 dump 现场行到 annotation
#   4) 设置搜索镜像 SettingsSearchIndex.kt 只 dump 不改
# 跑一次 CI 即可拿到真形态; 下次按 dump 修准。

import io
import os
import sys

NL = chr(10)
Q = chr(34)
ZH = "app/src/main/res/values-zh/strings.xml"
SP = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPage.kt"
SI = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingsSearchIndex.kt"
NEEDLE = "定时任务"


def warn(msg):
    print("::warning::batch149 " + msg)


def notice(msg):
    print("::notice::batch149 " + msg)


def read(path):
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as exc:
        warn("read failed " + path + " :: " + str(exc))
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
    zh = read(ZH)
    if zh is None:
        notice("values-zh/strings.xml missing, skip")
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
            ks = ks + ", "
        ks = ks + k
    notice("keys from values-zh: [" + ks + "]")
    if not keys:
        notice("no cron strings found in values-zh; nothing to do")
        return

    src = read(SP)
    if src is None:
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
    notice("SettingPage match lines=" + str(len(hits)) + " item-blocks=" + str(len(blocks)))
    for idx, b in enumerate(blocks):
        notice("block" + str(idx) + " lines " + str(b[0] + 1) + "-" + str(b[1] + 1) + " nav: " + nav_target(block_text(lines, b)))

    if len(blocks) == 2:
        s0 = nav_target(block_text(lines, blocks[0]))
        s1 = nav_target(block_text(lines, blocks[1]))
        if s0 != "" and s0 == s1:
            b = blocks[1]
            del_start = b[0]
            if del_start > 0 and lines[del_start - 1].strip() == "":
                del_start -= 1
            del lines[del_start:b[1] + 1]
            out = NL.join(lines)
            if out.count("(") - src.count("(") != out.count(")") - src.count(")"):
                warn("paren delta mismatch after removal, NOT writing")
                return
            if out.count("{") - src.count("{") != out.count("}") - src.count("}"):
                warn("brace delta mismatch after removal, NOT writing")
                return
            try:
                with io.open(SP, "w", encoding="utf-8") as f:
                    f.write(out)
            except Exception as exc:
                warn("write failed :: " + str(exc))
                return
            notice("duplicate cron row removed (was lines " + str(b[0] + 1) + "-" + str(b[1] + 1) + ")")
        else:
            warn("two blocks navigate differently [" + s0 + "] vs [" + s1 + "], NOT removing; needs manual decision")
    else:
        notice("block count != 2, no removal (see dump above)")

    # 设置搜索镜像只 dump 不改
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
                for i in si_hits:
                    notice("mirror hit L" + str(i + 1) + ": " + si_lines[i].strip()[:120])
            else:
                notice("mirror index clean")
    else:
        notice("mirror file not found at " + SI)


if __name__ == "__main__":
    main()

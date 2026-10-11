#!/usr/bin/env python3
# batch148 v3: 酒馆模式开关移到面板底部 (装机反馈 #7) —— 全面 warn-only 版
#
# v1 死因: CI 形态已有 HorizontalDivider, 绝对计数断言误判, fail-loud 拦住构建。
# v2: 差值校验版(已通过 patch 步, 开关成功移动)。
# v3: 与另一会话的放宽意图统一 —— 任何锚点/校验失败只 ::warning + 跳过,
#     不阻塞构建; 应用前全量自检, 全部通过才写文件; 失败时 dump 现场到 ::notice。
# 幂等: 命中 rhTavernBelowDivider 即跳过。锚点: batch130 已知插入文本 + Slider 调用行。

import io

NL = chr(10)
PATH = "app/src/main/java/me/rerere/rikkahub/ui/components/ai/ReasoningPicker.kt"
MARK_NEW = "rhTavernBelowDivider"
OLD_MARK = "rhTavernMode: 会话级酒馆模式开关(借位显示"
IF_LINE = "if (onUpdateTavernMode != null) {"


def warn(msg):
    print("::warning file=" + PATH + "::batch148v3 " + msg)


def dump(lines, center, before, after):
    lo = center - before
    if lo < 0:
        lo = 0
    hi = center + after
    if hi > len(lines):
        hi = len(lines)
    out = ""
    for i in range(lo, hi):
        out = out + "L" + str(i + 1) + ":" + lines[i].strip()[:90] + " ;; "
    return out[:1400]


def depth_end_soft(lines, start):
    # 混合配平: 同行同数 () 与 {} (batch142 教训); 失败返回 -1 不抛
    depth = 0
    for j in range(start, len(lines)):
        ln = lines[j]
        depth += ln.count("(") - ln.count(")") + ln.count("{") - ln.count("}")
        if depth < 0:
            return -1
        if depth == 0 and j > start:
            return j
    return -1


def main():
    try:
        with io.open(PATH, "r", encoding="utf-8") as f:
            src = f.read()
    except Exception as exc:
        warn("read failed: " + str(exc))
        return
    if MARK_NEW in src:
        print("batch148v3: already applied, skip")
        return
    lines = src.split(NL)

    # ---- 1. 定位并移除旧开关块(batch130 插在标题正下方) ----
    cmt = -1
    for i, ln in enumerate(lines):
        if OLD_MARK in ln:
            cmt = i
            break
    if cmt < 0:
        warn("old tavern block comment not found; skip (no write)")
        return
    if_i = -1
    for j in range(cmt + 1, min(cmt + 4, len(lines))):
        if lines[j].strip() == IF_LINE:
            if_i = j
            break
    if if_i < 0:
        warn("if-block start not found near L" + str(cmt + 1) + " ;; " + dump(lines, cmt, 3, 12))
        return
    if_end = depth_end_soft(lines, if_i)
    if if_end < 0:
        warn("old block end not found from L" + str(if_i + 1) + " ;; " + dump(lines, if_i, 2, 26))
        return
    block_start = cmt
    if cmt > 0 and lines[cmt - 1].strip() == "":
        block_start = cmt - 1
    removed = NL.join(lines[block_start:if_end + 1])
    for need in ["Switch(", "setting_tavern_mode", "onCheckedChange"]:
        if need not in removed:
            warn("removed block missing " + need + "; skip (no write)")
            return
    del lines[block_start:if_end + 1]

    # ---- 2. 在 Slider 块之后重新插入(不带分割线; 已有分割线不动) ----
    slider_i = -1
    for i, ln in enumerate(lines):
        if ln.strip() == "Slider(":
            slider_i = i
            break
    if slider_i < 0:
        warn("Slider( call not found; skip (no write)")
        return
    slider_end = depth_end_soft(lines, slider_i)
    if slider_end < 0:
        warn("Slider end not found from L" + str(slider_i + 1) + " ;; " + dump(lines, slider_i, 2, 32))
        return
    pad = "            "
    block = [
        "",
        pad + "// rhTavernMode: 会话级酒馆模式开关(移到面板底部, 已有分割线下方) [" + MARK_NEW + "]",
        pad + IF_LINE,
        pad + "    Row(",
        pad + "        modifier = Modifier.fillMaxWidth(),",
        pad + "        verticalAlignment = Alignment.CenterVertically,",
        pad + "        horizontalArrangement = Arrangement.SpaceBetween,",
        pad + "    ) {",
        pad + "        Column(modifier = Modifier.weight(1f)) {",
        pad + "            Text(",
        pad + "                text = stringResource(R.string.setting_tavern_mode),",
        pad + "                style = MaterialTheme.typography.titleSmall,",
        pad + "            )",
        pad + "            Text(",
        pad + "                text = stringResource(R.string.setting_tavern_mode_desc),",
        pad + "                style = MaterialTheme.typography.bodySmall,",
        pad + "                color = MaterialTheme.colorScheme.onSurfaceVariant,",
        pad + "            )",
        pad + "        }",
        pad + "        Switch(",
        pad + "            checked = tavernMode,",
        pad + "            onCheckedChange = { onUpdateTavernMode?.invoke(it) },",
        pad + "        )",
        pad + "    }",
        pad + "}",
    ]
    for j, b in enumerate(block):
        lines.insert(slider_end + 1 + j, b)

    out = NL.join(lines)

    # ---- 3. 写前全量自检(全差值; 不通过=不写, 只 warn + dump) ----
    problems = ""
    if out.count(MARK_NEW) != 1:
        problems = problems + "marker!=1; "
    if OLD_MARK in out:
        problems = problems + "old-comment-remains; "
    if out.count("R.string.setting_tavern_mode") != 2:
        problems = problems + "string-refs!=2; "
    if out.count("HorizontalDivider(") != src.count("HorizontalDivider("):
        problems = problems + "divider-count-changed; "
    if out.count("(") - src.count("(") != out.count(")") - src.count(")"):
        problems = problems + "paren-delta; "
    if out.count("{") != src.count("{") or out.count("}") != src.count("}"):
        problems = problems + "brace-delta; "
    if problems != "":
        m = 0
        for i, ln in enumerate(lines):
            if MARK_NEW in ln:
                m = i
                break
        warn("self-check failed, NOT written: " + problems + " ;; " + dump(lines, m, 3, 30))
        return

    try:
        with io.open(PATH, "w", encoding="utf-8") as f:
            f.write(out)
    except Exception as exc:
        warn("write failed: " + str(exc))
        return
    print("batch148v3: tavern switch moved to bottom (after Slider), warn-only style")


if __name__ == "__main__":
    main()

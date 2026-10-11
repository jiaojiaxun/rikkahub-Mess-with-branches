#!/usr/bin/env python3
# batch148: 酒馆模式开关移到分割线下面 (装机反馈 #7)
#
# batch130 把开关插在了思考深度面板标题正下方; 用户要求挪到分割线下面。
# 本脚本在 CI 形态下:
#   1) 移除 batch130 插入的旧位置开关块 (锚点 = batch130 的已知插入文本)
#   2) 在 Slider 块之后重新插入 [HorizontalDivider + 开关]
#      (面板原本没有分割线, 顺便补上, 正好对齐"分割线下面"的描述)
# 幂等: 命中 rhTavernBelowDivider 即跳过。
# 括号纪律: 用「与原始文件的差值」校验配平, 不做全文件绝对计数。

import io
import sys

NL = chr(10)
PATH = "app/src/main/java/me/rerere/rikkahub/ui/components/ai/ReasoningPicker.kt"
MARK_NEW = "rhTavernBelowDivider"
OLD_MARK = "rhTavernMode: 会话级酒馆模式开关(借位显示"
IF_LINE = "if (onUpdateTavernMode != null) {"


def fail(msg):
    print("::error file=" + PATH + "::batch148 " + msg)
    sys.exit(1)


def depth_end(lines, start):
    # 混合配平: 同行同数 () 与 {} (batch142 教训: 只数花括号会在 onClick={...}, 行误判)
    depth = 0
    for j in range(start, len(lines)):
        ln = lines[j]
        depth += ln.count("(") - ln.count(")") + ln.count("{") - ln.count("}")
        if depth == 0 and j > start:
            return j
        if depth < 0:
            fail("depth went negative at line " + str(j + 1))
    fail("block end not found from line " + str(start + 1))
    return -1


def main():
    with io.open(PATH, "r", encoding="utf-8") as f:
        src = f.read()
    if MARK_NEW in src:
        print("batch148: already applied, skip")
        return
    lines = src.split(NL)

    # ---- 1. 定位并移除旧开关块 ----
    cmt = -1
    for i, ln in enumerate(lines):
        if OLD_MARK in ln:
            cmt = i
            break
    if cmt < 0:
        fail("old tavern block comment not found; file unchanged")
    if_i = -1
    for j in range(cmt + 1, min(cmt + 4, len(lines))):
        if lines[j].strip() == IF_LINE:
            if_i = j
            break
    if if_i < 0:
        fail("tavern if-block start not found near line " + str(cmt + 1))
    if_end = depth_end(lines, if_i)
    block_start = cmt
    if cmt > 0 and lines[cmt - 1].strip() == "":
        block_start = cmt - 1
    removed = NL.join(lines[block_start:if_end + 1])
    for need in ["Switch(", "setting_tavern_mode", "onCheckedChange"]:
        if need not in removed:
            fail("removed block missing " + need + "; abort before write")
    del lines[block_start:if_end + 1]

    # ---- 2. 在 Slider 块之后重新插入 ----
    slider_i = -1
    for i, ln in enumerate(lines):
        if ln.strip() == "Slider(":
            slider_i = i
            break
    if slider_i < 0:
        fail("Slider( call not found; abort before write")
    slider_end = depth_end(lines, slider_i)
    pad = "            "
    block = [
        "",
        pad + "// rhTavernMode: 会话级酒馆模式开关(移到分割线下方) [" + MARK_NEW + "]",
        pad + IF_LINE,
        pad + "    androidx.compose.material3.HorizontalDivider(modifier = Modifier.padding(vertical = 4.dp))",
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

    # ---- 3. 自检(差值校验) ----
    if out.count(MARK_NEW) != 1:
        fail("new marker count != 1")
    if OLD_MARK in out:
        fail("old block comment still present")
    if out.count("R.string.setting_tavern_mode") != 2:
        fail("tavern string refs != 2 (title+desc)")
    if out.count("HorizontalDivider(") != 1:
        fail("divider count != 1")
    if out.count("(") - src.count("(") != out.count(")") - src.count(")"):
        fail("paren delta mismatch")
    if out.count("{") != src.count("{") or out.count("}") != src.count("}"):
        fail("brace count changed")

    with io.open(PATH, "w", encoding="utf-8") as f:
        f.write(out)
    print("batch148: tavern switch moved below divider (after Slider)")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
# rhRemote355k: 修 SettingPhoneControlPage.kt 缺 utils.plus import（run622 编译红）
# 非本批引入: 该文件由并行会话 348b(手机操控设置页) 新增。
# 现象: L102 Unresolved reference 'plus' for operator '+' on receiver of type 'PaddingValues'
# 根因: PaddingValues + PaddingValues 是 me.rerere.rikkahub.utils.plus 扩展, 文件未 import。
# 修法: 补一条标准 import（幂等）。
# 自检吸取 355i 教训: 不断言外部可变状态(用法计数只记录, 不判 FAIL)。
import os

DIAG = "ci_diag_batch355k_phone_padding.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())

path = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPhoneControlPage.kt"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

diag = []
ok = True

ANCHOR = "import me.rerere.rikkahub.ui.theme.CustomColors\n"
ADD = "import me.rerere.rikkahub.utils.plus\n"

if ADD in text:
    diag.append("import:already")
elif text.count(ANCHOR) == 1:
    text = text.replace(ANCHOR, ANCHOR + ADD, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    diag.append("import:added")
else:
    diag.append("import:ANCHOR-MISMATCH(" + str(text.count(ANCHOR)) + ")")
    ok = False

# 只断言自己的产物
if ADD not in text:
    diag.append("MISS:import")
    ok = False

# 外部状态只记录不判死（355i 教训）
uses = text.count("innerPadding + PaddingValues")
diag.append("paddingPlus:" + str(uses))
if uses == 0:
    diag.append("NOTE:usage-not-found(import 仍无害)")

# import 位置必须在第一个 @Composable 之前
first_composable = text.find("@Composable")
import_pos = text.find(ADD)
if import_pos < 0 or (first_composable >= 0 and import_pos > first_composable):
    diag.append("POSITION:not-in-imports")
    ok = False

if text.count("{") != text.count("}"):
    diag.append("BRACES(" + str(text.count("{")) + "/" + str(text.count("}")) + ")")
    ok = False
# 括号配平（新增 import 不影响，但顺带核对文件完整性）
if text.count("(") != text.count(")"):
    diag.append("PARENS(" + str(text.count("(")) + "/" + str(text.count(")")) + ")")
    ok = False

diag.append("RESULT:" + ("OK" if ok else "FAIL"))
with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
    f.write("\n".join(diag) + "\n")
print(" | ".join(diag))
if not ok:
    print("::error title=batch355k::" + " | ".join(diag))

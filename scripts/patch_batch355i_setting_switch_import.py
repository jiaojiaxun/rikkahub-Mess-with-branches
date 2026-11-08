#!/usr/bin/env python3
# rhRemote355i: 修 SettingPage.kt 缺 Switch import（run618 编译红，非本批引入）
# 现象: L304/317/330 Unresolved reference 'Switch' + L306/319/332 'enabled' 类型无法推断
# 根因: import 区无 androidx.compose.material3.Switch, 但文件里用了 Switch(...);
#       Switch 未解析 -> onCheckedChange lambda 参数 enabled 无类型来源, 连带报错。
# 来源: 并行会话在 355g 与 355h 之间推了引入 Switch 的改动, 355h 的新 head 把它带进编译。
# 修法: 补一条标准 import（幂等; 若对方已修则跳过）。
import os

DIAG = "ci_diag_batch355i_remote.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())

path = "app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPage.kt"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

diag = []
ok = True

ANCHOR = "import androidx.compose.material3.Scaffold\n"
ADD = "import androidx.compose.material3.Switch\n"

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

if ADD not in text:
    diag.append("MISS:import")
    ok = False
uses = text.count("Switch(")
diag.append("uses:" + str(uses))
if uses < 1:
    diag.append("MISS:switch-usage")
    ok = False
if text.count("{") != text.count("}"):
    diag.append("BRACES(" + str(text.count("{")) + "/" + str(text.count("}")) + ")")
    ok = False
first_composable = text.find("@Composable")
import_pos = text.find(ADD)
if import_pos < 0 or import_pos > first_composable:
    diag.append("POSITION:not-in-imports")
    ok = False

diag.append("RESULT:" + ("OK" if ok else "FAIL"))
with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
    f.write("\n".join(diag) + "\n")
print(" | ".join(diag))
if not ok:
    print("::error title=batch355i::" + " | ".join(diag))

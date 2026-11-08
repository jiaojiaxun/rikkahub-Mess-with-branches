#!/usr/bin/env python3
# rhRemote355j: 双存储区切换器的多选防御
# 缺陷(355h 自我抗辩发现): 多选模式下 area 切换器仍显示; 切换后 selectedPaths 仍是旧区路径,
#   VM.selectArea 只重置 path/entries/error, 不动 DetailPage 层的选中集合 → 导出选中会错乱/失败。
# 修法(最小): 多选期间不显示切换器, 从源头避免跨区选中。
import os

DIAG = "ci_diag_batch355j_remote.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())

path = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceDetailPage.kt"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

diag = []
ok = True

ANCHOR = """        item {
            WorkspaceAreaSelector(area = area, onSelectArea = onSelectArea)
        }
"""
REPL = """        // 多选期间不显示切换器: 切区会重置 path/entries, 但调用方的选中集合不会同步,
        // 跨区导出选中会点到不存在的路径。
        if (!selectionMode) {
            item {
                WorkspaceAreaSelector(area = area, onSelectArea = onSelectArea)
            }
        }
"""

if "if (!selectionMode) {\n            item {\n                WorkspaceAreaSelector(" in text:
    diag.append("gate:already")
elif text.count(ANCHOR) == 1:
    text = text.replace(ANCHOR, REPL, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    diag.append("gate:ok")
else:
    diag.append("gate:ANCHOR-MISMATCH(" + str(text.count(ANCHOR)) + ")")
    ok = False

# 自检: 组件仍存在 + 门控括号完整包住 item + 全文件括号配平
if "WorkspaceAreaSelector(area = area, onSelectArea = onSelectArea)" not in text:
    diag.append("MISS:selector-removed")
    ok = False
start = text.find("if (!selectionMode) {\n            item {\n                WorkspaceAreaSelector(")
if start < 0:
    diag.append("MISS:gate")
    ok = False
else:
    depth = 0
    end = -1
    for i in range(start, min(len(text), start + 500)):
        c = text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end < 0 or "WorkspaceAreaSelector" not in text[start:end]:
        diag.append("BRACE:gate-not-wrapping")
        ok = False
    else:
        diag.append("BRACE:ok")
if text.count("{") != text.count("}"):
    diag.append("FILE-BRACES(" + str(text.count("{")) + "/" + str(text.count("}")) + ")")
    ok = False

diag.append("RESULT:" + ("OK" if ok else "FAIL"))
with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
    f.write("\n".join(diag) + "\n")
print(" | ".join(diag))
if not ok:
    print("::error title=batch355j::" + " | ".join(diag))

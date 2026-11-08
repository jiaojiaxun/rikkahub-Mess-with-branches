#!/usr/bin/env python3
# rhRemote355q: TabRow 空列表守卫（355p 自我抗辩发现的运行时崩溃）
# 缺陷: tabs 为空时(ensureSession 启动 → SSH 建连完成之间有窗口),
#       TabRow(selectedTabIndex = 0) 在 count=0 越界 → IllegalArgumentException。
#       新建按钮在 Row 里, 不能整行隐藏, 只能把 TabRow 单独包条件。
# 修法: if (tabs.isEmpty()) Box(weight 1f) else TabRow(...); IconButton 始终在。
import os

DIAG = "ci_diag_batch355q_tabs_guard.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())

path = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceTerminalPage.kt"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

diag = []
ok = True

# 锚 1: TabRow 开头
A1 = "                        TabRow(\n"
R1 = (
    "                        if (tabsState.tabs.isEmpty()) {\n"
    "                            // 建连窗口内 tabs 为空: TabRow(selectedTabIndex=0) 会越界崩溃\n"
    "                            Box(modifier = Modifier.weight(1f))\n"
    "                        } else {\n"
    "                        TabRow(\n"
)
# 锚 2: TabRow 闭合 + IconButton 开始
A2 = "                        }\n                        IconButton(\n                            enabled = workspace != null && !tabsState.isCreating,\n"
R2 = "                        }\n                        }\n                        IconButton(\n                            enabled = workspace != null && !tabsState.isCreating,\n"

if "if (tabsState.tabs.isEmpty()) {" in text:
    diag.append("guard:already")
else:
    if text.count(A1) != 1:
        diag.append("anchor1:MISMATCH(" + str(text.count(A1)) + ")")
        ok = False
    elif text.count(A2) != 1:
        diag.append("anchor2:MISMATCH(" + str(text.count(A2)) + ")")
        ok = False
    else:
        text = text.replace(A1, R1, 1)
        text = text.replace(A2, R2, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        diag.append("guard:ok")

# 自检
final = open(path, "r", encoding="utf-8").read()
for needle in (
    "if (tabsState.tabs.isEmpty()) {",
    "Box(modifier = Modifier.weight(1f))",
    "} else {",
    "IconButton(\n                            enabled = workspace != null && !tabsState.isCreating,",
):
    if needle not in final:
        diag.append("MISS:" + needle[:40].replace("\n", "|"))
        ok = False


def strip_literals(src):
    res = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c == '/' and i + 1 < n and src[i + 1] == '/':
            while i < n and src[i] != '\n':
                i += 1
            continue
        if c == '/' and i + 1 < n and src[i + 1] == '*':
            i += 2
            while i + 1 < n and not (src[i] == '*' and src[i + 1] == '/'):
                i += 1
            i += 2
            continue
        if c == '"':
            if src.startswith('"""', i):
                i += 3
                while i + 2 < n and not src.startswith('"""', i):
                    i += 1
                i += 3
                continue
            i += 1
            while i < n:
                if src[i] == '\\':
                    i += 2
                    continue
                if src[i] == '"':
                    i += 1
                    break
                i += 1
            continue
        if c == "'":
            i += 1
            while i < n:
                if src[i] == '\\':
                    i += 2
                    continue
                if src[i] == "'":
                    i += 1
                    break
                i += 1
            continue
        res.append(c)
        i += 1
    return "".join(res)


clean = strip_literals(final)
for pname, left, right in (("braces", "{", "}"), ("parens", "(", ")")):
    d = clean.count(left) - clean.count(right)
    diag.append(pname + "-diff:" + str(d))
    if d != 0:
        ok = False

diag.append("RESULT:" + ("OK" if ok else "FAIL"))
with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
    f.write("\n".join(diag) + "\n")
print(" | ".join(diag))
if not ok:
    print("::error title=batch355q::" + " | ".join(diag))

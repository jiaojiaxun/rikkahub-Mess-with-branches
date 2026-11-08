#!/usr/bin/env python3
# rhRemote355n: 修 355m 遗漏的 import（run629 编译红）
# 现象: WorkspaceFileEditorPage.kt:85 Unresolved reference 'stringResource' / 'R'
# 根因: 355m 在 TopAppBar title 里用了 stringResource(R.string.workspace_file_read_only),
#       但该文件 import 区既没有 androidx.compose.ui.res.stringResource 也没有 me.rerere.rikkahub.R。
# 铁律①(import 清单)失守: 跨包符号必须逐个核对 import。
# 自检改进: 括号配平先剥离字符串与注释（355l 的 BRACES(49/48)/PARENS(167/166) 就是
#   字符串 "([{<\"'" 造成的假阳性, 不是代码损坏）。
import os
import re

DIAG = "ci_diag_batch355n_editor_import.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())

path = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceFileEditorPage.kt"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

diag = []
ok = True

EDIT1_NEEDLE = "import androidx.compose.ui.Modifier\n"
EDIT1_REPL = "import androidx.compose.ui.Modifier\nimport androidx.compose.ui.res.stringResource\n"

EDIT2_NEEDLE = "import me.rerere.rikkahub.data.repository.WorkspaceRepository\n"
EDIT2_REPL = "import me.rerere.rikkahub.R\nimport me.rerere.rikkahub.data.repository.WorkspaceRepository\n"

for label, needle, repl in (
    ("import-stringResource", EDIT1_NEEDLE, EDIT1_REPL),
    ("import-R", EDIT2_NEEDLE, EDIT2_REPL),
):
    if repl in text:
        diag.append(label + ":already")
        continue
    if text.count(needle) != 1:
        diag.append(label + ":ANCHOR-MISMATCH(" + str(text.count(needle)) + ")")
        ok = False
        continue
    text = text.replace(needle, repl, 1)
    diag.append(label + ":ok")

with open(path, "w", encoding="utf-8") as f:
    f.write(text)

# 自检 1: 两个 import 必须存在
for needle in (
    "import androidx.compose.ui.res.stringResource\n",
    "import me.rerere.rikkahub.R\n",
):
    if needle not in text:
        diag.append("MISS:" + needle.strip())
        ok = False

# 自检 2: 用法与 import 必须对应（只断言本批相关符号）
if "stringResource(" not in text:
    diag.append("MISS:stringResource-usage")
    ok = False
if "R.string.workspace_file_read_only" not in text:
    diag.append("MISS:R-usage")
    ok = False

# 自检 3: 剥离字符串与注释后再统计括号（避免字符串假阳性）
def strip_literals(src: str) -> str:
    out = []
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
        out.append(c)
        i += 1
    return "".join(out)


clean = strip_literals(text)
for pair_label, left, right in (("braces", "{", "}"), ("parens", "(", ")")):
    diff = clean.count(left) - clean.count(right)
    diag.append(pair_label + "-diff:" + str(diff))
    if diff != 0:
        ok = False
diag.append("raw-braces(" + str(text.count("{")) + "/" + str(text.count("}")) + ")")
diag.append("raw-parens(" + str(text.count("(")) + "/" + str(text.count(")")) + ")")

diag.append("RESULT:" + ("OK" if ok else "FAIL"))
with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
    f.write("\n".join(diag) + "\n")
print(" | ".join(diag))
if not ok:
    print("::error title=batch355n::" + " | ".join(diag))

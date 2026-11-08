#!/usr/bin/env python3
# rhRemote355o: WorkspaceFileEditorPage import 去重（run631 编译红）
# run631: line34/35 Conflicting import: imported name 'R' is ambiguous
# 真相: 并行会话 348e 与我的 355n 各自加了同两条 import：
#   28 import androidx.compose.ui.res.stringResource            (355n, 无注释)
#   31 import androidx.compose.ui.res.stringResource // rhPhone348e (348e)
#   34 import me.rerere.rikkahub.R // rhPhone348e              (348e)
#   35 import me.rerere.rikkahub.R                             (355n)
# 355n 的幂等检查写成 `if repl in text`（整块两行），348e 的 R 行带行内注释 → 整块不匹配
# → 355n 又插一条 → 两个 R / 两个 stringResource。
# 修法: 按「规范形式」（剥离 " // ..." 行内注释）对 import 区去重, 保留首次出现。
import os

DIAG = "ci_diag_batch355o_editor_dedupe.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())

path = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceFileEditorPage.kt"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

diag = []
ok = True

# ---- 去重（只处理 import 行）----
lines = text.split("\n")
seen = set()
out = []
removed = []
for line in lines:
    s = line.strip()
    if s.startswith("import "):
        canonical = s.split(" // ")[0].strip() if " // " in s else s
        if canonical in seen:
            removed.append(s)
            continue
        seen.add(canonical)
    out.append(line)
new_text = "\n".join(out)

if new_text != text:
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_text)
    diag.append("dedupe:removed=" + str(len(removed)))
else:
    diag.append("dedupe:no-change")

# ---- 自检 1: 规范形式无重复 ----
canon_count = {}
for line in new_text.split("\n"):
    s = line.strip()
    if s.startswith("import "):
        c = s.split(" // ")[0].strip() if " // " in s else s
        canon_count[c] = canon_count.get(c, 0) + 1
dups = [k for k, v in canon_count.items() if v > 1]
diag.append("dups:" + str(len(dups)))
if dups:
    diag.append("DUP:" + ",".join(d[:40] for d in dups[:3]))
    ok = False

# ---- 自检 2: 必需符号的 import 必须存在（各恰好一份 canonical）----
for needle in (
    "import androidx.compose.ui.res.stringResource",
    "import me.rerere.rikkahub.R",
):
    if canon_count.get(needle, 0) != 1:
        diag.append("NOT-ONE:" + needle + "=" + str(canon_count.get(needle, 0)))
        ok = False

# ---- 自检 3: 用法仍在 ----
for needle in (
    "stringResource(R.string.workspace_file_read_only)",
    "readOnly = area != WorkspaceStorageArea.FILES",
):
    if needle not in new_text:
        diag.append("MISS:" + needle[:44])
        ok = False

# ---- 自检 4: 剥离字符串/注释后括号配平 ----
def strip_literals(src: str) -> str:
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


clean = strip_literals(new_text)
for label, left, right in (("braces", "{", "}"), ("parens", "(", ")")):
    d = clean.count(left) - clean.count(right)
    diag.append(label + "-diff:" + str(d))
    if d != 0:
        ok = False

diag.append("RESULT:" + ("OK" if ok else "FAIL"))
with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
    f.write("\n".join(diag) + "\n")
print(" | ".join(diag))
if not ok:
    print("::error title=batch355o::" + " | ".join(diag))

#!/usr/bin/env python3
# rhRemote355d: 修 353 埋在 WorkspaceBasicPage 里的 navController 作用域错误
# run610: WorkspaceDetailPage.kt:457 Unresolved reference 'navController'
# 根因: 353 的 SSH 连接卡(含"编辑连接"按钮)被插进 WorkspaceBasicPage —— 该函数是独立
# 私有 Composable, 参数只有 workspace/onToolApprovalChange, 作用域里没有 navController。
# run604 时该错误被 356a 的 Repository Unresolved 掩盖(编译器一次只报一层), 356d 修好后暴露。
# 修法: 在 WorkspaceBasicPage 内部取 LocalNavController.current(文件已 import)。
import os

DIAG = "ci_diag_batch355d_remote.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())

path = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceDetailPage.kt"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

diag = []
ok = True

NEEDLE = """private fun WorkspaceBasicPage(
    workspace: WorkspaceEntity?,
    onToolApprovalChange: (String, Boolean) -> Unit,
) {
    LazyColumn("""
REPL = """private fun WorkspaceBasicPage(
    workspace: WorkspaceEntity?,
    onToolApprovalChange: (String, Boolean) -> Unit,
) {
    val navController = LocalNavController.current
    LazyColumn("""

if "private fun WorkspaceBasicPage(\n    workspace: WorkspaceEntity?,\n    onToolApprovalChange: (String, Boolean) -> Unit,\n) {\n    val navController = LocalNavController.current" in text:
    diag.append("basic-nav:already")
elif text.count(NEEDLE) == 1:
    text = text.replace(NEEDLE, REPL, 1)
    diag.append("basic-nav:ok")
else:
    diag.append("basic-nav:ANCHOR-MISMATCH(" + str(text.count(NEEDLE)) + ")")
    ok = False

with open(path, "w", encoding="utf-8") as f:
    f.write(text)

# 自检
if "import me.rerere.rikkahub.ui.context.LocalNavController" not in text:
    diag.append("import:MISS-LocalNavController")
    ok = False
# navController 定义必须出现在 WorkspaceBasicPage 内（粗略位置校验: 定义在函数头之后、WorkspaceFilesPage 之前）
basic_idx = text.find("private fun WorkspaceBasicPage(")
files_idx = text.find("private fun WorkspaceFilesPage(")
nav_idx = text.find("val navController = LocalNavController.current", basic_idx)
if basic_idx < 0 or files_idx < 0 or nav_idx < 0 or not (basic_idx < nav_idx < files_idx):
    diag.append("scope:navController-not-in-basic")
    ok = False
# WorkspaceBasicPage 里对 navController 的引用必须都在取用之后
seg = text[basic_idx:files_idx]
if "navController.navigate(" not in seg:
    diag.append("scope:no-navigate-in-basic")
    ok = False

diag.append("lines:" + str(text.count("\n") + 1))
diag.append("RESULT:" + ("OK" if ok else "FAIL"))
with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
    f.write("\n".join(diag) + "\n")
print(" | ".join(diag))
if not ok:
    print("::error title=batch355d::" + " | ".join(diag))

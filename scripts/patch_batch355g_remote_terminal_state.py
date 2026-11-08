#!/usr/bin/env python3
# rhRemote355g: 终端页会话重建时复位 finished 状态
# 现象: 结束会话后离开再进, LaunchedEffect 会重建 session (existing.isRunning=false 分支),
# 但 finished 是 remember(id) 状态, 仍是 true → 新会话在跑, 界面却显示"会话已结束"。
# 修法: 取/建会话前统一 finished = false。
import os

DIAG = "ci_diag_batch355g_remote.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())

path = "app/src/main/java/me/rerere/rikkahub/ui/pages/extensions/workspace/WorkspaceTerminalPage.kt"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

diag = []
ok = True

ANCHOR = """                val existing = terminalSessions[id]
                session = if (existing != null && existing.isRunning) {
"""
REPL = """                val existing = terminalSessions[id]
                // 重建或复用会话时复位结束态, 否则新会话在跑却显示"会话已结束"
                finished = false
                session = if (existing != null && existing.isRunning) {
"""

if "finished = false\n                session = if (existing != null && existing.isRunning)" in text:
    diag.append("reset:already")
elif text.count(ANCHOR) == 1:
    text = text.replace(ANCHOR, REPL, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    diag.append("reset:ok")
else:
    diag.append("reset:ANCHOR-MISMATCH(" + str(text.count(ANCHOR)) + ")")
    ok = False

# 自检: 复位点必须在 session 赋值之前、existing 取值之后
e = text.find("val existing = terminalSessions[id]")
f_ = text.find("finished = false", e)
s = text.find("session = if (existing != null && existing.isRunning)", e)
if not (e >= 0 and f_ > e and s > f_):
    diag.append("ORDER:bad(" + str(e) + "," + str(f_) + "," + str(s) + ")")
    ok = False

diag.append("RESULT:" + ("OK" if ok else "FAIL"))
with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
    f.write("\n".join(diag) + "\n")
print(" | ".join(diag))
if not ok:
    print("::error title=batch355g::" + " | ".join(diag))

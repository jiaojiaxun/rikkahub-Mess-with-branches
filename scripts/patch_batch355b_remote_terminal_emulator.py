#!/usr/bin/env python3
# rhRemote355b: 终端仿真器核心文件 —— CI 直接从上游 GitHub 下载原样文件。
# runner 访问 raw.githubusercontent.com 已被 batch219(下载 proot 二进制)验证可行。
# 下载的文件全部是 Termux 上游原版, 互相依赖闭合, 不需要人工改动。
# LocalPtyTransport / JNI 不搬: SSH 终端不需要本地 pty。
import os
import urllib.request

DIAG = "ci_diag_batch355b_remote.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())

BASE = "https://raw.githubusercontent.com/rikkahub/rikkahub/master/terminal/src/main/java/com/termux/terminal/"
DEST = "terminal/src/main/java/com/termux/terminal/"
FILES = [
    "TerminalRow.java",
    "TextStyle.java",
    "TerminalColors.java",
    "TerminalColorScheme.java",
    "WcWidth.java",
    "TerminalBuffer.java",
    "KeyHandler.java",
    "TerminalEmulator.java",
    "TerminalSession.java",
]

diag = []
ok = True
for name in FILES:
    dest = os.path.join(DEST, name)
    if os.path.exists(dest):
        diag.append(name + ":exists")
        continue
    url = BASE + name
    try:
        urllib.request.urlretrieve(url, dest)
        size = os.path.getsize(dest)
        if size < 500:
            diag.append(name + ":TOO-SMALL(" + str(size) + ")")
            ok = False
        else:
            diag.append(name + ":downloaded(" + str(size) + ")")
    except Exception as e:
        diag.append(name + ":FAILED(" + str(e)[:80] + ")")
        ok = False

# TerminalSession 引用 LocalPtyTransport 的构造器, 我们不搬本地 pty —— 去掉那个构造器。
SESSION = os.path.join(DEST, "TerminalSession.java")
if os.path.exists(SESSION):
    with open(SESSION, "r", encoding="utf-8") as f:
        text = f.read()
    ctor = """    /** Create a session running a local subprocess, see {@link LocalPtyTransport}. */
    public TerminalSession(String shellPath, String cwd, String[] args, String[] env, Integer transcriptRows, TerminalSessionClient client) {
        this(new LocalPtyTransport(shellPath, cwd, args, env), transcriptRows, client);
    }

"""
    if ctor in text:
        text = text.replace(ctor, "", 1)
        with open(SESSION, "w", encoding="utf-8") as f:
            f.write(text)
        diag.append("Session:local-ctor-removed")
    elif "LocalPtyTransport" not in text:
        diag.append("Session:ctor-already-clean")
    else:
        # 还有别的 LocalPtyTransport 引用(如 javadoc) —— javadoc 引用不影响编译, 只清理构造器
        diag.append("Session:ctor-anchor-miss(javadoc-only?)")

# 自检: transport 构造器必须保留, 关键结构必须存在
with open(SESSION, "r", encoding="utf-8") as f:
    final_session = f.read()
for needle in (
    "public TerminalSession(TerminalTransport transport, Integer transcriptRows, TerminalSessionClient client)",
    "mTransport.start(columns, rows)",
    "MSG_PROCESS_EXITED",
    "mPendingInput",
):
    if needle not in final_session:
        diag.append("Session:MISSING:" + needle[:44])
        ok = False
if "new LocalPtyTransport(" in final_session:
    diag.append("Session:LEFTOVER-local-pty")
    ok = False

diag.append("RESULT:" + ("OK" if ok else "FAIL"))
with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
    f.write("\n".join(diag) + "\n")
print(" | ".join(diag))
if not ok:
    print("::error title=batch355b::" + " | ".join(diag))

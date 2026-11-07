#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhWsFix345 -- 工作区 rootfs 农场建不出来的真因：busybox --list 的 argv[0]。

━━ 证据链 ━━
1) 用户实测报错（2026-11-07）：
     workspace_install_rootfs → busybox --list 退出码 127: libbusybox.so: applet not found
     workspace_write_file   → rootfs 未就绪：缺少 /usr/rh-bin busybox 农场或 libbusybox.so
2) 源码 WorkspaceBusybox.listApplets：
     val process = ProcessBuilder(exe.absolutePath, "--list")
   Java 的 ProcessBuilder 把 command[0] 同时当可执行路径和 argv[0]。
   所以子进程 argv = [<...>/libbusybox.so, "--list"]，basename = "libbusybox.so"。
   busybox 在 basename 不是已知 applet 时，会拿 argv[1] 当 applet 名；
   "--list" 不是 applet（它只是主模式下的选项）→ die("applet not found")。
   报错串与源码 "busybox --list 退出码 " + exit + ": " + text 逐字吻合。
3) 因果链：listApplets 抛异常 → ensureFarm 抛异常 → RootfsInstaller.install 抛异常
   → commitRootfs 不执行 → 农场永远建不出来 → WorkspaceBusybox.isReady=false
   → workspace_shell / workspace_write_file / 文件删除全部被拒。

━━ 修法（两处，最小） ━━
A. ProcessBuilder 改成 [exe, "busybox", "--list"]：
   argv[1]="busybox" 是真正的 applet，busybox 会进入主模式处理 argv[2]="--list"。
   这就是 `busybox busybox --list` 形式，等价于 `busybox --list`。
B. ensureFarm 加白名单兜底：即使某些 busybox 变体不支持 --list，也用最小 applet
   集合把农场建起来（否则一个安装器的小 bug 会让整个工作区永久不可用）。

━━ 不做什么（避免过度设计） ━━
- 不改 ProotShellRunner 的 `EXEC_PATH + "sh"`：sh 是 applet，能跑；错的是 --list。
- 不改 RootfsInstaller：它没有吞异常，是正确传播的。
"""
import os
import sys

MARK = "rhWsFix345"
DIAG = "ci_diag_batch345_busybox.txt"
Q = chr(34)
ROOT = os.path.abspath(os.getcwd())
REL = "workspace/src/main/java/me/rerere/workspace/WorkspaceBusybox.kt"
rows = []


def note(msg):
    line = "[batch345] " + str(msg)
    print(line)
    rows.append(line)


def fail(msg):
    note("FAIL " + str(msg))
    flush()
    sys.exit(1)


def flush():
    try:
        with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
            f.write("\n".join(rows) + "\n")
    except Exception:
        pass


def parens(t):
    return (t.count("(") - t.count(")"), t.count("{") - t.count("}"), t.count("[") - t.count("]"))


FALLBACK = '''    /** rhWsFix345: busybox 变体不支持 `busybox --list` 时的最小农场白名单（只放核心命令）。 */
    private val FALLBACK_APPLETS = listOf(
        "sh", "ash", "ls", "cat", "echo", "printf", "mkdir", "rmdir", "rm", "mv", "cp", "ln",
        "chmod", "grep", "sed", "awk", "find", "xargs", "env", "sleep", "date", "tar", "gzip",
        "wget", "head", "tail", "sort", "uniq", "wc", "cut", "tr", "tee", "touch", "stat",
        "readlink", "dirname", "basename", "true", "false", "test", "expr", "id", "uname",
        "df", "du", "mktemp", "seq", "md5sum", "sha256sum", "base64", "diff", "ps", "kill",
    )
'''


def main():
    path = os.path.join(ROOT, REL)
    if not os.path.exists(path):
        fail("MISSING " + REL)
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if MARK in text:
        note("already applied")
        flush()
        return

    before = parens(text)

    # A. ProcessBuilder 加 argv[1]="busybox"
    needle = "        val process = ProcessBuilder(exe.absolutePath, " + Q + "--list" + Q + ")"
    if text.count(needle) != 1:
        fail("listApplets anchor count=" + str(text.count(needle)))
    repl = (
        "        // " + MARK + ": argv[0] 的 basename 是 libbusybox.so，busybox 会把 argv[1]\n"
        "        // 当 applet 名；\"--list\" 不是 applet，必须先用 \"busybox\" 进主模式。\n"
        "        val process = ProcessBuilder(exe.absolutePath, " + Q + "busybox" + Q + ", " + Q + "--list" + Q + ")"
    )
    text = text.replace(needle, repl, 1)

    # B. 白名单常量插在 APPLET_NAME 之后
    anchor = "    private val APPLET_NAME = Regex(" + Q + "[A-Za-z0-9_-]+" + Q + ")"
    if text.count(anchor) != 1:
        fail("APPLET_NAME anchor count=" + str(text.count(anchor)))
    text = text.replace(anchor, anchor + "\n\n" + FALLBACK, 1)

    # C. ensureFarm 用兜底
    needle2 = "        val applets = listApplets(nativeLibraryDir)"
    if text.count(needle2) != 1:
        fail("ensureFarm anchor count=" + str(text.count(needle2)))
    repl2 = (
        "        // " + MARK + ": 列表拿不到也不能让整个安装卡死——用最小白名单把农场建起来\n"
        "        val applets = runCatching { listApplets(nativeLibraryDir) }.getOrElse { FALLBACK_APPLETS }"
    )
    text = text.replace(needle2, repl2, 1)

    after = parens(text)
    if after != before:
        fail("BALANCE " + str(before) + " -> " + str(after))
    for need in (MARK, Q + "busybox" + Q + ", " + Q + "--list" + Q, "FALLBACK_APPLETS"):
        if need not in text:
            fail("SELFCHECK missing " + need)
    if needle in text:
        fail("SELFCHECK old ProcessBuilder still present")

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    note("listApplets: argv[1]=busybox added")
    note("ensureFarm: fallback whitelist added")
    note("parens before=" + str(before) + " after=" + str(after))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass
    except Exception as exc:  # noqa: BLE001
        note("EXCEPTION " + type(exc).__name__ + " " + str(exc)[:240])
    flush()
    print("::error::batch345 END lines=" + str(len(rows)))
    sys.exit(0)
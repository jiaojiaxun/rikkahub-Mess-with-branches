#!/usr/bin/env python3
# batch282: 修 Toast 时序 —— 确认删除后紧接 exitProcess(0)，post 出去的任务可能来不及跑。
# 主线程直接 show，系统会自己把 Toast 排进通知队列（进程退出后仍显示）。
# MARK=rhBackupDel282
import sys
from pathlib import Path

MARK = "rhBackupDel282"
NL = chr(10)
DIAG = "ci_diag_batch282.txt"
STORE = "app/src/main/java/me/rerere/rikkahub/data/sync/PendingBackupDeleteStore.kt"
applied = []
failed = []


def diag(msg):
    try:
        with open(DIAG, "a", encoding="utf-8") as f:
            f.write(msg + NL)
    except Exception:
        pass


def fail(msg):
    diag("FAIL " + msg)
    print("::error title=batch282::" + msg)
    raise SystemExit(0)


OLD = '''    private fun toast(context: Context, text: String) {
        Handler(Looper.getMainLooper()).post {
            runCatching { Toast.makeText(context, text, Toast.LENGTH_LONG).show() }
        }
    }'''

NEW = '''    private fun toast(context: Context, text: String) {
        // rhBackupDel282: 确认删除后紧接 exitProcess(0)，post 出去的任务可能来不及执行，
        // 主线程直接 show 才能让系统把 Toast 排进通知队列（进程退出后仍会显示）。
        val action = Runnable {
            runCatching { Toast.makeText(context, text, Toast.LENGTH_LONG).show() }
        }
        if (Looper.myLooper() == Looper.getMainLooper()) {
            action.run()
        } else {
            Handler(Looper.getMainLooper()).post(action)
        }
    }'''


def main():
    p = Path(STORE)
    if not p.exists():
        fail("missing file: " + STORE)
    content = p.read_text(encoding="utf-8")
    if MARK in content:
        diag("already patched")
        print("::notice title=batch282-skip::already patched")
        return
    if "rhBackupDel280" not in content:
        diag("batch280 not applied, nothing to patch")
        print("::notice title=batch282-skip::batch280 not applied")
        return
    if OLD not in content:
        fail("toast block not found")
    if content.count(OLD) != 1:
        fail("toast block count=" + str(content.count(OLD)))
    content = content.replace(OLD, NEW, 1)
    p.write_text(content, encoding="utf-8")
    check = p.read_text(encoding="utf-8")
    for needle in (MARK, "Looper.myLooper() == Looper.getMainLooper()"):
        if needle not in check:
            fail("verify failed: " + needle)
    applied.append("toast-sync")
    diag("applied=" + ",".join(applied))
    print("::notice title=batch282-ok::toast-sync")


main()

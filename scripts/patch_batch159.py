#!/usr/bin/env python3
# batch159: 备份合并改造 10/10 —— WebDavTab / S3Tab 的 MERGE 按钮改接两阶段状态机
# 变更:
#   1) WebDavTab.kt: MERGE 按钮 vm.restore(item, MERGE) → vm.beginWebDavMerge(item)
#   2) S3Tab.kt:     MERGE 按钮 vm.restoreFromS3(item, MERGE) → vm.beginS3Merge(item)
# OVERWRITE 按钮完全不动。
# 锚点: 两文件恢复对话框段落已读原文(2026-10-11); 含 MERGE 的调用行各唯一。
# 幂等: 命中 [batch159] 标记即跳过; 锚点失配 fail-loud + dump 现场。

import io
import sys

NL = chr(10)
MARK = "[batch159]"
Q = chr(34)

WDTAB = "app/src/main/java/me/rerere/rikkahub/ui/pages/backup/tabs/WebDavTab.kt"
S3TAB = "app/src/main/java/me/rerere/rikkahub/ui/pages/backup/tabs/S3Tab.kt"

WD_OLD = (
    "                        if (item != null) scope.launch {" + NL +
    "                            restoringItemId = item.displayName" + NL +
    "                            runCatching {" + NL +
    "                                vm.restore(item, BackupRestoreMode.MERGE)" + NL +
    "                                toaster.show(context.getString(R.string.backup_page_restore_success), type = ToastType.Success)" + NL +
    "                                showBackupFiles = false" + NL +
    "                                onShowRestartDialog()" + NL +
    "                            }.onFailure { err ->" + NL +
    "                                toaster.show(context.getString(R.string.backup_page_restore_failed, err.message ?: " + Q + Q + "), type = ToastType.Error)" + NL +
    "                            }" + NL +
    "                            restoringItemId = null" + NL +
    "                        }" + NL +
    "                    }) { Text(BackupRestoreMode.MERGE.displayName()) }"
)

WD_NEW = (
    "                        // [batch159] 合并走两阶段状态机：下载 → 扫描 → 差异确认 → 应用" + NL +
    "                        if (item != null) vm.beginWebDavMerge(item)" + NL +
    "                    }) { Text(BackupRestoreMode.MERGE.displayName()) }"
)

S3_OLD = (
    "                        if (item != null) scope.launch {" + NL +
    "                            restoringItemId = item.displayName" + NL +
    "                            runCatching {" + NL +
    "                                vm.restoreFromS3(item, BackupRestoreMode.MERGE)" + NL +
    "                                toaster.show(context.getString(R.string.backup_page_restore_success), type = ToastType.Success)" + NL +
    "                                showBackupFiles = false" + NL +
    "                                onShowRestartDialog()" + NL +
    "                            }.onFailure { err ->" + NL +
    "                                toaster.show(context.getString(R.string.backup_page_restore_failed, err.message ?: " + Q + Q + "), type = ToastType.Error)" + NL +
    "                            }" + NL +
    "                            restoringItemId = null" + NL +
    "                        }" + NL +
    "                    }) { Text(BackupRestoreMode.MERGE.displayName()) }"
)

S3_NEW = (
    "                        // [batch159] 合并走两阶段状态机：下载 → 扫描 → 差异确认 → 应用" + NL +
    "                        if (item != null) vm.beginS3Merge(item)" + NL +
    "                    }) { Text(BackupRestoreMode.MERGE.displayName()) }"
)


def fail(msg):
    print("::error::" + msg)
    sys.exit(1)


def dump_lines(src, needle, radius):
    lines = src.split(NL)
    hit = -1
    for i in range(len(lines)):
        if needle in lines[i]:
            hit = i
            break
    if hit < 0:
        return "(no line contains " + needle + ")"
    lo = max(0, hit - radius)
    hi = min(len(lines), hit + radius + 1)
    out = ""
    for k in range(lo, hi):
        if out:
            out = out + " | "
        out = out + str(k + 1) + ": " + lines[k]
    return out


def patch_tab(path, old_block, new_block, check):
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            src = f.read()
    except Exception as exc:
        fail("batch159: read failed :: " + path + " :: " + str(exc))
    if MARK in src:
        print("batch159: already applied, skip " + path)
        return
    if src.count(old_block) != 1:
        fail("batch159: anchor count=" + str(src.count(old_block)) + " in " + path + " :: " + dump_lines(src, "BackupRestoreMode.MERGE", 14))
    out = src.replace(old_block, new_block, 1)
    if check not in out:
        fail("batch159: post-check missing in " + path + " :: " + check)
    try:
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(out)
    except Exception as exc:
        fail("batch159: write failed :: " + path + " :: " + str(exc))
    print("batch159: patched " + path)


def main():
    patch_tab(WDTAB, WD_OLD, WD_NEW, "vm.beginWebDavMerge(item)")
    patch_tab(S3TAB, S3_OLD, S3_NEW, "vm.beginS3Merge(item)")
    print("batch159: WebDavTab + S3Tab MERGE buttons wired")


if __name__ == "__main__":
    main()

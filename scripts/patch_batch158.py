#!/usr/bin/env python3
# batch158: 备份合并改造 9/10 —— BackupPage 挂载差异确认 UI + ImportExportTab MERGE 按钮接线
# 变更:
#   1) BackupPage.kt: +4 import; 挂 MergeConfirmDialog(观察 vm.mergeUiState) +
#      Done/Failed 副作用处理(toast + 复位 + 重启对话框)
#   2) ImportExportTab.kt: 恢复模式对话框的 MERGE 按钮改调 vm.beginLocalMerge(file)
# 锚点: 两文件均已读原文(2026-10-11); batch6 只碰 ImportExportTab 的导出区(LITE 项),
#       恢复对话框区未动。
# 幂等: 命中 [batch158] 标记即跳过; 锚点失配 fail-loud + dump 现场。

import io
import sys

NL = chr(10)
MARK = "[batch158]"

PAGE = "app/src/main/java/me/rerere/rikkahub/ui/pages/backup/BackupPage.kt"
TAB = "app/src/main/java/me/rerere/rikkahub/ui/pages/backup/tabs/ImportExportTab.kt"

PAGE_IMPORT_ANCHOR = "import me.rerere.rikkahub.ui.pages.backup.components.BackupDialog"
PAGE_IMPORTS = (
    "import androidx.compose.runtime.LaunchedEffect" + NL +
    "import androidx.lifecycle.compose.collectAsStateWithLifecycle" + NL +
    "import com.dokar.sonner.ToastType" + NL +
    "import me.rerere.rikkahub.ui.context.LocalToaster" + NL +
    PAGE_IMPORT_ANCHOR
)

PAGE_TOASTER_ANCHOR = "    var showRestartDialog by remember { mutableStateOf(false) }"
PAGE_TOASTER_NEW = (
    PAGE_TOASTER_ANCHOR + NL +
    "    val toaster = LocalToaster.current"
)

PAGE_MERGE_ANCHOR = (
    "    if (showRestartDialog) {" + NL +
    "        BackupDialog()" + NL +
    "    }"
)

PAGE_MERGE_BLOCK = r'''    // [batch158] 两阶段合并：差异确认对话框 + 结果处理
    val mergeState by vm.mergeUiState.collectAsStateWithLifecycle()
    LaunchedEffect(mergeState) {
        when (val state = mergeState) {
            is BackupVM.MergeUiState.Done -> {
                toaster.show("合并完成：" + state.summary, type = ToastType.Success)
                vm.cancelMerge()
                showRestartDialog = true
            }
            is BackupVM.MergeUiState.Failed -> {
                toaster.show("合并失败：" + state.message, type = ToastType.Error)
                vm.cancelMerge()
            }
            else -> Unit
        }
    }
    (mergeState as? BackupVM.MergeUiState.AwaitingDecision)?.let { state ->
        MergeConfirmDialog(
            plan = state.plan,
            onConversationDecision = vm::updateConversationDecision,
            onSettingsItemDecision = vm::updateSettingsItemDecision,
            onToggleScalar = vm::toggleScalarAdoption,
            onConfirm = { vm.confirmMerge() },
            onCancel = { vm.cancelMerge() },
        )
    }

'''

TAB_MERGE_OLD = (
    "                    TextButton(onClick = {" + NL +
    "                        val file = pendingRestoreFile" + NL +
    "                        pendingRestoreFile = null" + NL +
    "                        showRestoreMode = false" + NL +
    "                        if (file != null) restoreLocal(file, BackupRestoreMode.MERGE)" + NL +
    "                    }) { Text(BackupRestoreMode.MERGE.displayName()) }"
)

TAB_MERGE_NEW = (
    "                    TextButton(onClick = {" + NL +
    "                        val file = pendingRestoreFile" + NL +
    "                        pendingRestoreFile = null" + NL +
    "                        showRestoreMode = false" + NL +
    "                        isRestoring = false" + NL +
    "                        // [batch158] 合并走两阶段状态机：扫描 → 差异确认 → 应用" + NL +
    "                        if (file != null) vm.beginLocalMerge(file)" + NL +
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


def balance(text):
    return (text.count("{") - text.count("}"), text.count("(") - text.count(")"))


def main():
    # ---- BackupPage ----
    try:
        with io.open(PAGE, "r", encoding="utf-8") as f:
            src = f.read()
    except Exception as exc:
        fail("batch158: read failed :: " + PAGE + " :: " + str(exc))
    if MARK not in src:
        if src.count(PAGE_IMPORT_ANCHOR) != 1:
            fail("batch158: page import anchor count=" + str(src.count(PAGE_IMPORT_ANCHOR)))
        if src.count(PAGE_TOASTER_ANCHOR) != 1:
            fail("batch158: page toaster anchor count=" + str(src.count(PAGE_TOASTER_ANCHOR)))
        if src.count(PAGE_MERGE_ANCHOR) != 1:
            fail("batch158: page merge anchor count=" + str(src.count(PAGE_MERGE_ANCHOR)) + " :: " + dump_lines(src, "showRestartDialog", 5))
        bal_before = balance(src)
        out = src.replace(PAGE_IMPORT_ANCHOR, PAGE_IMPORTS, 1)
        out = out.replace(PAGE_TOASTER_ANCHOR, PAGE_TOASTER_NEW, 1)
        out = out.replace(PAGE_MERGE_ANCHOR, PAGE_MERGE_BLOCK + PAGE_MERGE_ANCHOR, 1)
        expected = (
            bal_before[0] + balance(PAGE_MERGE_BLOCK)[0],
            bal_before[1] + balance(PAGE_MERGE_BLOCK)[1],
        )
        if balance(out) != expected:
            fail("batch158: page balance failed :: before=" + str(bal_before) + " after=" + str(balance(out)))
        for needle in ("MergeConfirmDialog(", "mergeUiState.collectAsStateWithLifecycle", "LocalToaster.current"):
            if needle not in out:
                fail("batch158: page post-check missing :: " + needle)
        try:
            with io.open(PAGE, "w", encoding="utf-8") as f:
                f.write(out)
        except Exception as exc:
            fail("batch158: page write failed :: " + str(exc))
        print("batch158: patched " + PAGE)
    else:
        print("batch158: already applied, skip " + PAGE)

    # ---- ImportExportTab ----
    try:
        with io.open(TAB, "r", encoding="utf-8") as f:
            src = f.read()
    except Exception as exc:
        fail("batch158: read failed :: " + TAB + " :: " + str(exc))
    if MARK not in src:
        if src.count(TAB_MERGE_OLD) != 1:
            fail("batch158: tab merge anchor count=" + str(src.count(TAB_MERGE_OLD)) + " :: " + dump_lines(src, "BackupRestoreMode.MERGE", 8))
        out = src.replace(TAB_MERGE_OLD, TAB_MERGE_NEW, 1)
        if "vm.beginLocalMerge(file)" not in out:
            fail("batch158: tab post-check missing beginLocalMerge")
        try:
            with io.open(TAB, "w", encoding="utf-8") as f:
                f.write(out)
        except Exception as exc:
            fail("batch158: tab write failed :: " + str(exc))
        print("batch158: patched " + TAB)
    else:
        print("batch158: already applied, skip " + TAB)

    print("batch158: BackupPage + ImportExportTab wired")


if __name__ == "__main__":
    main()

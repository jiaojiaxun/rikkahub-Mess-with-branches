#!/usr/bin/env python3
# batch280: 修复「恢复后删除备份包」从不生效。
#
# 三个叠加缺陷（上一版 batch239）:
#   1. takePersistableUriPermission(READ or WRITE) 在只拿到 READ 时整次抛 SecurityException，
#      READ 也没持久化 -> 重启后 URI 不可用；
#   2. 选择器用 ActivityResultContracts.OpenDocument()，请求不带 WRITE -> 永远没有写权限；
#   3. 标记在尝试删除前就 clear()，失败且静默 -> 一次失败永久放弃。
#
# 本批：重写 store（READ/WRITE 分开取、当场删、失败排队重试 3 次、成功/失败都提示）+ 重写弹窗
# + 换选择器契约 + 取消恢复时清候选。
# MARK=rhBackupDel280
import sys
from pathlib import Path

MARK = "rhBackupDel280"
NL = chr(10)
DIAG = "ci_diag_batch280.txt"
STORE = "app/src/main/java/me/rerere/rikkahub/data/sync/PendingBackupDeleteStore.kt"
DIALOG = "app/src/main/java/me/rerere/rikkahub/ui/pages/backup/components/BackupDialog.kt"
TAB = "app/src/main/java/me/rerere/rikkahub/ui/pages/backup/tabs/ImportExportTab.kt"
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
    print("::error title=batch280::" + msg)
    raise SystemExit(0)


def read(path):
    p = Path(path)
    if not p.exists():
        fail("missing file: " + path)
    return p.read_text(encoding="utf-8")


def write(path, content):
    Path(path).write_text(content, encoding="utf-8")


def replace_text(content, old, new, label):
    if old not in content:
        fail(label + " text not found")
    n = content.count(old)
    if n != 1:
        fail(label + " text not unique: " + str(n))
    applied.append(label)
    return content.replace(old, new, 1)


STORE_CODE = '''package me.rerere.rikkahub.data.sync

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.provider.DocumentsContract
import android.provider.OpenableColumns
import android.util.Log
import android.widget.Toast
import java.io.File

/**
 * rhBackupDel280: 恢复完成后删除备份包。
 *
 * 上一版(batch239)三个缺陷导致「勾选了但文件永远删不掉」:
 *  1. takePersistableUriPermission(READ or WRITE) 在只拿到 READ 授权时整次抛 SecurityException,
 *     结果 READ 也没持久化 -> 重启后 URI 完全不可用;
 *  2. 选择器请求不带 WRITE 标志 -> 系统根本不给写权限 -> deleteDocument 必失败;
 *  3. 失败前就把标记 clear() 且静默 -> 一次失败就永久放弃。
 *
 * 本版: READ/WRITE 分开取; 确认时先趁进程内授权还有效就删; 删不掉才排到下次启动重试(至多 3 次),
 * 成功与最终失败都会 Toast 告知。
 */
object PendingBackupDeleteStore {
    private const val TAG = "PendingBackupDel"
    private const val PREF_NAME = "rh_pending_backup_delete"
    private const val KEY_URI = "candidate_uri"
    private const val KEY_PATH = "candidate_path"
    private const val KEY_NAME = "candidate_name"
    private const val KEY_CONFIRMED = "confirmed"
    private const val KEY_ATTEMPTS = "attempts"
    private const val MAX_ATTEMPTS = 3

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)

    fun recordLocalBackupCandidate(context: Context, uri: Uri) {
        // (1) READ 一定能持久化: ACTION_OPEN_DOCUMENT 的返回值带 persistable 标志
        runCatching {
            context.contentResolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION,
            )
        }.onFailure { Log.w(TAG, "takePersistableUriPermission(READ) failed", it) }
        // (2) WRITE 单独再试: 请求里没带 WRITE 标志时这里会抛异常, 但不能影响上面的 READ
        val canWrite = runCatching {
            context.contentResolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
            )
        }.isSuccess
        val displayName = queryDisplayName(context, uri)
            ?: uri.lastPathSegment?.substringAfterLast('/')
            ?: ""
        val resolvedPath = resolveLocalFilePath(context, uri) ?: ""
        prefs(context).edit()
            .putString(KEY_URI, uri.toString())
            .putString(KEY_PATH, resolvedPath)
            .putString(KEY_NAME, displayName)
            .putBoolean(KEY_CONFIRMED, false)
            .putInt(KEY_ATTEMPTS, 0)
            .commit()
        Log.i(TAG, "record: name=" + displayName + " canWrite=" + canWrite + " path=" + resolvedPath)
    }

    fun hasCandidate(context: Context): Boolean {
        val p = prefs(context)
        return p.getString(KEY_URI, "").orEmpty().isNotBlank() ||
            p.getString(KEY_PATH, "").orEmpty().isNotBlank()
    }

    fun getCandidateName(context: Context): String? {
        val p = prefs(context)
        val uri = p.getString(KEY_URI, "").orEmpty()
        val path = p.getString(KEY_PATH, "").orEmpty()
        if (uri.isBlank() && path.isBlank()) return null
        val name = p.getString(KEY_NAME, "").orEmpty()
        return name.ifBlank {
            path.substringAfterLast('/').ifBlank { uri.substringAfterLast('/') }
        }.ifBlank { null }
    }

    /** 恢复完成弹窗勾选后立刻调用: 进程内授权仍然有效, 成功率最高。 */
    fun deleteCandidateNow(context: Context): Boolean {
        val p = prefs(context)
        val uriStr = p.getString(KEY_URI, "").orEmpty()
        val pathStr = p.getString(KEY_PATH, "").orEmpty()
        val nameStr = p.getString(KEY_NAME, "").orEmpty()
        if (uriStr.isBlank() && pathStr.isBlank()) {
            p.edit().clear().commit()
            return false
        }
        val deleted = deleteInternal(context, uriStr, pathStr)
        Log.i(TAG, "deleteCandidateNow: deleted=" + deleted + " name=" + nameStr)
        if (deleted) {
            p.edit().clear().commit()
            toast(context, if (nameStr.isNotBlank()) "已删除备份包：「 + nameStr else "已删除上次恢复的备份包")
        }
        return deleted
    }

    /** 立刻删失败时排队: 下次启动继续尝试。 */
    fun queueForNextLaunch(context: Context) {
        prefs(context).edit().putBoolean(KEY_CONFIRMED, true).commit()
    }

    /** 用户没勾选就重启、或者直接取消恢复: 丢弃候选, 别让旧文件被误删。 */
    fun clearCandidate(context: Context) {
        prefs(context).edit().clear().commit()
    }

    fun executePendingDeleteOnStartup(context: Context) {
        val p = prefs(context)
        if (!p.getBoolean(KEY_CONFIRMED, false)) return
        val uriStr = p.getString(KEY_URI, "").orEmpty()
        val pathStr = p.getString(KEY_PATH, "").orEmpty()
        val nameStr = p.getString(KEY_NAME, "").orEmpty()
        if (uriStr.isBlank() && pathStr.isBlank()) {
            p.edit().clear().commit()
            return
        }
        val deleted = deleteInternal(context, uriStr, pathStr)
        val attempts = p.getInt(KEY_ATTEMPTS, 0) + 1
        Log.i(TAG, "startup delete: deleted=" + deleted + " attempt=" + attempts + " name=" + nameStr)
        if (deleted) {
            p.edit().clear().commit()
            toast(context, if (nameStr.isNotBlank()) "已自动删除备份包：「 + nameStr else "已自动删除上次恢复的备份包")
        } else if (attempts >= MAX_ATTEMPTS) {
            p.edit().clear().commit()
            val label = if (nameStr.isNotBlank()) nameStr else pathStr.substringAfterLast('/')
            toast(context, "备份包删除失败，请手动删除：" + label)
        } else {
            p.edit().putInt(KEY_ATTEMPTS, attempts).commit()
        }
    }

    private fun deleteInternal(context: Context, uriStr: String, pathStr: String): Boolean {
        var deleted = false
        if (uriStr.isNotBlank()) {
            val uri = runCatching { Uri.parse(uriStr) }.getOrNull()
            if (uri != null) {
                deleted = runCatching {
                    DocumentsContract.deleteDocument(context.contentResolver, uri)
                }.getOrDefault(false)
                if (!deleted) {
                    deleted = runCatching {
                        context.contentResolver.delete(uri, null, null) > 0
                    }.getOrDefault(false)
                }
            }
        }
        if (!deleted && pathStr.isNotBlank()) {
            val f = File(pathStr)
            if (f.exists()) {
                deleted = runCatching { f.delete() }.getOrDefault(false)
            }
        }
        return deleted
    }

    private fun toast(context: Context, text: String) {
        Handler(Looper.getMainLooper()).post {
            runCatching { Toast.makeText(context, text, Toast.LENGTH_LONG).show() }
        }
    }

    private fun queryDisplayName(context: Context, uri: Uri): String? = runCatching {
        context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
            if (c.moveToFirst()) {
                val idx = c.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                if (idx >= 0) c.getString(idx) else null
            } else null
        }
    }.getOrNull()

    private fun resolveLocalFilePath(context: Context, uri: Uri): String? = runCatching {
        if (uri.scheme.equals("file", ignoreCase = true)) {
            return@runCatching uri.path
        }
        if (DocumentsContract.isDocumentUri(context, uri)) {
            val docId = DocumentsContract.getDocumentId(uri)
            if (docId.startsWith("raw:")) {
                return@runCatching docId.removePrefix("raw:")
            }
            if (docId.startsWith("primary:")) {
                val rel = docId.removePrefix("primary:").trimStart('/')
                val root = Environment.getExternalStorageDirectory().absolutePath.trimEnd('/')
                return@runCatching root + "/" + rel
            }
            if (docId.startsWith("home:")) {
                val rel = docId.removePrefix("home:").trimStart('/')
                val root = Environment.getExternalStorageDirectory().absolutePath.trimEnd('/') + "/Documents"
                return@runCatching root + "/" + rel
            }
        }
        null
    }.getOrNull()
}
'''

DIALOG_CODE = '''package me.rerere.rikkahub.ui.pages.backup.components

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import me.rerere.rikkahub.R
import me.rerere.rikkahub.data.sync.PendingBackupDeleteStore
import kotlin.system.exitProcess

// rhBackupDel280: 恢复完成弹窗。勾选删除时先趁进程内授权有效立刻删, 删不掉才排队到下次启动。
@Composable
fun BackupDialog() {
    val context = LocalContext.current
    val candidateName = remember { PendingBackupDeleteStore.getCandidateName(context) }
    val hasCandidate = remember { PendingBackupDeleteStore.hasCandidate(context) }
    var deleteAfterRestore by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = {},
        title = { Text(stringResource(R.string.backup_page_restart_app)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(stringResource(R.string.backup_page_restart_desc))
                if (hasCandidate) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { deleteAfterRestore = !deleteAfterRestore }
                            .padding(vertical = 4.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Checkbox(
                            checked = deleteAfterRestore,
                            onCheckedChange = { deleteAfterRestore = it },
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text(
                                text = "删除本次恢复所用的备份包",
                                style = MaterialTheme.typography.bodyMedium,
                            )
                            Text(
                                text = candidateName ?: "上次恢复使用的备份文件",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                    }
                }
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    if (hasCandidate) {
                        if (deleteAfterRestore) {
                            if (!PendingBackupDeleteStore.deleteCandidateNow(context)) {
                                PendingBackupDeleteStore.queueForNextLaunch(context)
                            }
                        } else {
                            PendingBackupDeleteStore.clearCandidate(context)
                        }
                    }
                    exitProcess(0)
                }
            ) {
                Text(stringResource(R.string.backup_page_restart_app))
            }
        },
    )
}
'''


def rewrite_store():
    p = Path(STORE)
    if not p.exists():
        fail("missing file: " + STORE)
    content = p.read_text(encoding="utf-8")
    if MARK in content:
        diag("store already patched")
        return
    if "takePersistableUriPermission" not in content:
        fail("store anchor missing (unexpected content)")
    p.write_text(STORE_CODE, encoding="utf-8")
    check = p.read_text(encoding="utf-8")
    for needle in (MARK, "fun deleteCandidateNow(", "fun queueForNextLaunch(", "MAX_ATTEMPTS"):
        if needle not in check:
            fail("store verify failed: " + needle)
    applied.append("store")


def rewrite_dialog():
    p = Path(DIALOG)
    if not p.exists():
        fail("missing file: " + DIALOG)
    content = p.read_text(encoding="utf-8")
    if MARK in content:
        diag("dialog already patched")
        return
    if "confirmDeleteOnNextLaunch" not in content:
        fail("dialog anchor missing (unexpected content)")
    p.write_text(DIALOG_CODE, encoding="utf-8")
    check = p.read_text(encoding="utf-8")
    for needle in (MARK, "deleteCandidateNow(context)", "hasCandidate"):
        if needle not in check:
            fail("dialog verify failed: " + needle)
    applied.append("dialog")


def patch_tab():
    p = Path(TAB)
    if not p.exists():
        fail("missing file: " + TAB)
    content = p.read_text(encoding="utf-8")
    if MARK in content:
        diag("tab already patched")
        return
    old_contract = "        contract = ActivityResultContracts.OpenDocument(),"
    new_contract = (
        "        contract = me.rerere.rikkahub.data.sync.OpenDocumentWithWriteContract(), // " + MARK
    )
    content = replace_text(content, old_contract, new_contract, "tab-contract")

    old_dismiss = "            onDismissRequest = {" + NL + "                pendingRestoreFile?.delete()"
    new_dismiss = (
        "            onDismissRequest = {" + NL
        + "                me.rerere.rikkahub.data.sync.PendingBackupDeleteStore.clearCandidate(context) // " + MARK + NL
        + "                pendingRestoreFile?.delete()"
    )
    content = replace_text(content, old_dismiss, new_dismiss, "tab-dismiss")

    old_cancel = "                TextButton(onClick = {" + NL + "                    pendingRestoreFile?.delete()"
    new_cancel = (
        "                TextButton(onClick = {" + NL
        + "                    me.rerere.rikkahub.data.sync.PendingBackupDeleteStore.clearCandidate(context) // " + MARK + NL
        + "                    pendingRestoreFile?.delete()"
    )
    content = replace_text(content, old_cancel, new_cancel, "tab-cancel")
    p.write_text(content, encoding="utf-8")
    check = p.read_text(encoding="utf-8")
    if check.count("clearCandidate(context)") != 2:
        fail("tab verify failed: clearCandidate count=" + str(check.count("clearCandidate(context)")))
    applied.append("tab")


def main():
    for label, fn in (("store", rewrite_store), ("dialog", rewrite_dialog), ("tab", patch_tab)):
        try:
            fn()
        except SystemExit:
            failed.append(label)
        except Exception as e:
            diag("EXCEPTION " + label + ": " + repr(e))
            failed.append(label)
    diag("applied=" + ",".join(applied) + " failed=" + (",".join(failed) if failed else "none"))
    if failed:
        print("::error title=batch280-FAILED::" + ",".join(failed))
    else:
        print("::notice title=batch280-ok::" + ",".join(applied))


main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch239: 备份恢复完成后主动询问是否删除备份包, 勾选则下次启动后自动删除

用户需求(2026-10-17):
  「备份恢复完成以后, 主动询问用户是否删除备份包, 然后如果我勾选了, 就在下一次启动之后把备份包删除」

设计方案(4 文件):
  1. 新增 PendingBackupDeleteStore.kt (me.rerere.rikkahub.data.sync):
     - recordLocalBackupCandidate(context, uri):
       在本地备份文件被选中时调用:
       (a) 调用 takePersistableUriPermission(READ | WRITE) 持久化 SAF 授权, 确保跨 exitProcess(0) 仍有效;
       (b) 查询 OpenableColumns.DISPLAY_NAME 获取文件名供弹窗展示;
       (c) 解析真实文件路径(支持 file://、DocumentsContract raw: 与 primary: 外部存储路径)作为双保险;
       (d) 写入专用 SharedPreferences("rh_pending_backup_delete")。
     - getCandidateName(context): 读取候选备份包显示名。
     - confirmDeleteOnNextLaunch(context, deleteOnNextLaunch):
       在用户点击「重启应用」前调用, 使用同步 .commit() 落盘(绝不用异步 apply, 防止紧随其后的
       exitProcess(0) 导致未刷盘丢失)。未勾选时清空候选记录。
     - executePendingDeleteOnStartup(context):
       下次启动在 RikkaHubApp.deleteTempFiles() 的 IO 协程中调用:
       若 confirmed=true, 先同步清空记录防重入, 再依次尝试 DocumentsContract.deleteDocument、
       contentResolver.delete 与 File(path).delete(); 删除成功后在主线程弹 Toast 告知用户。
  2. ImportExportTab.kt:
     - openDocumentLauncher 的 "local" 分支选中 sourceUri 时调用
       PendingBackupDeleteStore.recordLocalBackupCandidate(context, sourceUri),
       覆盖「本地覆盖恢复」与「本地合并恢复」两条路径。
  3. BackupDialog.kt:
     - 升级恢复完成后的重启对话框: 展示「下次启动后删除此备份包」复选框行(含备份包文件名副标题);
       点击重启按钮时先调 confirmDeleteOnNextLaunch(context, checked) 再调 exitProcess(0)。
  4. RikkaHubApp.kt:
     - deleteTempFiles() 的 IO 协程内追加 PendingBackupDeleteStore.executePendingDeleteOnStartup(this@RikkaHubApp)。

五查:
1. import 清单:
   - PendingBackupDeleteStore.kt 为独立新文件, 自带完整 import;
   - BackupDialog.kt 整文件重写(仅 28 行且从未被任何 patch 修改), import 完整自包含;
   - ImportExportTab.kt 与 RikkaHubApp.kt 均用全限定名调用, 零新增 import。
2. 同文件冲突:
   - BackupDialog.kt 无在链 patch;
   - ImportExportTab.kt 锚点在 openDocumentLauncher "local" 分支(与 batch158 showRestoreMode 区域不相交);
   - RikkaHubApp.kt 锚点在 deleteTempFiles 函数体(与 batch99 onCreate 区域不相交)。
3. 作用域:
   - ImportExportTab openDocumentLauncher 内 context/sourceUri 在作用域;
   - RikkaHubApp deleteTempFiles 内 this@RikkaHubApp 在作用域。
4. 括号配对: 逐文件校验 balance。
5. 函数签名: BackupDialog() 保持无参签名, BackupPage.kt 调用点零改动。

Python 三查: 引号用 Q 变量或三引号块构造; NL 手写 concat 禁 f-string/join/walrus; helper 先定义后用; fail-loud
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhBackupDel239'

STORE = 'app/src/main/java/me/rerere/rikkahub/data/sync/PendingBackupDeleteStore.kt'
DIALOG = 'app/src/main/java/me/rerere/rikkahub/ui/pages/backup/components/BackupDialog.kt'
TAB = 'app/src/main/java/me/rerere/rikkahub/ui/pages/backup/tabs/ImportExportTab.kt'
APP = 'app/src/main/java/me/rerere/rikkahub/RikkaHubApp.kt'


def fail(msg):
    print('::error::batch239 ' + str(msg)[:1400])
    sys.stdout.flush()
    sys.exit(0)


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def replace_once(text, old, new, label):
    n = text.count(old)
    if n == 0:
        fail(label + ': anchor not found. head=' + repr(old[:120]))
    if n != 1:
        fail(label + ': anchor count=' + str(n) + ' (expected 1). head=' + repr(old[:120]))
    return text.replace(old, new, 1)


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
 * rhBackupDel239: 记录最近一次恢复所使用的备份包位置;
 * 当用户在「备份已恢复」弹窗中勾选「下次启动后删除备份包」时,
 * 用 commit() 同步落盘标记, 并在下次应用启动(RikkaHubApp.onCreate)时自动删除。
 */
object PendingBackupDeleteStore {
    private const val TAG = "PendingBackupDel"
    private const val PREF_NAME = "rh_pending_backup_delete"
    private const val KEY_URI = "candidate_uri"
    private const val KEY_PATH = "candidate_path"
    private const val KEY_NAME = "candidate_name"
    private const val KEY_CONFIRMED = "confirmed"

    fun recordLocalBackupCandidate(context: Context, uri: Uri) {
        runCatching {
            context.contentResolver.takePersistableUriPermission(
                uri,
                Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION,
            )
        }
        val displayName = queryDisplayName(context, uri)
            ?: uri.lastPathSegment?.substringAfterLast('/')
            ?: ""
        val resolvedPath = resolveLocalFilePath(context, uri) ?: ""
        context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_URI, uri.toString())
            .putString(KEY_PATH, resolvedPath)
            .putString(KEY_NAME, displayName)
            .putBoolean(KEY_CONFIRMED, false)
            .commit()
    }

    fun getCandidateName(context: Context): String? {
        val prefs = context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
        val uri = prefs.getString(KEY_URI, "").orEmpty()
        val path = prefs.getString(KEY_PATH, "").orEmpty()
        if (uri.isBlank() && path.isBlank()) return null
        val name = prefs.getString(KEY_NAME, "").orEmpty()
        return name.ifBlank {
            path.substringAfterLast('/').ifBlank { uri.substringAfterLast('/') }
        }.ifBlank { null }
    }

    /**
     * 必须在 exitProcess(0) 之前调用, 因此使用 commit() 同步写盘。
     */
    fun confirmDeleteOnNextLaunch(context: Context, deleteOnNextLaunch: Boolean) {
        val prefs = context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
        if (deleteOnNextLaunch) {
            prefs.edit().putBoolean(KEY_CONFIRMED, true).commit()
        } else {
            prefs.edit().clear().commit()
        }
    }

    fun executePendingDeleteOnStartup(context: Context) {
        val prefs = context.getSharedPreferences(PREF_NAME, Context.MODE_PRIVATE)
        val confirmed = prefs.getBoolean(KEY_CONFIRMED, false)
        if (!confirmed) return
        val uriStr = prefs.getString(KEY_URI, "").orEmpty()
        val pathStr = prefs.getString(KEY_PATH, "").orEmpty()
        val nameStr = prefs.getString(KEY_NAME, "").orEmpty()
        // 先清空标记, 确保只执行一次
        prefs.edit().clear().commit()

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
            if (f.exists() && runCatching { f.delete() }.getOrDefault(false)) {
                deleted = true
            }
        }
        Log.i(TAG, "executePendingDeleteOnStartup: deleted=" + deleted + " name=" + nameStr + " path=" + pathStr)
        if (deleted) {
            Handler(Looper.getMainLooper()).post {
                val tip = if (nameStr.isNotBlank()) {
                    "已自动删除备份包：" + nameStr
                } else {
                    "已自动删除上次恢复的备份包"
                }
                Toast.makeText(context, tip, Toast.LENGTH_SHORT).show()
            }
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

// rhBackupDel239: 备份恢复完成弹窗 —— 主动询问是否在下一次启动后删除备份包
@Composable
fun BackupDialog() {
    val context = LocalContext.current
    val candidateName = remember { PendingBackupDeleteStore.getCandidateName(context) }
    var deleteOnNextLaunch by remember { mutableStateOf(false) }

    AlertDialog(
        onDismissRequest = {},
        title = { Text(stringResource(R.string.backup_page_restart_app)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(stringResource(R.string.backup_page_restart_desc))
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { deleteOnNextLaunch = !deleteOnNextLaunch }
                        .padding(vertical = 4.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Checkbox(
                        checked = deleteOnNextLaunch,
                        onCheckedChange = { deleteOnNextLaunch = it },
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Column(modifier = Modifier.weight(1f)) {
                        Text(
                            text = "下次启动后删除备份包",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        if (!candidateName.isNullOrBlank()) {
                            Text(
                                text = candidateName,
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
                    PendingBackupDeleteStore.confirmDeleteOnNextLaunch(context, deleteOnNextLaunch)
                    exitProcess(0)
                }
            ) {
                Text(stringResource(R.string.backup_page_restart_app))
            }
        },
    )
}
'''


def write_store():
    p = ROOT / STORE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(STORE_CODE, encoding='utf-8')
    if balance(STORE_CODE) != 0:
        fail('store: balance != 0')
    print('batch239: PendingBackupDeleteStore OK')


def patch_dialog():
    p = ROOT / DIALOG
    if not p.exists():
        fail('BackupDialog.kt missing')
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        print('batch239: BackupDialog already applied')
        return
    p.write_text(DIALOG_CODE, encoding='utf-8')
    if balance(DIALOG_CODE) != 0:
        fail('BackupDialog: balance != 0')
    print('batch239: BackupDialog OK')


def patch_tab():
    p = ROOT / TAB
    if not p.exists():
        fail('ImportExportTab.kt missing')
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        print('batch239: ImportExportTab already applied')
        return
    bal0 = balance(t)
    old = ('                    ' + Q + 'local' + Q + ' -> {' + NL
           + '                        val temp = File(context.cacheDir, ' + Q + 'temp_restore_${System.nanoTime()}.zip' + Q + ')')
    new = ('                    ' + Q + 'local' + Q + ' -> {' + NL
           + '                        me.rerere.rikkahub.data.sync.PendingBackupDeleteStore.recordLocalBackupCandidate(context, sourceUri) // ' + MARK + NL
           + '                        val temp = File(context.cacheDir, ' + Q + 'temp_restore_${System.nanoTime()}.zip' + Q + ')')
    t = replace_once(t, old, new, 'ImportExportTab local branch')
    if balance(t) != bal0:
        fail('ImportExportTab: balance changed')
    p.write_text(t, encoding='utf-8')
    print('batch239: ImportExportTab OK')


def patch_app():
    p = ROOT / APP
    if not p.exists():
        fail('RikkaHubApp.kt missing')
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        print('batch239: RikkaHubApp already applied')
        return
    bal0 = balance(t)
    old = ('    private fun deleteTempFiles() {' + NL
           + '        get<AppScope>().launch(Dispatchers.IO) {' + NL
           + '            val dir = appTempFolder' + NL
           + '            if (dir.exists()) {' + NL
           + '                dir.deleteRecursively()' + NL
           + '            }' + NL
           + '        }' + NL
           + '    }')
    new = ('    private fun deleteTempFiles() {' + NL
           + '        get<AppScope>().launch(Dispatchers.IO) {' + NL
           + '            val dir = appTempFolder' + NL
           + '            if (dir.exists()) {' + NL
           + '                dir.deleteRecursively()' + NL
           + '            }' + NL
           + '            runCatching {' + NL
           + '                me.rerere.rikkahub.data.sync.PendingBackupDeleteStore.executePendingDeleteOnStartup(this@RikkaHubApp) // ' + MARK + NL
           + '            }.onFailure {' + NL
           + '                Log.w(TAG, ' + Q + 'executePendingDeleteOnStartup failed' + Q + ', it)' + NL
           + '            }' + NL
           + '        }' + NL
           + '    }')
    t = replace_once(t, old, new, 'RikkaHubApp deleteTempFiles')
    if balance(t) != bal0:
        fail('RikkaHubApp: balance changed')
    p.write_text(t, encoding='utf-8')
    print('batch239: RikkaHubApp OK')


def main():
    write_store()
    patch_dialog()
    patch_tab()
    patch_app()
    print('::notice::batch239 OK - backup delete prompt after restore + auto-delete on next startup')


main()

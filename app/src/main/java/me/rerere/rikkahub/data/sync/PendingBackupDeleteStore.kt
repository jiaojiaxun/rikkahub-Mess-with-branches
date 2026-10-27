package me.rerere.rikkahub.data.sync

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
            toast(context, if (nameStr.isNotBlank()) "已删除备份包：" + nameStr else "已删除上次恢复的备份包")
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
            toast(context, if (nameStr.isNotBlank()) "已自动删除备份包：" + nameStr else "已自动删除上次恢复的备份包")
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

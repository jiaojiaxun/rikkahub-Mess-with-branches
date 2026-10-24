package me.rerere.rikkahub.data.sync

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.activity.result.contract.ActivityResultContract

/**
 * rhBackupDel280: 与 [androidx.activity.result.contract.ActivityResultContracts.OpenDocument]
 * 行为一致，但**显式请求写权限 + 持久化权限**。
 *
 * 为什么必须自定义：
 * ACTION_OPEN_DOCUMENT 只在调用方请求了 FLAG_GRANT_WRITE_URI_PERMISSION 时才会下发写权限。
 * 官方 OpenDocument() 契约的 createIntent 里没有这个标志，所以拿到的 URI 只能读；
 * 而「恢复后删除备份包」要走 DocumentsContract.deleteDocument，必须要写权限。
 */
class OpenDocumentWithWriteContract : ActivityResultContract<Array<String>, Uri?>() {
    override fun createIntent(context: Context, input: Array<String>): Intent {
        return Intent(Intent.ACTION_OPEN_DOCUMENT)
            .addCategory(Intent.CATEGORY_OPENABLE)
            .setType("*/*")
            .putExtra(Intent.EXTRA_MIME_TYPES, input)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            .addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
            .addFlags(Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION)
    }

    override fun parseResult(resultCode: Int, intent: Intent?): Uri? {
        if (resultCode != Activity.RESULT_OK) return null
        return intent?.data
    }
}

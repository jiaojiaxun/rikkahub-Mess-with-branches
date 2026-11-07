package me.rerere.rikkahub.data.db.fts

import android.content.Context
import android.util.Log
import androidx.sqlite.db.SupportSQLiteDatabase
import java.io.File

object SimpleDictManager {

    private const val DICT_ASSET_DIR = "simple_dict"
    private const val VERSION_FILE = "version.txt"

    // 与 assets 中的词典版本对齐，更新词典时递增此值
    private const val CURRENT_VERSION = 1

    @Volatile
    private var registered = false
    private val registerLock = Any()

    /**
     * 幂等、best-effort jieba 词典注册。首次调用解压词典并执行 SELECT jieba_dict(?)
     * (磁盘 IO + 整本词典加载)，因此从 Room onOpen 挪出：DataSourceModule 后台预热 +
     * 搜索/索引路径懒注册兜底。失败只记日志，下次冷启动重试。
     */
    fun ensureRegistered(context: Context, db: SupportSQLiteDatabase) {
        if (registered) return
        synchronized(registerLock) {
            if (registered) return
            try {
                val dictDir = extractDict(context)
                val cursor = db.query("SELECT jieba_dict(?)", arrayOf(dictDir.absolutePath))
                cursor.use {
                    if (it.moveToFirst()) {
                        val result = it.getString(0)
                        if (result?.trimEnd('/') != dictDir.absolutePath.trimEnd('/')) {
                            Log.e("SimpleDictManager", "jieba_dict failed: $result, path=${dictDir.absolutePath}")
                        }
                    }
                }
            } catch (e: Exception) {
                Log.e("SimpleDictManager", "ensureRegistered failed", e)
            }
            registered = true
        }
    }

    /**
     * 将 assets/simple_dict 解压到 files/simple_dict，返回词典目录。
     * 已是最新版本时直接返回，无需重复拷贝。
     * 可在任意线程调用。
     */
    fun extractDict(context: Context): File {
        val destDir = File(context.filesDir, DICT_ASSET_DIR)
        val versionFile = File(destDir, VERSION_FILE)

        if (versionFile.exists() && versionFile.readText().trim().toIntOrNull() == CURRENT_VERSION) {
            return destDir
        }

        destDir.deleteRecursively()
        destDir.mkdirs()
        copyAssetDir(context, DICT_ASSET_DIR, destDir)
        versionFile.writeText(CURRENT_VERSION.toString())
        return destDir
    }

    private fun copyAssetDir(context: Context, assetPath: String, destDir: File) {
        val assets = context.assets.list(assetPath) ?: return
        for (name in assets) {
            val childAsset = "$assetPath/$name"
            val destFile = File(destDir, name)
            val children = context.assets.list(childAsset)
            if (!children.isNullOrEmpty()) {
                destFile.mkdirs()
                copyAssetDir(context, childAsset, destFile)
            } else {
                context.assets.open(childAsset).use { input ->
                    destFile.outputStream().use { output ->
                        input.copyTo(output)
                    }
                }
            }
        }
    }
}

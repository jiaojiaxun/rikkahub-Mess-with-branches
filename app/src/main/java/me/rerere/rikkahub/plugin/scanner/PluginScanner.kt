/*
 * 橘瓣 OrangeChat
 * 衍生自 RikkaHub (https://github.com/rikkahub/rikkahub)，原作者 RE
 * 本项目基于 GNU AGPL v3 开源，详见根目录 LICENSE 文件
 */

package me.rerere.rikkahub.plugin.scanner

import android.content.Context
import android.net.Uri
import kotlinx.serialization.json.Json
import me.rerere.rikkahub.plugin.model.PluginInfo
import me.rerere.rikkahub.plugin.model.PluginManifest
import java.io.File
import java.io.FileOutputStream
import java.util.zip.ZipInputStream

/**
 * 插件扫描器
 * 负责扫描、导入和管理插件目录
 */
class PluginScanner(
    private val context: Context,
) {
    companion object {
        const val PLUGINS_DIR = "orangechat/plugins"
        const val MANIFEST_FILE = "manifest.json"
        private const val MAX_ARCHIVE_BYTES = 32L * 1024 * 1024
        private const val MAX_UNPACKED_BYTES = 64L * 1024 * 1024
        private const val MAX_ENTRY_BYTES = 8L * 1024 * 1024
        private const val MAX_ARCHIVE_ENTRIES = 512
        private val SAFE_ID = Regex("^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
        private val SAFE_NAME = Regex("^[A-Za-z0-9_-]{1,48}$")
        private val SAFE_HANDLER = Regex("^[A-Za-z_$][A-Za-z0-9_$]{0,63}$")
        private val ALLOWED_PARAMETER_TYPES = setOf("string", "number", "integer", "boolean", "object", "array")
    }

    private val json = Json {
        ignoreUnknownKeys = true
        isLenient = true
    }

    /**
     * 获取插件根目录。插件只存放在应用私有 filesDir，避免外部存储权限和跨应用窥探。
     */
    val pluginsDir: File
        get() = File(context.filesDir, PLUGINS_DIR).apply { mkdirs() }

    /**
     * 确保插件目录存在
     */
    fun ensurePluginsDir(): File = pluginsDir

    /**
     * 扫描所有插件
     */
    fun scanPlugins(): List<PluginInfo> {
        val dir = ensurePluginsDir()
        if (!dir.exists() || !dir.isDirectory) {
            return emptyList()
        }

        return dir.listFiles { file -> file.isDirectory }
            ?.mapNotNull { pluginDir -> loadPluginInfo(pluginDir) }
            ?: emptyList()
    }

    /**
     * 加载单个插件信息
     */
    fun loadPluginInfo(pluginDir: File): PluginInfo? {
        val manifestFile = File(pluginDir, MANIFEST_FILE)
        if (!manifestFile.exists()) {
            return null
        }

        return try {
            val content = manifestFile.readText()
            val manifest = json.decodeFromString(PluginManifest.serializer(), content)
            validateManifest(manifest)

            // 完整性校验：若存在 .integrity 文件则验证，失败则禁用并标记错误
            val integrityFile = File(pluginDir, ".integrity")
            if (integrityFile.exists()) {
                val stored = integrityFile.readText().trim()
                val current = computePluginChecksum(pluginDir)
                if (stored != current) {
                    return PluginInfo(
                        manifest = manifest,
                        directory = pluginDir,
                        isEnabled = false,
                        loadError = "完整性校验失败：插件文件已被篡改或损坏"
                    )
                }
            }

            PluginInfo(
                manifest = manifest,
                directory = pluginDir,
                isEnabled = true // 默认启用
            )
        } catch (e: Exception) {
            // 解析失败，返回错误状态的插件
            PluginInfo(
                manifest = PluginManifest(
                    id = pluginDir.name,
                    name = pluginDir.name,
                    description = "加载失败: ${e.message}",
                    version = "error",
                    author = "unknown",
                    icon = "⚠️",
                    entry = "",
                    tools = emptyList(),
                    config = emptyList()
                ),
                directory = pluginDir,
                isEnabled = false,
                loadError = e.message
            )
        }
    }

    /**
     * 从ZIP文件预览插件（不解压到插件目录，仅解析 manifest）
     * 返回 manifest 和临时目录，供调用方展示权限确认对话框。
     * 调用方确认后应调用 [completeImport] 完成导入；取消时应清理临时目录。
     */
    suspend fun previewFromZip(uri: Uri): Result<Pair<PluginManifest, File>> {
        return try {
            val tempFile = File(context.cacheDir, "plugin_preview_${System.currentTimeMillis()}.zip")
            context.contentResolver.openInputStream(uri)?.use { input ->
                FileOutputStream(tempFile).use { output ->
                    copyBounded(input, output, MAX_ARCHIVE_BYTES)
                }
            } ?: return Result.failure(IllegalStateException("无法读取文件"))

            val tempDir = File(context.cacheDir, "plugin_preview_${System.currentTimeMillis()}")
            unzip(tempFile, tempDir)

            val manifestFile = findManifest(tempDir)
                ?: run {
                    tempFile.delete()
                    tempDir.deleteRecursively()
                    return Result.failure(IllegalArgumentException("找不到 manifest.json"))
                }

            val manifest = json.decodeFromString(PluginManifest.serializer(), manifestFile.readText())
            validateManifest(manifest)

            // 预览阶段保留 tempFile 和 tempDir，供后续 completeImport 使用
            Result.success(manifest to tempDir)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 完成插件导入（在 previewFromZip 后调用）
     * @param manifest 预览阶段解析的 manifest
     * @param tempDir 预览阶段解压的临时目录
     */
    suspend fun completeImport(manifest: PluginManifest, tempDir: File): Result<PluginInfo> {
        return try {
            val existingPlugins = scanPlugins()
            if (existingPlugins.any { it.manifest.id == manifest.id }) {
                tempDir.deleteRecursively()
                return Result.failure(IllegalArgumentException("插件 ${manifest.id} 已存在"))
            }

            val manifestFile = findManifest(tempDir)
                ?: run {
                    tempDir.deleteRecursively()
                    return Result.failure(IllegalArgumentException("找不到 manifest.json"))
                }

            val entryFile = File(manifestFile.parentFile, manifest.entry)
            if (!entryFile.exists()) {
                tempDir.deleteRecursively()
                return Result.failure(IllegalArgumentException("找不到入口文件: ${manifest.entry}"))
            }

            val pluginDir = File(pluginsDir, manifest.id)
            if (pluginDir.exists()) {
                pluginDir.deleteRecursively()
            }
            manifestFile.parentFile?.copyRecursively(pluginDir, overwrite = true)
            tempDir.deleteRecursively()

            // 写入完整性校验和
            runCatching {
                val checksum = computePluginChecksum(pluginDir)
                File(pluginDir, ".integrity").writeText(checksum)
            }

            loadPluginInfo(pluginDir)?.let { Result.success(it) }
                ?: Result.failure(IllegalStateException("无法加载插件信息"))
        } catch (e: Exception) {
            tempDir.deleteRecursively()
            Result.failure(e)
        }
    }

    /**
     * 从ZIP文件导入插件（旧版一次性导入，保留用于兼容）
     */
    suspend fun importFromZip(uri: Uri): Result<PluginInfo> {
        return try {
            // 1. 复制到临时文件
            val tempFile = File(context.cacheDir, "plugin_import_${System.currentTimeMillis()}.zip")
            context.contentResolver.openInputStream(uri)?.use { input ->
                FileOutputStream(tempFile).use { output ->
                    copyBounded(input, output, MAX_ARCHIVE_BYTES)
                }
            } ?: return Result.failure(IllegalStateException("无法读取文件"))

            // 2. 解压到临时目录
            val tempDir = File(context.cacheDir, "plugin_import_${System.currentTimeMillis()}")
            unzip(tempFile, tempDir)

            // 3. 查找manifest.json
            val manifestFile = findManifest(tempDir)
                ?: return Result.failure(IllegalArgumentException("找不到 manifest.json"))

            // 4. 解析manifest
            val content = manifestFile.readText()
            val manifest = json.decodeFromString(PluginManifest.serializer(), content)
            validateManifest(manifest)

            // 5. 检查ID是否重复
            val existingPlugins = scanPlugins()
            if (existingPlugins.any { it.manifest.id == manifest.id }) {
                // 清理临时文件
                tempFile.delete()
                tempDir.deleteRecursively()
                return Result.failure(IllegalArgumentException("插件 ${manifest.id} 已存在"))
            }

            // 6. 验证入口文件
            val entryFile = File(manifestFile.parentFile, manifest.entry)
            if (!entryFile.exists()) {
                tempFile.delete()
                tempDir.deleteRecursively()
                return Result.failure(IllegalArgumentException("找不到入口文件: ${manifest.entry}"))
            }

            // 7. 移动到插件目录
            val pluginDir = File(pluginsDir, manifest.id)
            if (pluginDir.exists()) {
                pluginDir.deleteRecursively()
            }
            manifestFile.parentFile?.copyRecursively(pluginDir, overwrite = true)

            // 8. 清理临时文件
            tempFile.delete()
            tempDir.deleteRecursively()

            // 9. 返回插件信息
            loadPluginInfo(pluginDir)?.let { Result.success(it) }
                ?: Result.failure(IllegalStateException("无法加载插件信息"))

        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    /**
     * 删除插件
     */
    fun deletePlugin(pluginId: String): Boolean {
        val pluginDir = File(pluginsDir, pluginId)
        return if (pluginDir.exists()) {
            pluginDir.deleteRecursively()
        } else {
            false
        }
    }

    /**
     * 获取插件目录
     */
    fun getPluginDir(pluginId: String): File {
        return File(pluginsDir, pluginId)
    }

    /**
     * 解压 ZIP 文件。拒绝绝对路径、.. 穿越、超大条目和超大总展开体积。
     */
    private fun unzip(zipFile: File, destDir: File) {
        destDir.mkdirs()
        val destRoot = destDir.canonicalFile
        var entryCount = 0
        var unpackedBytes = 0L
        ZipInputStream(zipFile.inputStream().buffered()).use { zis ->
            var entry: java.util.zip.ZipEntry? = zis.nextEntry
            while (entry != null) {
                if (++entryCount > MAX_ARCHIVE_ENTRIES) {
                    throw IllegalArgumentException("插件压缩包条目过多")
                }
                val normalizedName = entry.name.replace(92.toChar(), '/')
                if (!isSafeRelativePath(normalizedName)) {
                    throw IllegalArgumentException("插件压缩包包含不安全路径")
                }
                val file = File(destRoot, normalizedName).canonicalFile
                val rootPrefix = destRoot.path + File.separator
                if (file.path != destRoot.path && !file.path.startsWith(rootPrefix)) {
                    throw IllegalArgumentException("插件压缩包路径越界")
                }
                if (entry.isDirectory) {
                    file.mkdirs()
                } else {
                    val declaredSize = entry.size
                    if (declaredSize > MAX_ENTRY_BYTES) {
                        throw IllegalArgumentException("插件文件过大")
                    }
                    file.parentFile?.mkdirs()
                    FileOutputStream(file).use { output ->
                        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                        var entryBytes = 0L
                        while (true) {
                            val read = zis.read(buffer)
                            if (read < 0) break
                            entryBytes += read
                            unpackedBytes += read
                            if (entryBytes > MAX_ENTRY_BYTES || unpackedBytes > MAX_UNPACKED_BYTES) {
                                throw IllegalArgumentException("插件解压后体积过大")
                            }
                            output.write(buffer, 0, read)
                        }
                    }
                }
                zis.closeEntry()
                entry = zis.nextEntry
            }
        }
    }

    private fun copyBounded(input: java.io.InputStream, output: java.io.OutputStream, maxBytes: Long) {
        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
        var copied = 0L
        while (true) {
            val read = input.read(buffer)
            if (read < 0) break
            copied += read
            if (copied > maxBytes) throw IllegalArgumentException("插件压缩包过大")
            output.write(buffer, 0, read)
        }
    }

    private fun validateManifest(manifest: PluginManifest) {
        require(SAFE_ID.matches(manifest.id) && manifest.id != "." && manifest.id != "..") { "插件 ID 不合法" }
        require(manifest.name.isNotBlank() && manifest.name.length <= 120) { "插件名称不合法" }
        require(isSafeRelativePath(manifest.entry)) { "插件入口路径不合法" }
        require(manifest.tools.size <= 64) { "插件工具数量过多" }
        require(manifest.tools.map { it.name }.distinct().size == manifest.tools.size) { "插件工具名称重复" }
        manifest.tools.forEach { tool ->
            require(SAFE_NAME.matches(tool.name)) { "插件工具名称不合法" }
            require(tool.description.length <= 4096) { "插件工具描述过长" }
            require(tool.parameters.size <= 32) { "插件工具参数过多" }
            require(tool.parameters.map { it.name }.distinct().size == tool.parameters.size) { "插件参数名称重复" }
            tool.parameters.forEach { parameter ->
                require(SAFE_NAME.matches(parameter.name)) { "插件参数名称不合法" }
                require(parameter.type in ALLOWED_PARAMETER_TYPES) { "插件参数类型不支持" }
                require(parameter.description.orEmpty().length <= 2048) { "插件参数描述过长" }
            }
        }
        require(manifest.allowedHosts.size <= 64) { "插件网络白名单过长" }
        manifest.allowedHosts.forEach { host ->
            require(host == "*" || (host.isNotBlank() && host.length <= 253 && !host.contains('/') && host.indexOf(92.toChar()) < 0 && host.none { it.isWhitespace() })) {
                "插件网络域名不合法"
            }
        }
        manifest.hooks.forEach { hook ->
            require(hook.event == "message_sent" || hook.event == "message_received") { "插件事件类型不支持" }
            require(SAFE_HANDLER.matches(hook.handler)) { "插件事件处理函数名不合法" }
        }
        manifest.customPageWebView?.let { require(isSafeRelativePath(it.entry)) { "插件 WebView 入口路径不合法" } }
    }

    private fun isSafeRelativePath(path: String): Boolean {
        if (path.isBlank() || path.startsWith('/') || path.indexOf(92.toChar()) >= 0) return false
        return path.split('/').none { it.isEmpty() || it == "." || it == ".." }
    }

    /**
     * 查找manifest.json文件
     * 优先在根目录查找，然后在子目录中查找
     */
    private fun findManifest(dir: File): File? {
        // 优先在根目录找
        val rootManifest = File(dir, MANIFEST_FILE)
        if (rootManifest.exists()) {
            return rootManifest
        }

        // 在子目录中查找
        return dir.listFiles { file -> file.isDirectory }
            ?.asSequence()
            ?.map { subdir -> File(subdir, MANIFEST_FILE) }
            ?.firstOrNull { it.exists() }
    }

    /**
     * 计算插件目录的 SHA-256 校验和（排除 .integrity 文件本身，稳定排序）
     */
    private fun computePluginChecksum(dir: File): String {
        val digest = java.security.MessageDigest.getInstance("SHA-256")
        dir.walkTopDown()
            .filter { it.isFile && it.name != ".integrity" }
            .sortedBy { it.relativeTo(dir).path.replace('\\', '/') }
            .forEach { file ->
                digest.update(file.relativeTo(dir).path.replace('\\', '/').toByteArray(Charsets.UTF_8))
                digest.update(file.readBytes())
            }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}
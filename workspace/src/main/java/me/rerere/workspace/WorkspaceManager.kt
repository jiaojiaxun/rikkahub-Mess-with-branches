package me.rerere.workspace

import java.io.File
import java.io.InputStream
import java.io.OutputStream
import java.nio.charset.Charset
import java.nio.charset.StandardCharsets

/**
 * 应用内持久文件工作区管理器。
 *
 * 工作区只提供受限文件操作，所有路径都解析到 filesDir/<workspace>/files 下；
 * 仅管理应用内文件目录，不执行操作系统命令，也不维护后台进程。
 */
class WorkspaceManager(
    private val baseDir: File,
    private val config: WorkspaceConfig = WorkspaceConfig(),
) {
    private val fileSystem = WorkspaceFileSystem(config)

    init {
        baseDir.mkdirs()
    }

    fun ensureWorkspace(root: String): File {
        val dir = workspaceDir(root)
        filesDir(root).mkdirs()
        return dir
    }

    fun workspaceDir(root: String): File {
        requireValidRoot(root)
        return File(baseDir, root)
    }

    fun filesDir(root: String): File = File(workspaceDir(root), FILES_DIR)

    fun listFiles(
        root: String,
        path: String = "",
        area: WorkspaceStorageArea = WorkspaceStorageArea.FILES,
    ): List<WorkspaceFileEntry> {
        require(area == WorkspaceStorageArea.FILES) { "Only the files workspace is available" }
        return fileSystem.list(filesDir(root), path)
    }

    fun readText(
        root: String,
        path: String,
        charset: Charset = StandardCharsets.UTF_8,
    ): String = fileSystem.readText(filesDir(root), path, charset)

    fun writeText(
        root: String,
        path: String,
        text: String,
        overwrite: Boolean = true,
        charset: Charset = StandardCharsets.UTF_8,
    ): WorkspaceFileEntry = fileSystem.writeText(filesDir(root), path, text, overwrite, charset)

    fun createFolder(root: String, path: String): WorkspaceFileEntry {
        val directory = fileSystem.resolve(filesDir(root), path)
        require(!directory.exists() || directory.isDirectory) { "Path is not a directory: $path" }
        directory.mkdirs()
        return WorkspaceFileEntry(
            path = path.trim('/'),
            name = directory.name,
            isDirectory = true,
            sizeBytes = 0L,
            updatedAt = directory.lastModified(),
        )
    }

    fun importFile(
        root: String,
        destinationPath: String = "",
        fileName: String,
        inputStream: InputStream,
    ): WorkspaceFileEntry {
        val targetPath = if (destinationPath.isBlank()) fileName else "$destinationPath/$fileName"
        return fileSystem.importBytes(filesDir(root), targetPath, inputStream)
    }

    fun fileSize(root: String, path: String): Long =
        fileSystem.resolve(filesDir(root), path).also { it.requireFile(path) }.length()

    fun exportFile(root: String, path: String, outputStream: OutputStream) {
        val file = fileSystem.resolve(filesDir(root), path)
        file.requireFile(path)
        outputStream.use { out -> file.inputStream().use { it.copyTo(out) } }
    }

    fun deleteFile(root: String, path: String, recursive: Boolean = false): Boolean =
        fileSystem.delete(filesDir(root), path, recursive)

    fun moveFile(root: String, source: String, target: String, overwrite: Boolean = false): WorkspaceFileEntry =
        fileSystem.move(filesDir(root), source, target, overwrite)

    fun glob(root: String, pattern: String, path: String = ""): List<WorkspaceFileEntry> =
        fileSystem.glob(filesDir(root), pattern, path)

    fun grep(
        root: String,
        query: String,
        path: String = "",
        regex: Boolean = false,
        ignoreCase: Boolean = true,
        includeGlob: String? = null,
    ): List<WorkspaceSearchMatch> =
        fileSystem.grep(filesDir(root), query, path, regex, ignoreCase, includeGlob)

    fun tree(root: String, path: String = "", maxDepth: Int = 10): WorkspaceTreeResult =
        fileSystem.tree(filesDir(root), path, maxDepth)

    fun cleanupAllTempDirs() {
        // 保留旧调用的幂等入口；纯文件工作区没有命令临时目录需要清理。
    }

    fun deleteWorkspace(root: String): Boolean = workspaceDir(root).deleteRecursively()

    private fun requireValidRoot(root: String) {
        require(root.matches(ROOT_NAME_REGEX)) { "Invalid workspace root name: $root" }
    }

    private fun File.requireFile(path: String) {
        require(exists()) { "File does not exist: $path" }
        require(isFile) { "Path is not a file: $path" }
    }

    companion object {
        private const val FILES_DIR = "files"
        private val ROOT_NAME_REGEX = Regex("[A-Za-z0-9._-]+")
    }
}

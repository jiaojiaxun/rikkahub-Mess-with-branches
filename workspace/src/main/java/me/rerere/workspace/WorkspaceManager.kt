package me.rerere.workspace

import java.io.File
import java.io.InputStream
import java.io.OutputStream
import java.nio.charset.Charset
import java.nio.charset.StandardCharsets
import java.nio.file.Files

class WorkspaceManager(
    private val baseDir: File,
    private val config: WorkspaceConfig = WorkspaceConfig(),
    val shellRunner: WorkspaceShellRunner = HostShellRunner(),
    private val bindMounts: List<WorkspaceBindMount> = emptyList(),
) {
    private val fileSystem = WorkspaceFileSystem(config)
    private val background = WorkspaceBackgroundProcesses()

    // 让 startBackground 的启动+注册 与 deleteWorkspace 的 killAll+删除 互斥:
    // 要么启动先完成(随后被 killAll 杀掉), 要么删除先完成(随后 shellRunner.start 因 rootfs
    // 缺失而失败并抛出), 不会出现"进程活着但 workspace 目录已删"的孤儿进程
    private val backgroundLifecycleLock = Any()

    // 按 target 长度降序, 保证 /a/b 优先于 /a 匹配
    private val sortedBindMounts = bindMounts.sortedByDescending { it.target.trimEnd('/').length }

    init {
        baseDir.mkdirs()
    }

    fun ensureWorkspace(root: String): File { // rhWsFix313
        val dir = workspaceDir(root)
        filesDir(root).mkdirs()
        linuxDir(root).mkdirs()
        tempDir(root).mkdirs()
        // rhWsBind311: proot 的 -b 要求 guest 挂载点存在。按 bindMounts 补建空目录,
        // 已经装过旧 rootfs 的用户不需要重装; 每次.executeCommand 前都会走到这里。
        File(linuxDir(root), WorkspaceBusybox.RH_LIBS.trimStart('/')).mkdirs()
        File(linuxDir(root), ROOTFS_WORKSPACE_DIR.trimStart('/')).mkdirs()
        for (mount in sortedBindMounts) {
            File(linuxDir(root), mount.target.trimStart('/')).mkdirs()
        }
        return dir
    }

    fun workspaceDir(root: String): File {
        requireValidRoot(root)
        return File(baseDir, root)
    }

    fun filesDir(root: String): File = File(workspaceDir(root), FILES_DIR)

    fun linuxDir(root: String): File = File(workspaceDir(root), LINUX_DIR)

    fun tempDir(root: String): File = File(workspaceDir(root), TEMP_DIR)

    fun hasRootfs(root: String): Boolean {
        val dir = linuxDir(root)
        val sh = File(dir, "bin/sh")
        // rhWsStage307: 安装后 bin/sh 指向 /rh-libs/libbusybox.so, 该目标在宿主不存在;
        // 只认 isFile 会让 checkIntegrity 把刚装好的 READY 误判为文件缺失并重置 DISABLED。
        val shPresent = sh.isFile || Files.isSymbolicLink(sh.toPath())
        // 同时要求 applet 农场已建: 旧版 rootfs(无 /usr/rh-bin)在 API 29+ 仍跑不了命令。
        return shPresent && WorkspaceBusybox.hasFarm(dir)
    }

    fun deleteWorkspace(root: String): Boolean = synchronized(backgroundLifecycleLock) {
        // 先杀掉该 workspace 所有后台进程, 再删目录, 避免进程仍持有已删除目录下的 fd
        killAllBackground(root)
        workspaceDir(root).deleteRecursively()
    }

    fun listFiles(
        root: String,
        path: String = "",
        area: WorkspaceStorageArea = WorkspaceStorageArea.FILES,
        limit: Int? = null,
    ): List<WorkspaceFileEntry> =
        if (limit == null) {
            fileSystem.list(areaDir(root, area), path)
        } else {
            fileSystem.list(areaDir(root, area), path, limit)
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

    fun importFile(
        root: String,
        destinationPath: String,
        area: WorkspaceStorageArea = WorkspaceStorageArea.FILES,
        fileName: String,
        inputStream: InputStream,
    ): WorkspaceFileEntry {
        val areaRoot = areaDir(root, area)
        val targetPath = if (destinationPath.isBlank()) fileName else "$destinationPath/$fileName"
        return fileSystem.importBytes(areaRoot, targetPath, inputStream)
    }

    fun fileSize(
        root: String,
        path: String,
        area: WorkspaceStorageArea = WorkspaceStorageArea.FILES,
    ): Long {
        val file = fileSystem.resolve(areaDir(root, area), path)
        require(file.exists()) { "File does not exist: $path" }
        require(file.isFile) { "Path is not a file: $path" }
        return file.length()
    }

    fun resolveFile(
        root: String,
        path: String,
        area: WorkspaceStorageArea = WorkspaceStorageArea.FILES,
    ): File {
        val file = fileSystem.resolve(areaDir(root, area), path)
        require(file.exists()) { "File does not exist: $path" }
        require(file.isFile) { "Path is not a file: $path" }
        return file
    }

    fun exportFile(
        root: String,
        path: String,
        area: WorkspaceStorageArea = WorkspaceStorageArea.FILES,
        outputStream: OutputStream,
    ) {
        val file = fileSystem.resolve(areaDir(root, area), path)
        require(file.exists()) { "File does not exist: $path" }
        require(file.isFile) { "Path is not a file: $path" }
        outputStream.use { out -> file.inputStream().use { it.copyTo(out) } }
    }

    /**
     * 把 Rootfs 内的绝对路径映射到宿主机上的真实文件。
     *
     * bind mount 的 source 本身就是 Android 侧的普通目录, 因此 /skills 这类挂载路径
     * 可以直接用文件 IO 访问, 无需经过 PRoot; 只是 Rootfs 目录里对应位置是个空挂载点,
     * 按 [WorkspaceStorageArea.LINUX] 解析必然落空。
     */
    fun resolveRootfsPath(root: String, path: String): RootfsLocation {
        val trimmed = path.trim().trimEnd('/').ifBlank { "/" }
        require(trimmed.startsWith("/")) { "Rootfs path must be absolute: $path" }

        sortedBindMounts.forEach { mount ->
            val target = mount.target.trimEnd('/')
            if (trimmed == target) return RootfsLocation(mount.source, "")
            if (trimmed.startsWith("$target/")) {
                return RootfsLocation(mount.source, trimmed.removePrefix("$target/"))
            }
        }

        if (trimmed == ROOTFS_WORKSPACE_DIR || trimmed.startsWith("$ROOTFS_WORKSPACE_DIR/")) {
            return RootfsLocation(
                rootDir = filesDir(root),
                relativePath = trimmed.removePrefix(ROOTFS_WORKSPACE_DIR).trimStart('/'),
            )
        }

        // 内核伪文件系统: 显式拒绝, 而不是回落到一个必然读不到的物理路径
        KERNEL_FS_MOUNTS.firstOrNull { trimmed == it || trimmed.startsWith("$it/") }?.let {
            error("$it is a kernel filesystem and cannot be read as a file, use workspace_shell instead")
        }

        return RootfsLocation(linuxDir(root), trimmed.trimStart('/'))
    }

    fun rootfsFileSize(root: String, path: String): Long =
        resolveRootfsFile(root, path).also { it.requireReadableFile(path) }.length()

    fun exportRootfsFile(root: String, path: String, outputStream: OutputStream) {
        val file = resolveRootfsFile(root, path)
        file.requireReadableFile(path)
        outputStream.use { out -> file.inputStream().use { it.copyTo(out) } }
    }

    /** 按 Rootfs 内绝对路径递归列出目录树, 支持 /workspace、bind mount 与 Rootfs 内部路径 */
    fun rootfsTree(root: String, path: String, maxDepth: Int = 10): WorkspaceTreeResult {
        val location = resolveRootfsPath(root, path)
        return fileSystem.tree(location.rootDir, location.relativePath, maxDepth)
    }

    private fun resolveRootfsFile(root: String, path: String): File {
        val location = resolveRootfsPath(root, path)
        return fileSystem.resolve(location.rootDir, location.relativePath)
    }

    private fun File.requireReadableFile(path: String) {
        require(exists()) { "File does not exist: $path" }
        require(isFile) { "Path is not a file: $path" }
    }

    fun deleteFile(
        root: String,
        path: String,
        recursive: Boolean = false,
        area: WorkspaceStorageArea = WorkspaceStorageArea.FILES,
    ): Boolean =
        fileSystem.delete(areaDir(root, area), path, recursive)

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

    fun executeCommand(
        root: String,
        command: String,
        cwd: String = "",
        timeoutMillis: Long = DEFAULT_COMMAND_TIMEOUT_MS,
        stdin: ByteArray? = null,
        shellCompatibilityMode: Boolean = false,
    ): WorkspaceCommandResult {
        require(command.isNotBlank()) { "Command is required" }
        val workingDir = resolveCommandWorkingDir(root, cwd)

        return shellRunner.execute(
            WorkspaceShellContext(
                root = root,
                command = command,
                cwd = cwd,
                filesDir = filesDir(root),
                linuxDir = linuxDir(root),
                tempDir = tempDir(root),
                workingDir = workingDir,
                timeoutMillis = timeoutMillis,
                stdin = stdin,
                bindMounts = bindMounts,
                shellCompatibilityMode = shellCompatibilityMode,
            )
        )
    }

    /**
     * Starts [command] as a long-lived background process for [root]. The process runs
     * in the foreground of its own proot invocation; the caller polls/kills it via
     * [backgroundStatus]/[killBackground]. Throws IllegalStateException if [root] is
     * already at the running-process cap.
     */
    fun startBackground(root: String, command: String, cwd: String = ""): BackgroundStatus =
        synchronized(backgroundLifecycleLock) {
            require(command.isNotBlank()) { "Command is required" }
            val workingDir = resolveCommandWorkingDir(root, cwd)

            val process = shellRunner.start(
                WorkspaceShellContext(
                    root = root,
                    command = command,
                    cwd = cwd,
                    filesDir = filesDir(root),
                    linuxDir = linuxDir(root),
                    tempDir = tempDir(root),
                    workingDir = workingDir,
                    timeoutMillis = 0L,
                )
            )
            background.start(root, process, command, cwd)
        }

    fun backgroundStatus(root: String, id: String): BackgroundStatus? = background.status(root, id)

    fun listBackground(root: String): List<BackgroundStatus> = background.list(root)

    fun killBackground(root: String, id: String): Boolean = background.kill(root, id)

    fun killAllBackground(root: String) = background.killAll(root)

    private fun resolveCommandWorkingDir(root: String, cwd: String): File {
        val workingDir = fileSystem.resolve(filesDir(root), cwd)
        require(workingDir.exists()) { "Working directory does not exist: $cwd" }
        require(workingDir.isDirectory) { "Working path is not a directory: $cwd" }
        return workingDir
    }

    private fun requireValidRoot(root: String) {
        require(root.matches(ROOT_NAME_REGEX)) {
            "Invalid workspace root name: $root"
        }
    }

    private fun areaDir(root: String, area: WorkspaceStorageArea): File = when (area) {
        WorkspaceStorageArea.FILES -> filesDir(root)
        WorkspaceStorageArea.LINUX -> linuxDir(root)
    }

/** rhWsStage307: 在 workspace 根下开一个干净的中转目录, 失败就整体丢弃, 不碰现有 rootfs。 */
fun createRootfsStaging(root: String): File {
    val dir = File(workspaceDir(root), ROOTFS_STAGING_DIR)
    dir.deleteRecursively()
    dir.mkdirs()
    require(dir.isDirectory) { "Failed to create rootfs staging directory: " + dir.absolutePath }
    return dir
}

/** rhWsStage307: 原子上线 — 旧 rootfs 先改名备份, 再换入 staging; 换入失败时回滚。 */
fun commitRootfs(root: String, stagingDir: File) {
    require(stagingDir.isDirectory) { "Rootfs staging directory is missing: " + stagingDir.absolutePath }
    val target = linuxDir(root)
    val backup = File(workspaceDir(root), ROOTFS_BACKUP_DIR)
    backup.deleteRecursively()
    if (target.exists() && !target.renameTo(backup)) {
        error("Failed to move existing rootfs aside: " + target.absolutePath)
    }
    if (!stagingDir.renameTo(target)) {
        if (backup.exists() && !target.exists()) {
            backup.renameTo(target)
        }
        error("Failed to move new rootfs into place: " + target.absolutePath)
    }
    backup.deleteRecursively()
}

    fun cleanupAllTempDirs() {
        val roots = baseDir.listFiles()?.filter { it.isDirectory } ?: return
        for (dir in roots) {
            val root = dir.name
            if (!root.matches(ROOT_NAME_REGEX)) continue
            // PRoot temp files
            tempDir(root).let { if (it.exists()) it.deleteRecursively() }
            // Rootfs /tmp and /var/tmp
            File(linuxDir(root), "tmp").let { if (it.exists()) it.deleteRecursively() }
            File(linuxDir(root), "var/tmp").let { if (it.exists()) it.deleteRecursively() }
        }
    }

    companion object {
        private const val FILES_DIR = "files"
        private const val LINUX_DIR = "linux"
        private const val TEMP_DIR = "tmp"
        const val DEFAULT_COMMAND_TIMEOUT_MS = 30_000L
        // rhWsStage307: rootfs 安装中转目录 / 回滚备份目录(均置于 workspace 根下)
        private const val ROOTFS_STAGING_DIR = "rootfs.staging"
        private const val ROOTFS_BACKUP_DIR = "rootfs.old"

        /** Rootfs 内工作区文件区的挂载点 */
        const val ROOTFS_WORKSPACE_DIR = "/workspace"

        /** 由宿主机透传的内核伪文件系统, 只能通过 shell 访问 */
        val KERNEL_FS_MOUNTS = listOf("/dev", "/proc", "/sys")

        private val ROOT_NAME_REGEX = Regex("[A-Za-z0-9._-]+")
    }
}

/** Rootfs 内绝对路径在宿主机上的落点 */
data class RootfsLocation(
    val rootDir: File,
    val relativePath: String,
)

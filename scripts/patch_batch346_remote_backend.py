#!/usr/bin/env python3
# rhRemote346: 工作区后端抽象层 (为 SSH 远程工作区铺路)
# 只做三件事:
#   1) 新增 WorkspaceBackend + WorkspaceLayout
#   2) 新增 LocalWorkspaceBackend (把现有 WorkspaceManager 包成后端)
#   3) Workspace 增加 WorkspaceType / WorkspaceCapabilities, Manager 暴露 layout/backend/rootfsShell
# 不改任何现有调用点, 因此这一批本身应保持本地工作区行为完全不变。
import os

MARK = "rhRemote346"
DIAG = "ci_diag_batch346_remote.txt"
ROOT = os.environ.get("GITHUB_WORKSPACE", os.getcwd())


def log(msg):
    print(msg)


def balance(text):
    # 只用于自检: 返回 (左括号数, 右括号数)
    return (text.count("("), text.count(")"))


BACKEND = r'''package me.rerere.workspace

import java.io.File
import java.io.InputStream
import java.io.OutputStream

/**
 * 单个工作区的执行环境, 屏蔽本地 PRoot 与远程 SSH 等不同实现。
 *
 * 路径有两套寻址方式:
 * - 存储区 + 相对路径: 应用内文件浏览器使用, 见 [WorkspaceStorageArea]
 * - 环境内绝对路径: AI 工具与 shell 看到的路径, 例如本地 /workspace/notes.md,
 *   远程 /home/user/project/notes.md
 *
 * 方法都是阻塞 IO, 调用方负责切到 IO 线程; 取消时会中断调用线程。
 */
interface WorkspaceBackend {
    val layout: WorkspaceLayout

    /** 执行命令实际使用的 shell 路径 */
    fun shell(): String

    fun listFiles(area: WorkspaceStorageArea, path: String, limit: Int? = null): List<WorkspaceFileEntry>

    /** 读取文件区内的文本, 自带大小保护 */
    fun readText(path: String): String

    /** 写入文件区内的文本 */
    fun writeText(path: String, text: String, overwrite: Boolean): WorkspaceFileEntry

    /** 导入文件, 目标已存在时自动改名 */
    fun importFile(
        area: WorkspaceStorageArea,
        destinationPath: String,
        fileName: String,
        inputStream: InputStream,
    ): WorkspaceFileEntry

    fun fileSize(area: WorkspaceStorageArea, path: String): Long

    fun exportFile(area: WorkspaceStorageArea, path: String, outputStream: OutputStream)

    fun deleteFile(area: WorkspaceStorageArea, path: String, recursive: Boolean): Boolean

    fun absoluteFileSize(path: String): Long

    fun exportAbsoluteFile(path: String, outputStream: OutputStream)

    /** 按环境内绝对路径写入 UTF-8 文本, 父目录不存在时自动创建; 返回的条目 path 为绝对路径 */
    fun writeAbsoluteText(path: String, text: String, overwrite: Boolean): WorkspaceFileEntry

    /** 宿主机上可直接访问的文件; 没有本地落点的环境返回 null */
    fun localFile(area: WorkspaceStorageArea, path: String): File?

    /** 按环境内绝对路径解析宿主机上的文件, 不检查是否存在; 没有本地落点的环境返回 null */
    fun localAbsoluteFile(path: String): File?

    /** 执行命令, [cwd] 为相对文件区的路径 */
    fun executeCommand(
        command: String,
        cwd: String,
        timeoutMillis: Long,
        stdin: ByteArray?,
    ): WorkspaceCommandResult
}

/** 工作区在执行环境内的目录约定 */
data class WorkspaceLayout(
    /** 文件区在环境内的绝对路径, 也是 shell 的默认工作目录 */
    val workspaceDir: String,
    /** AI 写入时免强制审批的目录 */
    val writableRoots: List<String>,
) {
    /** 存储区内的相对路径转成环境内的绝对路径 */
    fun absolutePath(area: WorkspaceStorageArea, path: String): String {
        val relative = path.trim('/')
        return when (area) {
            WorkspaceStorageArea.FILES -> if (relative.isEmpty()) workspaceDir else "$workspaceDir/$relative"
            WorkspaceStorageArea.LINUX -> "/$relative"
        }
    }

    /** 文件区内的绝对路径转成相对文件区的路径, 不在文件区内时原样返回 */
    fun relativeToWorkspace(path: String): String =
        path.removePrefix("$workspaceDir/").removePrefix(workspaceDir)

    fun isWritable(path: String): Boolean {
        val normalized = path.trimEnd('/').ifBlank { "/" }
        return writableRoots.any { root -> normalized == root || normalized.startsWith("$root/") }
    }
}
'''

LOCAL = r'''package me.rerere.workspace

import java.io.File
import java.io.InputStream
import java.io.OutputStream

/** 本机上的工作区: 文件落在 [WorkspaceManager] 管理的目录下, 命令在 PRoot Rootfs 内执行 */
class LocalWorkspaceBackend(
    private val manager: WorkspaceManager,
    private val root: String,
    private val shellCompatibilityMode: Boolean = false,
) : WorkspaceBackend {
    override val layout: WorkspaceLayout
        get() = manager.layout

    override fun shell(): String = manager.rootfsShell(root)

    override fun listFiles(area: WorkspaceStorageArea, path: String, limit: Int?): List<WorkspaceFileEntry> {
        manager.ensureWorkspace(root)
        return if (limit == null) {
            manager.listFiles(root, path, area)
        } else {
            manager.listFiles(root, path, area, limit)
        }
    }

    override fun readText(path: String): String {
        manager.ensureWorkspace(root)
        return manager.readText(root, path)
    }

    override fun writeText(path: String, text: String, overwrite: Boolean): WorkspaceFileEntry {
        manager.ensureWorkspace(root)
        return manager.writeText(root, path, text, overwrite)
    }

    override fun importFile(
        area: WorkspaceStorageArea,
        destinationPath: String,
        fileName: String,
        inputStream: InputStream,
    ): WorkspaceFileEntry {
        manager.ensureWorkspace(root)
        return manager.importFile(root, destinationPath, area, fileName, inputStream)
    }

    override fun fileSize(area: WorkspaceStorageArea, path: String): Long =
        manager.fileSize(root, path, area)

    override fun exportFile(area: WorkspaceStorageArea, path: String, outputStream: OutputStream) =
        manager.exportFile(root, path, area, outputStream)

    override fun deleteFile(area: WorkspaceStorageArea, path: String, recursive: Boolean): Boolean =
        manager.deleteFile(root, path, recursive, area)

    override fun absoluteFileSize(path: String): Long {
        manager.ensureWorkspace(root)
        return manager.rootfsFileSize(root, path)
    }

    override fun exportAbsoluteFile(path: String, outputStream: OutputStream) {
        manager.ensureWorkspace(root)
        manager.exportRootfsFile(root, path, outputStream)
    }

    // 在 Rootfs 内用 shell 写入: Rootfs 里的绝对路径软链只有 PRoot 内才能正确解析
    override fun writeAbsoluteText(path: String, text: String, overwrite: Boolean): WorkspaceFileEntry {
        val pathArg = path.workspaceShellQuote()
        val result = runCommand(
            action = "Write file",
            command = """
                if [ -e $pathArg ] && [ ${if (overwrite) 0 else 1} = 1 ]; then
                  printf '%s\n' ${"File already exists: $path".workspaceShellQuote()} >&2
                  exit 1
                fi
                if [ -e $pathArg ] && [ ! -f $pathArg ]; then
                  printf '%s\n' ${"Path is not a file: $path".workspaceShellQuote()} >&2
                  exit 1
                fi
                parent=${'$'}(dirname -- $pathArg) || exit 1
                mkdir -p -- "${'$'}parent" || exit 1
                cat > $pathArg || exit 1
                if [ -d $pathArg ]; then entry_type=d; else entry_type=f; fi
                entry_size=${'$'}(stat -c '%s' -- $pathArg) || exit 1
                entry_mtime=${'$'}(stat -c '%Y' -- $pathArg) || exit 1
                printf '%s\0%s\0%s\0%s\0' "${'$'}entry_type" "${'$'}entry_size" "${'$'}entry_mtime" $pathArg
            """.trimIndent(),
            stdin = text.toByteArray(Charsets.UTF_8),
        )
        return result.stdout.parseWorkspaceEntry()
    }

    override fun localFile(area: WorkspaceStorageArea, path: String): File {
        manager.ensureWorkspace(root)
        return manager.resolveFile(root, path, area)
    }

    override fun localAbsoluteFile(path: String): File = manager.resolveRootfsFile(root, path)

    override fun executeCommand(
        command: String,
        cwd: String,
        timeoutMillis: Long,
        stdin: ByteArray?,
    ): WorkspaceCommandResult {
        manager.ensureWorkspace(root)
        return manager.executeCommand(
            root = root,
            command = command,
            cwd = cwd,
            timeoutMillis = timeoutMillis,
            stdin = stdin,
            shellCompatibilityMode = shellCompatibilityMode,
        )
    }

    private fun runCommand(action: String, command: String, stdin: ByteArray?): WorkspaceCommandResult {
        val result = executeCommand(command, cwd = "", WorkspaceManager.DEFAULT_COMMAND_TIMEOUT_MS, stdin)
        if (result.timedOut) {
            error("$action timed out")
        }
        if (result.exitCode != 0) {
            val message = result.stderr.ifBlank { result.stdout }.trim()
            error(if (message.isBlank()) "$action failed with exit code ${result.exitCode}" else message)
        }
        if (result.truncated) {
            error("$action output is too large")
        }
        return result
    }

    private fun String.parseWorkspaceEntry(): WorkspaceFileEntry {
        val fields = split('\u0000').dropLastWhile { it.isEmpty() }
        require(fields.size == 4) { "Invalid file metadata output" }
        val (type, size, mtime, path) = fields
        return WorkspaceFileEntry(
            path = path,
            name = path.trimEnd('/').substringAfterLast('/').ifBlank { "/" },
            isDirectory = type == "d",
            sizeBytes = size.toLongOrNull() ?: error("Invalid file size: $size"),
            updatedAt = (mtime.toLongOrNull() ?: error("Invalid file mtime: $mtime")) * 1_000L,
        )
    }
}

/** 单引号包裹, 供本地 rootfs shell 的命令行使用 */
internal fun String.workspaceShellQuote(): String =
    "'" + replace("'", "'\"'\"'") + "'"
'''

TYPE_BLOCK = r'''/** 工作区类型; 能力表由类型声明, 调用方按能力判断而不是直接比较类型 */
enum class WorkspaceType(val capabilities: WorkspaceCapabilities) {
    /** 本机 PRoot Rootfs */
    LOCAL(
        WorkspaceCapabilities(
            rootfs = true,
            terminal = false,
            localFiles = true,
            fileWriteTools = true,
            backgroundShell = true,
        )
    ),

    /** 通过 SSH 连接的远程机器 */
    SSH(
        WorkspaceCapabilities(
            rootfs = false,
            terminal = false,
            localFiles = false,
            fileWriteTools = false,
            backgroundShell = false,
        )
    ),
}

/** 一种工作区能用哪些功能 */
data class WorkspaceCapabilities(
    /** 需要安装 Rootfs, 挂载了 /skills、/upload、/tool_outputs 等应用目录 */
    val rootfs: Boolean,
    /** 支持交互式终端 (接到终端模块后才会打开) */
    val terminal: Boolean,
    /** 文件在本机; 否则每次访问都要走网络, 也没法交给系统文件选择器 */
    val localFiles: Boolean,
    /** AI 可以用写文件、编辑文件工具直接写入; 否则只能经 shell 修改文件 */
    val fileWriteTools: Boolean,
    /** shell 命令可以在后台运行 */
    val backgroundShell: Boolean,
)

'''

MANAGER_LAYOUT = r'''    /** 工作区在执行环境内的目录约定; 本地工作区文件区固定挂在 /workspace */
    val layout = WorkspaceLayout(
        workspaceDir = ROOTFS_WORKSPACE_DIR,
        writableRoots = listOf(ROOTFS_WORKSPACE_DIR, "/tmp", "/skills"),
    )

'''

MANAGER_BACKEND = r'''    /** 把本地工作区包装成统一后端, 供仓库层与工具层使用 */
    fun backend(root: String, shellCompatibilityMode: Boolean = false): WorkspaceBackend =
        LocalWorkspaceBackend(this, root, shellCompatibilityMode)

'''

MANAGER_SHELL = r'''    /** Rootfs 内使用的 shell: 优先 bash, 没有时 (如 Alpine minirootfs) 回退到 /bin/sh */
    fun rootfsShell(root: String): String {
        val linux = linuxDir(root)
        val bash = File(linux, "bin/bash")
        // Alpine 等发行版的 bin/bash 可能是指向 busybox 的软链, 宿主上解析不到目标也算存在
        return if (bash.isFile || Files.isSymbolicLink(bash.toPath())) "/bin/bash" else "/bin/sh"
    }

'''


def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def write(path, text):
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def patch_once(text, needle, replacement, label, count_expected=1):
    if replacement in text:
        log("ALREADY " + label)
        return text, True
    if text.count(needle) != count_expected:
        log("ANCHOR-MISMATCH " + label + " count=" + str(text.count(needle)))
        return text, False
    return text.replace(needle, replacement, 1), True


def main():
    diag = []
    ok = True

    # 1) 新文件
    backend_path = "workspace/src/main/java/me/rerere/workspace/WorkspaceBackend.kt"
    local_path = "workspace/src/main/java/me/rerere/workspace/LocalWorkspaceBackend.kt"
    if os.path.exists(backend_path):
        diag.append("WorkspaceBackend: exists")
    else:
        write(backend_path, BACKEND)
        diag.append("WorkspaceBackend: wrote " + str(len(BACKEND)))
    if os.path.exists(local_path):
        diag.append("LocalWorkspaceBackend: exists")
    else:
        write(local_path, LOCAL)
        diag.append("LocalWorkspaceBackend: wrote " + str(len(LOCAL)))
    if balance(BACKEND) != (BACKEND.count("("), BACKEND.count(")")):
        ok = False
    if balance(LOCAL)[0] != balance(LOCAL)[1] - LOCAL.count(")") + balance(LOCAL)[1]:
        pass

    # 2) Workspace.kt 增加类型与能力
    ws_path = "workspace/src/main/java/me/rerere/workspace/Workspace.kt"
    ws = read(ws_path)
    if "enum class WorkspaceType" in ws:
        diag.append("Workspace.kt: already")
    else:
        anchor = "enum class WorkspaceShellStatus {"
        if ws.count(anchor) != 1:
            diag.append("Workspace.kt: ANCHOR-MISMATCH " + str(ws.count(anchor)))
            ok = False
        else:
            ws = ws.replace(anchor, TYPE_BLOCK + anchor, 1)
            write(ws_path, ws)
            diag.append("Workspace.kt: type+capabilities")

    # 3) WorkspaceManager.kt 暴露 layout/backend/rootfsShell, 并公开 resolveRootfsFile
    mgr_path = "workspace/src/main/java/me/rerere/workspace/WorkspaceManager.kt"
    mgr = read(mgr_path)
    changed = []
    anchor_layout = "    // 按 target 长度降序, 保证 /a/b 优先于 /a 匹配\n    private val sortedBindMounts = bindMounts.sortedByDescending { it.target.trimEnd('/').length }"
    if "val layout = WorkspaceLayout(" in mgr:
        changed.append("layout:already")
    elif mgr.count(anchor_layout) == 1:
        mgr = mgr.replace(anchor_layout, MANAGER_LAYOUT + anchor_layout, 1)
        changed.append("layout:ok")
    else:
        changed.append("layout:MISS")
        ok = False

    anchor_init = "    init {\n        baseDir.mkdirs()\n    }"
    if "fun backend(root: String, shellCompatibilityMode: Boolean = false)" in mgr:
        changed.append("backend:already")
    elif mgr.count(anchor_init) == 1:
        mgr = mgr.replace(anchor_init, anchor_init + "\n" + MANAGER_BACKEND, 1)
        changed.append("backend:ok")
    else:
        changed.append("backend:MISS")
        ok = False

    anchor_delete = "    fun deleteWorkspace(root: String): Boolean = synchronized(backgroundLifecycleLock) {"
    if "fun rootfsShell(root: String): String" in mgr:
        changed.append("shell:already")
    elif mgr.count(anchor_delete) == 1:
        mgr = mgr.replace(anchor_delete, MANAGER_SHELL + anchor_delete, 1)
        changed.append("shell:ok")
    else:
        changed.append("shell:MISS")
        ok = False

    old_resolve = "    private fun resolveRootfsFile(root: String, path: String): File {"
    if "    fun resolveRootfsFile(root: String, path: String): File {" in mgr:
        changed.append("resolve:already")
    elif mgr.count(old_resolve) == 1:
        mgr = mgr.replace(old_resolve, "    fun resolveRootfsFile(root: String, path: String): File {", 1)
        changed.append("resolve:ok")
    else:
        changed.append("resolve:MISS")
        ok = False

    write(mgr_path, mgr)
    diag.append("Manager: " + ",".join(changed))

    # 括号自检: 只统计新增块, 保证自身配平
    for name, block in (("BACKEND", BACKEND), ("LOCAL", LOCAL), ("TYPE", TYPE_BLOCK),
                        ("LAYOUT", MANAGER_LAYOUT), ("BACKEND_FN", MANAGER_BACKEND), ("SHELL_FN", MANAGER_SHELL)):
        left = block.count("(")
        right = block.count(")")
        if left != right:
            diag.append(name + ":UNBALANCED(" + str(left) + "/" + str(right) + ")")
            ok = False

    diag.append("RESULT:" + ("OK" if ok else "FAIL"))
    with open(os.path.join(ROOT, DIAG), "w", encoding="utf-8") as f:
        f.write("\n".join(diag) + "\n")
    log("diag " + DIAG + " -> " + " | ".join(diag))
    if not ok:
        # 不用 exit(1): 合组构建时单个批失败不应阻断后面的批, 但要留下 ::error 证据
        print("::error title=batch346::" + " | ".join(diag))


main()

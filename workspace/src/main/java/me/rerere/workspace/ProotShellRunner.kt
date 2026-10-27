package me.rerere.workspace

import java.io.File

data class WorkspaceBindMount(
    val source: File,
    val target: String,
) {
    init {
        require(target.startsWith("/")) { "Bind mount target must be absolute: " + target }
    }
}

/**
 * rhWsProot308 / rhWsFix312: PRoot 执行器。
 *
 * exec 入口不是 rootfs 里的解释器，而是经 /rh-libs 映射回宿主 nativeLibraryDir 的静态
 * busybox —— Android 10+（untrusted_app 禁止 exec 应用数据目录文件）下唯一稳定可执行的
 * 应用可控位置。详见 WorkspaceBusybox 类注释。
 *
 * guest 内 PATH 首项是 /usr/rh-bin（applet 软链农场），所以 ls/sed/awk/grep/stat/mkdir
 * 全部命中同一个可执行文件。直接写 rootfs 内的绝对路径（例如 bin 目录下的 ls）仍会被
 * SELinux 拒（设计使然，不是缺陷）。
 */
class ProotShellRunner(
    val nativeLibraryDir: File,
    private val patcher: RootfsPatcher = RootfsPatcher(),
) : WorkspaceShellRunner {

    override fun execute(context: WorkspaceShellContext): WorkspaceCommandResult {
        val problem = preflight(context)
        if (problem != null) {
            return WorkspaceCommandResult(exitCode = 127, stdout = "", stderr = problem)
        }
        if (context.shellCompatibilityMode) {
            return compatibilityProcess(context).start().readResult(context.timeoutMillis, context.stdin)
        }
        context.tempDir.mkdirs()
        patcher.patch(context.linuxDir)
        return prootProcess(context).start().readResult(context.timeoutMillis, context.stdin)
    }

    override fun start(context: WorkspaceShellContext): Process {
        val problem = preflight(context)
        if (problem != null) throw IllegalStateException(problem)
        if (context.shellCompatibilityMode) return compatibilityProcess(context).start()
        context.tempDir.mkdirs()
        patcher.patch(context.linuxDir)
        return prootProcess(context).start()
    }

    /** 返回 null 表示可执行；否则是直接展示给用户/模型的错误文案 */
    private fun preflight(context: WorkspaceShellContext): String? {
        if (context.shellCompatibilityMode) return null
        if (!context.linuxDir.isDirectory) {
            return "Rootfs is not installed: " + context.linuxDir.absolutePath
        }
        if (!WorkspaceBusybox.isReady(context.linuxDir, nativeLibraryDir)) {
            // rhWsFix312: 行尾 + 而不是行首 +，否则 Kotlin 会把它当一元 plus
            return "rootfs 未就绪：缺少 /usr/rh-bin busybox 农场或 libbusybox.so。" +
                "请在 扩展 → 工作区 → 详情 里重新安装 rootfs。"
        }
        val proot = File(nativeLibraryDir, PROOT_EXEC)
        if (!proot.isFile) {
            return "proot executable not found: " + proot.absolutePath
        }
        val loader = File(nativeLibraryDir, PROOT_LOADER)
        if (!loader.isFile) {
            return "proot loader not found: " + loader.absolutePath
        }
        return null
    }

    /** 降级路径：完全不经 proot，用系统 shell 直接跑（无 /workspace 与 bind mount） */
    private fun compatibilityProcess(context: WorkspaceShellContext): ProcessBuilder {
        val builder = ProcessBuilder(HOST_SHELL, "-c", context.command)
            .directory(context.workingDir)
            .redirectErrorStream(false)
        val env = builder.environment()
        env["PATH"] = HOST_PATH
        env["HOME"] = context.filesDir.absolutePath
        env["TMPDIR"] = context.tempDir.absolutePath
        env["TERM"] = "dumb"
        env["LANG"] = "C.UTF-8"
        env["LC_ALL"] = "C.UTF-8"
        env["CI"] = "true"
        env["NO_COLOR"] = "1"
        env["PAGER"] = "cat"
        return builder
    }

    private fun prootProcess(context: WorkspaceShellContext): ProcessBuilder {
        val proot = File(nativeLibraryDir, PROOT_EXEC)
        val loader = File(nativeLibraryDir, PROOT_LOADER)
        val builder = ProcessBuilder(buildArgv(context, proot))
            .directory(context.filesDir)
            .redirectErrorStream(false)
        val env = builder.environment()
        // 只保留 bionic/平台需要的宿主变量，其余清空 —— 否则 HOME/ANDROID_* 会直接泄进 guest
        val keep = listOf("ANDROID_ROOT", "ANDROID_DATA", "ANDROID_STORAGE", "EXTERNAL_STORAGE")
        val saved = HashMap<String, String>()
        for (key in keep) {
            val value = env[key]
            if (value != null) saved[key] = value
        }
        env.clear()
        env.putAll(saved)
        env["PATH"] = GUEST_PATH
        env["HOME"] = "/root"
        env["TERM"] = "dumb"
        env["LANG"] = "C.UTF-8"
        env["LC_ALL"] = "C.UTF-8"
        env["TMPDIR"] = "/tmp"
        env["CI"] = "true"
        env["NO_COLOR"] = "1"
        env["PAGER"] = "cat"
        // proot 自身的运行时依赖（同目录 libtalloc / libandroid-shmem）靠它找
        env["LD_LIBRARY_PATH"] = nativeLibraryDir.absolutePath
        env["PROOT_TMP_DIR"] = context.tempDir.absolutePath
        env["PROOT_LOADER"] = loader.absolutePath
        // 部分 ROM 的 seccomp 策略会拦 ptrace；关掉 seccomp 加速换取可运行
        env["PROOT_NO_SECCOMP"] = "1"
        return builder
    }

    private fun buildArgv(context: WorkspaceShellContext, proot: File): List<String> {
        val argv = mutableListOf(
            proot.absolutePath,
            "--root-id",
            "--link2symlink",
            "-r", context.linuxDir.absolutePath,
            "-b", nativeLibraryDir.absolutePath + ":" + WorkspaceBusybox.RH_LIBS,
            "-b", context.filesDir.absolutePath + ":" + WorkspaceManager.ROOTFS_WORKSPACE_DIR,
        )
        for (mount in context.bindMounts) {
            if (mount.source.exists()) {
                argv += "-b"
                argv += mount.source.absolutePath + ":" + mount.target.trimEnd('/')
            }
        }
        for (path in WorkspaceManager.KERNEL_FS_MOUNTS) {
            if (File(path).exists()) {
                argv += "-b"
                argv += path
            }
        }
        argv += "-w"
        argv += context.prootCwd()
        // exec 目标是农场里的 sh（软链 -> /rh-libs/libbusybox.so），不是 rootfs 的 bin/sh。
        // 命令作为单个 argv 交给 sh -c，全程不经字符串拼接。
        argv += WorkspaceBusybox.APPLET_PATH + "/sh"
        argv += "-c"
        argv += context.command
        return argv
    }

    private fun WorkspaceShellContext.prootCwd(): String {
        val normalized = cwd.trim().trim('/')
        return if (normalized.isBlank()) {
            WorkspaceManager.ROOTFS_WORKSPACE_DIR
        } else {
            WorkspaceManager.ROOTFS_WORKSPACE_DIR + "/" + normalized
        }
    }

    private companion object {
        private const val PROOT_EXEC = "libproot_exec.so"
        private const val PROOT_LOADER = "libproot_loader.so"
        private const val HOST_SHELL = "/system/bin/sh"
        private const val HOST_PATH = "/system/bin:/system/xbin"
        private const val GUEST_PATH =
            "/usr/rh-bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
    }
}

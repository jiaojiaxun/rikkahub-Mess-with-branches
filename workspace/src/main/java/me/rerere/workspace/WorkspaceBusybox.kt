package me.rerere.workspace

import java.io.File
import java.io.IOException
import java.nio.file.Files
import java.nio.file.Paths
import java.util.concurrent.TimeUnit

/**
 * rhWsBusybox306 / rhWsFix312: 工作区 Linux 引擎的“可执行入口”。
 *
 * 为什么需要它（Android 10+ 的硬约束，不是设计偏好）：
 * targetSdk >= 29 的 untrusted_app 域被 SELinux 禁止 exec() 应用数据目录
 * （filesDir / getExternalFilesDir）里的文件。rootfs 解包在 filesDir 下，所以
 * Alpine 自带的 /bin 下的可执行文件（musl 动态链接）在 Android 10+ 上 exec 一律
 * 被拒 —— 这就是“rootfs 装好了但 workspace_shell 全是 127 / Permission denied”的根因。
 *
 * 唯一稳定可 exec 的应用可控位置是 APK 的 nativeLibraryDir（apk_data_file，
 * 安装器解出的 jniLibs，且 app 已开 useLegacyPackaging=true 所以是真实文件）。因此：
 *  1. shell 入口改用 <nativeLib>/libbusybox.so（静态 ELF，无 PT_INTERP）；
 *  2. proot 用 -b <nativeLib>:/rh-libs 把它映射进命名空间，guest 内路径
 *     /rh-libs/libbusybox.so 解析回宿主 nativeLibraryDir，内核按 apk_data_file 放行；
 *  3. rootfs 内 usr/rh-bin/<applet> -> /rh-libs/libbusybox.so 的软链农场让
 *     ls/sed/awk/grep/stat/mkdir 等通过 PATH 命中同一个可执行文件；
 *  4. bin/sh 与 bin/busybox 也指向 /rh-libs/libbusybox.so，这样 #!/bin/sh
 *     的脚本（proot 把软链解析到宿主 nativeLibraryDir）同样可执行。
 *
 * 注意：软链目标必须是命名空间内的路径 /rh-libs/libbusybox.so，不能写宿主绝对
 * 路径 —— 宿主路径在 proot 根内不存在，exec 会 ENOENT。
 *
 * 本文件里切忌在块注释中出现斜杠加星号的字面组合：Kotlin 的块注释支持嵌套，
 * 多写一层就会变成 Unclosed comment（run#544 就是这么挂的）。
 */
object WorkspaceBusybox {

    /** jniLibs 里的文件名（Android 安装器只会解出 lib 开头的 so） */
    const val LIB_NAME = "libbusybox.so"

    /** proot 内绑定点：宿主 nativeLibraryDir 在命名空间里的落点 */
    const val RH_LIBS = "/rh-libs"

    /** 命名空间内的 busybox 本体路径（映射到宿主 nativeLibraryDir/libbusybox.so） */
    const val EXEC_PATH = RH_LIBS + "/" + LIB_NAME

    /** rootfs 内 applet 软链农场目录（相对 rootfs 根） */
    const val APPLET_DIR = "usr/rh-bin"

    /** 农场目录在命名空间内的绝对路径，同时也是 PATH 首项 */
    const val APPLET_PATH = "/usr/rh-bin"

    private val APPLET_NAME = Regex("[A-Za-z0-9_-]+")

    fun binary(nativeLibraryDir: File): File = File(nativeLibraryDir, LIB_NAME)

    fun hasBinary(nativeLibraryDir: File): Boolean = binary(nativeLibraryDir).isFile

    /** 农场是否已建立（目录存在且非空） */
    fun hasFarm(linuxDir: File): Boolean {
        val dir = File(linuxDir, APPLET_DIR)
        if (!dir.isDirectory) return false
        val children = dir.list()
        return children != null && children.isNotEmpty()
    }

    /**
     * rootfs 是否可执行：bin/sh 存在（真实文件或软链）且 applet 农场已建。
     * 这里必须用 Files.isSymbolicLink 兜底：安装后 bin/sh 是指向
     * /rh-libs/libbusybox.so 的软链，宿主上该目标不存在，File.isFile 会返回 false。
     */
    fun isReady(linuxDir: File, nativeLibraryDir: File): Boolean {
        val sh = File(linuxDir, "bin/sh")
        val shPresent = sh.isFile || Files.isSymbolicLink(sh.toPath())
        return shPresent && hasFarm(linuxDir) && hasBinary(nativeLibraryDir)
    }

    /**
     * 枚举 busybox 内建 applet。直接在主进程里跑宿主 nativeLibraryDir 的
     * libbusybox.so --list（静态 ELF，不需要 proot，也不受 SELinux exec 限制影响，
     * 因为它自己就在 nativeLibraryDir 里）。
     */
    fun listApplets(nativeLibraryDir: File, timeoutMillis: Long = 15_000L): List<String> {
        val exe = binary(nativeLibraryDir)
        require(exe.isFile) {
            "busybox 二进制缺失: " + exe.absolutePath + "（请安装带 libbusybox.so 的 APK 后重新安装 rootfs）"
        }
        if (!exe.canExecute()) {
            require(exe.setExecutable(true)) { "busybox 二进制不可执行且无法授权: " + exe.absolutePath }
        }
        val process = ProcessBuilder(exe.absolutePath, "--list")
            .redirectErrorStream(true)
            .start()
        try {
            if (!process.waitFor(timeoutMillis, TimeUnit.MILLISECONDS)) {
                process.destroyForcibly()
                throw IllegalStateException("busybox --list 超时（" + timeoutMillis + "ms）")
            }
            val text = process.inputStream.bufferedReader().use { it.readText() }
            val exit = process.exitValue()
            if (exit != 0) {
                throw IllegalStateException("busybox --list 退出码 " + exit + ": " + text.take(400))
            }
            val names = text.split('\n')
                .map { it.trim() }
                .filter { it.isNotEmpty() && APPLET_NAME.matches(it) }
                .distinct()
            if (names.isEmpty()) throw IllegalStateException("busybox --list 返回空列表")
            return names
        } finally {
            if (process.isAlive) process.destroyForcibly()
        }
    }

    /**
     * 建立/刷新 applet 软链农场，并把 bin/sh、bin/busybox 指到 /rh-libs/libbusybox.so。
     * 幂等：已指向正确目标的软链跳过；错误目标或真实文件先挪到 <name>.rh-orig 再建。
     */
    fun ensureFarm(
        linuxDir: File,
        nativeLibraryDir: File,
        onProgress: (done: Int, total: Int) -> Unit = { _, _ -> },
    ): Int {
        val applets = listApplets(nativeLibraryDir)
        val farm = File(linuxDir, APPLET_DIR)
        farm.mkdirs()
        var done = 0
        for (name in applets) {
            if (Thread.currentThread().isInterrupted) {
                throw InterruptedException("Rootfs install cancelled")
            }
            link(farm, name, EXEC_PATH)
            done++
            if (done % 200 == 0) onProgress(done, applets.size)
        }
        val binDir = File(linuxDir, "bin")
        binDir.mkdirs()
        link(binDir, "sh", EXEC_PATH)
        link(binDir, "busybox", EXEC_PATH)
        File(linuxDir, "tmp").mkdirs()
        File(linuxDir, "usr/bin").mkdirs()
        // rhWsBind311: proot 的 -b 需要 guest 挂载点已存在，否则部分版本直接启动失败
        File(linuxDir, "rh-libs").mkdirs()
        File(linuxDir, "workspace").mkdirs()
        onProgress(applets.size, applets.size)
        if (!hasFarm(linuxDir)) {
            throw IllegalStateException("busybox applet 农场建立失败: " + File(linuxDir, APPLET_DIR).absolutePath)
        }
        return done
    }

    private fun link(dir: File, name: String, target: String) {
        val path = File(dir, name)
        try {
            if (Files.isSymbolicLink(path.toPath())) {
                val current = Files.readSymbolicLink(path.toPath()).toString()
                if (current == target) return
                Files.delete(path.toPath())
            } else if (path.exists()) {
                val backup = File(dir, name + ".rh-orig")
                if (backup.exists()) backup.deleteRecursively()
                if (!path.renameTo(backup) && !path.deleteRecursively()) {
                    println("WorkspaceBusybox: cannot move existing " + path.absolutePath + " aside")
                    return
                }
            }
            Files.createSymbolicLink(path.toPath(), Paths.get(target))
        } catch (e: IOException) {
            println("WorkspaceBusybox: symlink failed for " + name + ": " + e.message)
        } catch (e: UnsupportedOperationException) {
            println("WorkspaceBusybox: filesystem does not support symlink for " + name + ": " + e.message)
        }
    }
}

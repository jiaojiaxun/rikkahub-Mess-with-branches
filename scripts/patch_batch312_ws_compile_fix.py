#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch312: 修 run#544 的两个真实编译错误（已从 check-run annotations 逐行核实）

【钳子级定位】
1. WorkspaceBusybox.kt:167 Syntax error: Unclosed comment.
   根因: KDoc 里写了 "/bin/*（musl 动态链接）" —— Kotlin 支持嵌套块注释,
   这串里的 /* 在注释内部又开了一层, 之后所有 */ 只能关一层, 到文件尾深度仍为 1。
   （batch310 只查括号与符号, 不查块注释深度, 所以没拦住 —— 本批把这项加入自检）
2. ProotShellRunner.kt:60 Unresolved reference 'unaryPlus' for operator '+' on receiver 'String'.
   根因: 多行字符串拼接把 + 写在了【下一行开头】:
       return "..."
           + "..."
   Kotlin 把行首 + 解析为一元 plus 新表达式, 而不是上一行的二元运算。
   修法: + 放到上一行末尾。

其余 4 条（WorkspaceBusybox Unresolved x3 / RootfsInstaller 的 done·total 类型未知）
都是这两个文件解析失败后的连锁, 不需单独处理。

【本批做法】整文件覆盖两个文件（在 306/308 之后执行, 且把 batch311 的占位目录一并包含,
不依赖前序 patch 的产物）, 并在写盘前做三道静态断言:
  A. Kotlin 块注释嵌套深度 == 0（新增, 防复发）
  B. 不存在“缩进 + 行首 +”
  C. 全量括号 balance == 0

五查: import 与 306/308 一致无新增 / 整文件覆盖无锤点依赖 / 全为成员声明 /
balance + 注释深度双断言 / execute·start 与外部调用签名不变。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhWsFix312'
BB = 'workspace/src/main/java/me/rerere/workspace/WorkspaceBusybox.kt'
PR = 'workspace/src/main/java/me/rerere/workspace/ProotShellRunner.kt'
DIAG = 'ci_diag_batch312.txt'

BUSYBOX = r'''package me.rerere.workspace

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
'''

PROOT = r'''package me.rerere.workspace

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
'''

report = []


def note(m):
    report.append(str(m)[:700])


def balance(t):
    return (t.count('(') - t.count(')')
            + t.count('{') - t.count('}')
            + t.count('[') - t.count(']'))


def comment_depth(text):
    depth = 0
    i = 0
    n = len(text)
    while i < n - 1:
        two = text[i:i + 2]
        if two == '/*':
            depth += 1
            i += 2
            continue
        if two == '*/' and depth > 0:
            depth -= 1
            i += 2
            continue
        i += 1
    return depth


def leading_plus(text):
    hits = []
    for idx, ln in enumerate(text.split(NL)):
        s = ln.lstrip()
        if s.startswith('+ ') and not s.startswith('+= '):
            hits.append(str(idx + 1))
    return hits


def write_checked(rel, src, label):
    if comment_depth(src) != 0:
        note('FATAL ' + label + ' comment depth=' + str(comment_depth(src)))
        return False
    if balance(src) != 0:
        note('FATAL ' + label + ' balance=' + str(balance(src)))
        return False
    lp = leading_plus(src)
    if lp:
        note('FATAL ' + label + ' leading plus at lines ' + ','.join(lp))
        return False
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(src, encoding='utf-8')
    text = p.read_text(encoding='utf-8')
    if comment_depth(text) != 0 or balance(text) != 0:
        note('POSTCHECK FAILED ' + label)
        return False
    note(label + ' written chars=' + str(len(src)) + ' comment_depth=0 balance=0')
    return True


def main():
    text = ''
    p = ROOT / BB
    if p.exists():
        try:
            text = p.read_text(encoding='utf-8')
        except Exception:
            text = ''
    if MARK not in text:
        write_checked(BB, BUSYBOX, 'WorkspaceBusybox.kt')
    else:
        note('WorkspaceBusybox.kt already fixed')

    text = ''
    p = ROOT / PR
    if p.exists():
        try:
            text = p.read_text(encoding='utf-8')
        except Exception:
            text = ''
    if MARK not in text:
        write_checked(PR, PROOT, 'ProotShellRunner.kt')
    else:
        note('ProotShellRunner.kt already fixed')

    # 全模块回归：任何 .kt 的块注释深度都必须为 0
    base = ROOT / 'workspace/src/main/java/me/rerere/workspace'
    bad = []
    if base.is_dir():
        for f in sorted(base.glob('*.kt')):
            try:
                t = f.read_text(encoding='utf-8')
            except Exception:
                continue
            if comment_depth(t) != 0:
                bad.append(f.name + '(depth=' + str(comment_depth(t)) + ')')
    if bad:
        note('MODULE comment-depth issues: ' + ','.join(bad))
    else:
        note('module-wide comment depth clean')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:
        print('::error::batch312 diag write failed ' + str(exc)[:200])


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        note('EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
    write_diag()
    for line in report:
        print('::error::batch312 ' + str(line)[:700])
    print('::error::batch312 END lines=' + str(len(report)))
    sys.exit(0)

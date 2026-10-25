#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch308: ProotShellRunner 整文件重写 — exec 入口改到 nativeLibraryDir 的静态 busybox

为什么必须重写:
  现有 argv 尾部为 /usr/bin/env -i ... /bin/bash -l -c( batch252 后为 pickRootfsShell )
  两个目标都在 rootfs 里 = filesDir 下 = app_data_file。Android 10+ untrusted_app
  禁止 exec 应用数据目录文件(W^X), 且 Alpine minirootfs 没有 /bin/bash
  => 每条命令 ENOENT/EACCES, workspace_shell 全线 127。

新 argv: proot --root-id --link2symlink -r linuxDir
  -b <nativeLib>:/rh-libs      (唯一可 exec 的应用可控位置)
  -b files:/workspace -b mounts... -b /proc /dev /sys
  -w <cwd>  /usr/rh-bin/sh -c <command>
/usr/rh-bin/sh 是 rootfs 内指向 /rh-libs/libbusybox.so 的软链, proot 解析回
宿主 nativeLibraryDir, 内核按 apk_data_file 放行; argv[0] basename 仍为 sh。

同时修掉:
1. 移除 --kill-on-exit(非 termux 补丁版 proot 不支持 => 启动直接失败)。
2. 环境变量 clear 后白名单重建, 保留 ANDROID_*/EXTERNAL_STORAGE,
   显式设 LD_LIBRARY_PATH=nativeLibraryDir(proot 自身的动态依赖靠它找)。
3. shellCompatibilityMode 改为真正的降级路径(/system/bin/sh, 不经 proot),
   之前只是设一个 PROOT_NO_SECCOMP 仍走 proot, ptrace 被禁的 ROM 照样不能启动。

保留: Process.readResult / WorkspaceBindMount / execute/start 签名。
五查: import 仅 File / 整文件覆盖不依赖链上前序 / 新函数均 private 成员 /
全量 balance 断言 / 接口签名不变。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhWsProot308'
F = 'workspace/src/main/java/me/rerere/workspace/ProotShellRunner.kt'
DIAG = 'ci_diag_batch308.txt'

SRC = r'''package me.rerere.workspace

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
 * rhWsProot308: PRoot 执行器。
 *
 * exec 入口不是 rootfs 里的解释器，而是经 /rh-libs 映射回宿主 nativeLibraryDir 的静态
 * busybox —— Android 10+（untrusted_app 禁止 exec 应用数据目录文件）下唯一稳定可执行的
 * 应用可控位置。详见 WorkspaceBusybox 类注释。
 *
 * guest 内 PATH 首项是 /usr/rh-bin（applet 软链农场），所以 ls/sed/awk/grep/stat/mkdir
 * 全部命中同一个可执行文件。直接写 /bin/ls 这类 rootfs 绝对路径仍会被 SELinux 拒
 * （设计使然，不是缺陷）。
 */
class ProotShellRunner(
    private val nativeLibraryDir: File,
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
            return "rootfs 未就绪：缺少 /usr/rh-bin busybox 农场或 libbusybox.so。"
                + "请在 扩展 → 工作区 → 详情 里重新安装 rootfs。"
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
        // exec 目标是农场里的 sh（软链 -> /rh-libs/libbusybox.so），不是 rootfs 的 /bin/sh。
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


def apply():
    p = ROOT / F
    bal = balance(SRC)
    if bal != 0:
        note('FATAL source balance=' + str(bal))
        return
    if p.exists():
        try:
            if MARK in p.read_text(encoding='utf-8'):
                note('already applied')
                return
        except Exception:
            pass
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(SRC, encoding='utf-8')
    text = p.read_text(encoding='utf-8')
    checks = [
        'class ProotShellRunner(',
        'data class WorkspaceBindMount(',
        'WorkspaceBusybox.APPLET_PATH + "/sh"',
        'WorkspaceBusybox.RH_LIBS',
        'override fun execute(context: WorkspaceShellContext): WorkspaceCommandResult',
        'override fun start(context: WorkspaceShellContext): Process',
        MARK,
    ]
    for need in checks:
        if need not in text:
            note('SELFCHECK missing ' + need)
    for bad in ['--kill-on-exit', '/bin/bash', 'pickRootfsShell']:
        if bad in text:
            note('SELFCHECK still present: ' + bad)
    note('written chars=' + str(len(SRC)) + ' balance=' + str(balance(text)))


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:
        print('::error::batch308 diag write failed ' + str(exc)[:200])


if __name__ == '__main__':
    try:
        apply()
    except Exception as exc:
        note('EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
    write_diag()
    for line in report:
        print('::error::batch308 ' + str(line)[:700])
    print('::error::batch308 END lines=' + str(len(report)))
    sys.exit(0)

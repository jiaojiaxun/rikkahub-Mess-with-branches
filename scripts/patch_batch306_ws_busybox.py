#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch306: 工作区 Linux 引擎真正可用的第一块 —— 静态 busybox 落 jniLibs + applet 农场模块

【为什么必须这么做 —— 已逐点核实的事实, 不是猜测】
1. Android 10+ (API 29+) 的 untrusted_app SELinux 域禁止 exec() 应用数据目录
   (filesDir / getExternalFilesDir) 里的文件 (W^X)。targetSdk=37, 这条硬性生效。
2. 现有 ProotShellRunner 的 exec 目标是 rootfs 内的解释器:
      /usr/bin/env -i ... /bin/bash -l -c   (batch252 后变成 pickRootfsShell -> /bin/bash 或 /bin/sh)
   rootfs 解包在 filesDir/workspaces/<root>/linux 下 => 目标落在 app_data_file。
   同时 Alpine minirootfs 根本没有 /bin/bash (只有 busybox 的 sh)。
   => 每条命令要么 ENOENT, 要么被 SELinux 拒绝, workspace_shell 全线不可用。
3. 唯一稳定可 exec 的应用可控位置是 nativeLibraryDir (apk_data_file, 由安装器解出)。
   app/build.gradle.kts 已设 packaging.jniLibs.useLegacyPackaging = true,
   所以 jniLibs 会解压成真实文件, 可直接 exec。

【本批做什么】
A. 下载 meefik 的静态 busybox (无 PT_INTERP) 到 workspace/src/main/jniLibs/arm64-v8a/libbusybox.so。
   硬校验: ELF64 + e_machine==183 (EM_AARCH64) + 无 PT_INTERP + e_type 合法。
   校验失败的候选直接丢弃, 绝不把错文件塞进构建。
B. 新增 WorkspaceBusybox.kt:
   - EXEC_PATH = /rh-libs/libbusybox.so (命名空间内路径)
   - listApplets(): 主进程直接跑 <nativeLib>/libbusybox.so --list 枚举 applet
   - ensureFarm(): 在 rootfs 内建 usr/rh-bin/<applet> -> /rh-libs/libbusybox.so 软链农场,
     并把 bin/sh、bin/busybox 也指向同一目标 (让 #!/bin/sh 脚本可执行)
   - hasFarm()/isReady()/hasBinary() 供 ProotShellRunner 与 WorkspaceManager 的 READY 判定

【确定性细节】
- 软链目标必须是命名空间内路径 /rh-libs/libbusybox.so; 宿主绝对路径在 proot 根内不存在。
- isReady 用 Files.isSymbolicLink 兜底: bin/sh 安装后是软链, 目标在宿主不存在,
  File.isFile 会返回 false —— 若只认 isFile, 装好立刻被判 BROKEN。
- 幂等 marker rhWsBusybox306; 重复执行只输出 already applied。

五查:
1 import: Kotlin 侧 File/IOException/Files/Paths/TimeUnit 全部显式 import
2 同文件冲突: WorkspaceBusybox.kt 是全新文件, 无历史批次; jniLibs 只新增 libbusybox.so,
  batch133/219 写的是 libproot_exec/libproot_loader, 文件名不相交
3 作用域: object WorkspaceBusybox 顶层, 全部成员 public, 供 ProotShellRunner/WorkspaceManager/RootfsInstaller 调用
4 括号配对: 写入前做全量 balance 断言, 不平衡则不落盘
5 函数签名: 新增文件, 不改任何既有签名
'''
import hashlib
import io
import struct
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhWsBusybox306'
DEST_DIR = 'workspace/src/main/jniLibs/arm64-v8a'
LIB_NAME = 'libbusybox.so'
KOTLIN = 'workspace/src/main/java/me/rerere/workspace/WorkspaceBusybox.kt'
DIAG = 'ci_diag_batch306.txt'

CANDIDATES = [
    (
        'https://github.com/meefik/busybox/releases/download/1.34.1/busybox-v1_34_1.zip',
        ('arm64/bin/busybox', 'arm64-v8a/bin/busybox', 'bin/arm64/busybox'),
    ),
    (
        'https://github.com/meefik/busybox/releases/download/1.35.0/busybox-v1_35_0.zip',
        ('arm64/bin/busybox', 'arm64-v8a/bin/busybox'),
    ),
    (
        'https://github.com/meefik/busybox/releases/download/1.36.1/busybox-v1_36_1.zip',
        ('arm64/bin/busybox', 'arm64-v8a/bin/busybox'),
    ),
]

report = []


def note(msg):
    report.append(str(msg)[:700])


def http_get(url, timeout=90):
    req = urllib.request.Request(url, headers={'User-Agent': 'rikkahub-batch306/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def elf_problem(data):
    '''None = 合法 aarch64 静态 ELF; 否则返回问题描述。'''
    if len(data) < 128:
        return 'too small (' + str(len(data)) + ' bytes)'
    if data[0:4] != bytes([127, 69, 76, 70]):
        return 'not ELF'
    ei_class = data[4]
    if ei_class != 2:
        return 'not ELF64 (ei_class=' + str(ei_class) + ')'
    ei_data = data[5]
    if ei_data != 1:
        return 'not little-endian (ei_data=' + str(ei_data) + ')'
    e_type = struct.unpack_from('<H', data, 16)[0]
    if e_type not in (2, 3):
        return 'unexpected e_type=' + str(e_type)
    e_machine = struct.unpack_from('<H', data, 18)[0]
    if e_machine != 183:
        return 'not EM_AARCH64 (e_machine=' + str(e_machine) + ')'
    e_phoff = struct.unpack_from('<Q', data, 32)[0]
    e_phentsize = struct.unpack_from('<H', data, 54)[0]
    e_phnum = struct.unpack_from('<H', data, 56)[0]
    if e_phoff <= 0 or e_phentsize < 32 or e_phnum <= 0:
        return 'bad program header table'
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        if off + 16 > len(data):
            return 'program header out of range'
        p_type = struct.unpack_from('<I', data, off)[0]
        if p_type == 3:
            return 'PT_INTERP present (dynamic, not static)'
    return None


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


KOTLIN_SRC = r'''package me.rerere.workspace

import java.io.File
import java.io.IOException
import java.nio.file.Files
import java.nio.file.Paths
import java.util.concurrent.TimeUnit

/**
 * rhWsBusybox306: 工作区 Linux 引擎的"可执行入口"。
 *
 * 为什么需要它（Android 10+ 的硬约束，不是设计偏好）：
 * targetSdk >= 29 的 untrusted_app 域被 SELinux 禁止 exec() 应用数据目录
 * （filesDir / getExternalFilesDir）里的文件。rootfs 解包在 filesDir 下，所以
 * Alpine 自带的 /bin/*（musl 动态链接）在 Android 10+ 上 exec 一律被拒 ——
 * 这就是"rootfs 装好了但 workspace_shell 全是 127 / Permission denied"的根因。
 *
 * 唯一稳定可 exec 的应用可控位置是 APK 的 nativeLibraryDir（apk_data_file，
 * 安装器解出的 jniLibs，且 app 已开 useLegacyPackaging=true 所以是真实文件）。因此：
 *  1. shell 入口改用 <nativeLib>/libbusybox.so（静态 ELF，无 PT_INTERP）；
 *  2. proot 用 -b <nativeLib>:/rh-libs 把它映射进命名空间，guest 内路径
 *     /rh-libs/libbusybox.so 解析回宿主 nativeLibraryDir，内核按 apk_data_file 放行；
 *  3. rootfs 内 usr/rh-bin/<applet> -> /rh-libs/libbusybox.so 的软链农场让
 *     ls/sed/awk/grep/stat/mkdir/... 通过 PATH 命中同一个可执行文件；
 *  4. bin/sh 与 bin/busybox 也指向 /rh-libs/libbusybox.so，这样 #!/bin/sh
 *     的脚本（proot 把软链解析到宿主 nativeLibraryDir）同样可执行。
 *
 * 注意：软链目标必须是命名空间内的路径 /rh-libs/libbusybox.so，不能写宿主绝对
 * 路径 —— 宿主路径在 proot 根内不存在，exec 会 ENOENT。
 */
object WorkspaceBusybox {

    /** jniLibs 里的文件名（Android 安装器只会解出 lib*.so） */
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


def write_kotlin():
    kt = ROOT / KOTLIN
    if kt.exists():
        try:
            if MARK in kt.read_text(encoding='utf-8'):
                note('WorkspaceBusybox.kt already applied')
                return
        except Exception:
            pass
    bal = balance(KOTLIN_SRC)
    if bal != 0:
        note('FATAL kotlin balance=' + str(bal) + ' -> not written')
        return
    kt.parent.mkdir(parents=True, exist_ok=True)
    kt.write_text(KOTLIN_SRC, encoding='utf-8')
    note('WorkspaceBusybox.kt written chars=' + str(len(KOTLIN_SRC)))
    text = kt.read_text(encoding='utf-8')
    for need in ['object WorkspaceBusybox', 'const val LIB_NAME', 'const val EXEC_PATH',
                 'fun listApplets(', 'fun ensureFarm(', 'fun hasFarm(', 'fun isReady(']:
        if need not in text:
            note('selfcheck missing ' + need)


def fetch_binary():
    dest = ROOT / DEST_DIR
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / LIB_NAME
    if target.exists():
        data = target.read_bytes()
        problem = elf_problem(data)
        if problem is None:
            note('libbusybox.so already present ok size=' + str(len(data))
                 + ' sha256=' + hashlib.sha256(data).hexdigest())
            return
        note('existing libbusybox.so invalid: ' + problem + ' -> re-download')
        try:
            target.unlink()
        except Exception as exc:
            note('cannot delete invalid libbusybox.so: ' + str(exc)[:120])
            return

    for url, entries in CANDIDATES:
        try:
            blob = http_get(url)
        except Exception as exc:
            note('download failed ' + url + ' err=' + str(exc)[:140])
            continue
        note('downloaded ' + url + ' bytes=' + str(len(blob)))
        try:
            zf = zipfile.ZipFile(io.BytesIO(blob))
            names = zf.namelist()
        except Exception as exc:
            note('zip open failed ' + url + ' err=' + str(exc)[:140])
            continue
        note('zip entries=' + str(len(names)) + ' sample=' + '|'.join(names[:6]))
        picked = None
        for want in entries:
            if want in names:
                picked = want
                break
        if picked is None:
            for candidate in names:
                low = candidate.lower()
                if low.endswith('/busybox') and 'arm64' in low:
                    picked = candidate
                    break
        if picked is None:
            note('no arm64 busybox entry in ' + url)
            continue
        try:
            data = zf.read(picked)
        except Exception as exc:
            note('zip read failed ' + picked + ' err=' + str(exc)[:140])
            continue
        problem = elf_problem(data)
        if problem is not None:
            note('extracted ' + picked + ' rejected: ' + problem)
            continue
        target.write_bytes(data)
        note('wrote ' + DEST_DIR + '/' + LIB_NAME + ' size=' + str(len(data))
             + ' sha256=' + hashlib.sha256(data).hexdigest() + ' from ' + picked)
        return

    note('FATAL: no usable arm64 static busybox could be fetched; workspace shell will report '
         + '"busybox binary is missing" at runtime')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:
        print('::error::batch306 diag write failed ' + str(exc)[:200])


def main():
    for label, fn in [('1 busybox binary', fetch_binary), ('2 WorkspaceBusybox.kt', write_kotlin)]:
        try:
            fn()
        except Exception as exc:
            note(label + ' EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
        print('::error::batch306 part ' + label + ' done')
    write_diag()
    for line in report:
        print('::error::batch306 ' + str(line)[:600])
    print('::error::batch306 END lines=' + str(len(report)))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::error::batch306 crashed ' + str(exc)[:400])
    sys.exit(0)

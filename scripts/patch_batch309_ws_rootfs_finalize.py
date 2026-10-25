#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch309: RootfsInstaller 整文件重写 + Workspace.kt 加 FINALIZING

为什么重写:
1. 现有 install 直接把解包结果 rename 成正式目录, 没有任何收尾步骤 ——
   缺少 /usr/rh-bin applet 农场, 而 ProotShellRunner 现在以 /usr/rh-bin/sh 为入口,
   没有农场 = 装完仍不可用。
2. 上线不是原子的: deleteRecursively 旧目录后 renameTo, 中途失败用户就没环境了。
   改用 manager.createRootfsStaging / commitRootfs(带备份回滚)。
3. 格式判定按 URL 后缀 —— 重定向/镜像路径变体容易误判。改成读文件头 magic。

保留并内置的既有修复(因为本批是整文件覆盖, 必须自己包含):
- batch215/218: blank root entry('./') 不再在 normalizeTarPath 的 require 上抛死
- batch236: 9 个 Alpine 镜像 fallback + 5s/128KB 龟速判定 + 12s/30s 超时 + content-length 校验

新增:
- FINALIZING 阶段: WorkspaceBusybox.ensureFarm(staging, nativeLibraryDir)
- GNU base-256 size 字段(>8GB 或前缀 0x80)
- 每 200 条目报一次进度(之前每条都报, 解包 2 万条目时刷爆 StateFlow)
- 硬链接目标乱序时降级为 0 字节占位(之前直接 return, 后续依赖它的条目会失败)

可视化契约不变: RootfsInstallStage 只新增 FINALIZING, 保留 INSTALLED;
RootfsInstallProgress 字段名一字不改(InstallVM/DetailVM 的契约冻结)。

额外两处一行改动(让 installer 拿到 nativeLibraryDir):
- WorkspaceManager: private val shellRunner -> val shellRunner
- ProotShellRunner: private val nativeLibraryDir -> val nativeLibraryDir
两处都是构造函数属性, 放宽可见性不改签名。

五查: import 新增 Files; 同文件前序仅 batch133 镜像(整文件覆盖无锚点依赖);
新逻辑全在类内; balance 断言; extractTar 签名保持(带默认 format 参数)。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhWsRootfs309'
RI = 'workspace/src/main/java/me/rerere/workspace/RootfsInstaller.kt'
WK = 'workspace/src/main/java/me/rerere/workspace/Workspace.kt'
WM = 'workspace/src/main/java/me/rerere/workspace/WorkspaceManager.kt'
PR = 'workspace/src/main/java/me/rerere/workspace/ProotShellRunner.kt'
DIAG = 'ci_diag_batch309.txt'

SRC = r'''package me.rerere.workspace

import java.io.BufferedInputStream
import java.io.EOFException
import java.io.File
import java.io.IOException
import java.io.InputStream
import java.net.HttpURLConnection
import java.net.URL
import java.nio.file.Files
import java.util.Locale
import java.util.zip.GZIPInputStream
import org.tukaani.xz.XZInputStream

/**
 * rhWsRootfs309: Alpine rootfs 安装器。
 *
 * 流程：staging 下载 → 按 magic 选解包器 → 解包 → FINALIZING（建 /usr/rh-bin 农场）
 * → 原子 commit。任何一步失败都只丢弃 staging，不动现有 rootfs。
 *
 * 关键：安装完必须建 applet 农场（WorkspaceBusybox.ensureFarm），否则
 * ProotShellRunner 找不到 /usr/rh-bin/sh，命令依旧跑不起来。
 */
class RootfsInstaller(
    private val manager: WorkspaceManager,
    private val patcher: RootfsPatcher = RootfsPatcher(),
) {

    private fun nativeLibraryDirOrNull(): File? =
        (manager.shellRunner as? ProotShellRunner)?.nativeLibraryDir

    fun install(
        root: String,
        url: String,
        onProgress: (RootfsInstallProgress) -> Unit = {},
    ) {
        require(url.isNotBlank()) { "Rootfs download url is required" }
        manager.ensureWorkspace(root)
        val nativeLib = nativeLibraryDirOrNull()
            ?: error("workspace engine is not configured: shellRunner is not ProotShellRunner")
        val archive = File(manager.tempDir(root).apply { mkdirs() }, "rootfs.payload")
        val staging = manager.createRootfsStaging(root)
        try {
            onProgress(RootfsInstallProgress(stage = RootfsInstallStage.DOWNLOADING))
            downloadWithFallback(url, archive, onProgress)
            val format = ArchiveFormat.detect(archive)
            extractTar(archive, staging, format, onProgress)
            onProgress(RootfsInstallProgress(stage = RootfsInstallStage.FINALIZING))
            WorkspaceBusybox.ensureFarm(staging, nativeLib) { done, total ->
                onProgress(
                    RootfsInstallProgress(
                        stage = RootfsInstallStage.FINALIZING,
                        entriesExtracted = done,
                        currentEntry = "busybox applet " + done + "/" + total,
                    )
                )
            }
            patcher.patch(staging)
            manager.commitRootfs(root, staging)
            onProgress(RootfsInstallProgress(stage = RootfsInstallStage.INSTALLED))
        } finally {
            archive.delete()
            staging.deleteRecursively()
        }
    }

    // ---------------- 下载 ----------------

    /** rhWsRootfs309: 基于传入 url 生成镜像候选（仅 /alpine/ 同构路径扩展，传入 url 永远第一） */
    private fun buildMirrorCandidates(url: String): List<String> {
        val plain = url.trim()
        val schemeEnd = plain.indexOf("://")
        if (schemeEnd <= 0) return listOf(plain)
        val afterScheme = plain.substring(schemeEnd + 3)
        val slash = afterScheme.indexOf('/')
        if (slash <= 0) return listOf(plain)
        val hostPort = afterScheme.substring(0, slash)
        val host = hostPort.substringBefore(':').lowercase(Locale.US)
        val path = afterScheme.substring(slash)
        val alpineIndex = path.indexOf("/alpine/")
        if (alpineIndex < 0) return listOf(plain)
        val tail = path.substring(alpineIndex)
        val candidates = mutableListOf(plain)
        for (mirror in MIRROR_HOSTS) {
            if (mirror == host) continue
            val candidate = "https://" + mirror + tail
            if (candidate !in candidates) candidates.add(candidate)
        }
        return candidates
    }

    private fun downloadWithFallback(
        url: String,
        target: File,
        onProgress: (RootfsInstallProgress) -> Unit,
    ) {
        val candidates = buildMirrorCandidates(url)
        var lastError: Exception? = null
        for (candidate in candidates) {
            checkInterrupted()
            try {
                download(candidate, target, onProgress)
                return
            } catch (e: InterruptedException) {
                throw e
            } catch (e: Exception) {
                lastError = e
                println("RootfsInstaller: mirror failed, trying next: " + candidate + " (" + e.message + ")")
                target.delete()
                onProgress(RootfsInstallProgress(stage = RootfsInstallStage.DOWNLOADING, bytesRead = 0, totalBytes = null))
            }
        }
        throw lastError ?: IOException("Rootfs download failed: no mirror available")
    }

    private fun download(
        url: String,
        target: File,
        onProgress: (RootfsInstallProgress) -> Unit,
    ) {
        val connection = URL(url).openConnection() as HttpURLConnection
        connection.connectTimeout = CONNECT_TIMEOUT_MS
        connection.readTimeout = READ_TIMEOUT_MS
        connection.instanceFollowRedirects = true
        try {
            val code = connection.responseCode
            require(code in 200..299) { "Rootfs download failed: HTTP " + code }
            val totalBytes = connection.contentLengthLong.takeIf { it > 0 }
            target.parentFile?.mkdirs()
            connection.inputStream.use { input ->
                target.outputStream().use { output ->
                    val buffer = ByteArray(BUFFER_SIZE)
                    var bytesRead = 0L
                    var lastReport = 0L
                    var windowStart = System.currentTimeMillis()
                    var windowBytes = 0L
                    while (true) {
                        checkInterrupted()
                        val read = input.read(buffer)
                        if (read < 0) break
                        output.write(buffer, 0, read)
                        bytesRead += read
                        val now = System.currentTimeMillis()
                        if (now - windowStart >= RATE_WINDOW_MS) {
                            val delta = bytesRead - windowBytes
                            val finished = totalBytes != null && bytesRead >= totalBytes
                            if (!finished && delta < RATE_MIN_BYTES) {
                                throw IOException("mirror too slow: " + delta + "B in " + (now - windowStart) + "ms")
                            }
                            windowStart = now
                            windowBytes = bytesRead
                        }
                        if (bytesRead - lastReport >= PROGRESS_STEP_BYTES
                            || (totalBytes != null && bytesRead >= totalBytes)
                        ) {
                            lastReport = bytesRead
                            onProgress(
                                RootfsInstallProgress(
                                    stage = RootfsInstallStage.DOWNLOADING,
                                    bytesRead = bytesRead,
                                    totalBytes = totalBytes,
                                )
                            )
                        }
                    }
                    if (totalBytes != null && bytesRead != totalBytes) {
                        throw IOException("Rootfs download incomplete: " + bytesRead + "/" + totalBytes)
                    }
                    if (bytesRead == 0L) {
                        onProgress(RootfsInstallProgress(stage = RootfsInstallStage.DOWNLOADING, bytesRead = 0, totalBytes = totalBytes))
                    }
                }
            }
        } finally {
            connection.disconnect()
        }
    }

    // ---------------- 解包 ----------------

    internal fun extractTar(
        archive: File,
        targetDir: File,
        format: ArchiveFormat = ArchiveFormat.fromFile(archive),
        onProgress: (RootfsInstallProgress) -> Unit,
    ) {
        format.wrap(BufferedInputStream(archive.inputStream())).use { input ->
            var entries = 0
            var pendingName: String? = null
            var pendingLink: String? = null
            while (true) {
                checkInterrupted()
                val header = input.readTarHeader() ?: break
                val name = pendingName ?: header.name
                val linkName = pendingLink ?: header.linkName
                pendingName = null
                pendingLink = null
                if (name.isBlank()) {
                    input.skipFully(header.size.padded())
                    continue
                }
                val target = targetDir.safeResolve(name)
                target.parentFile?.mkdirs()
                when (header.type) {
                    TarEntryType.LONG_NAME -> {
                        pendingName = input.readExactly(header.size).text()
                        input.skipFully(header.size.padding())
                        continue
                    }

                    TarEntryType.LONG_LINK -> {
                        pendingLink = input.readExactly(header.size).text()
                        input.skipFully(header.size.padding())
                        continue
                    }

                    TarEntryType.PAX -> {
                        val pax = parsePax(input.readExactly(header.size).text())
                        pendingName = pax["path"]
                        pendingLink = pax["linkpath"]
                        input.skipFully(header.size.padding())
                        continue
                    }

                    TarEntryType.DIRECTORY -> target.mkdirs()
                    TarEntryType.SYMLINK -> createSymlink(targetDir, target, linkName)
                    TarEntryType.HARDLINK -> createHardLink(targetDir, target, linkName)
                    TarEntryType.FILE -> {
                        target.outputStream().use { output ->
                            input.copyExactly(output, header.size)
                        }
                        target.applyMode(header.mode)
                    }

                    TarEntryType.OTHER -> Unit
                }
                // 只在这里跳一次载荷：LONG_NAME/LONG_LINK/PAX 已在分支内 continue。
                // 如果在 when 前后各跳一次，会多吞一个数据区，后续 header 全错位。
                if (header.type != TarEntryType.FILE) {
                    input.skipFully(header.size)
                }
                input.skipFully(header.size.padding())
                if (header.modTime > 0 && header.type != TarEntryType.SYMLINK) {
                    target.setLastModified(header.modTime * 1000L)
                }
                entries++
                if (entries % 200 == 0) {
                    onProgress(
                        RootfsInstallProgress(
                            stage = RootfsInstallStage.EXTRACTING,
                            entriesExtracted = entries,
                            currentEntry = name,
                        )
                    )
                }
            }
            onProgress(
                RootfsInstallProgress(
                    stage = RootfsInstallStage.EXTRACTING,
                    entriesExtracted = entries,
                    currentEntry = null,
                )
            )
        }
    }

    private fun createSymlink(root: File, target: File, linkName: String) {
        if (linkName.isBlank()) return
        val linkTarget = if (File(linkName).isAbsolute) {
            File(linkName)
        } else {
            val resolved = File(target.parentFile ?: root, linkName).canonicalFile
            val rootFile = root.canonicalFile
            require(resolved.path == rootFile.path || resolved.path.startsWith(rootFile.path + File.separator)) {
                "Symlink escapes rootfs: " + target.name
            }
            (target.parentFile ?: root).toPath().relativize(resolved.toPath()).toFile()
        }
        target.delete()
        runCatching { Files.createSymbolicLink(target.toPath(), linkTarget.toPath()) }
            .onFailure { println("RootfsInstaller: symlink failed " + target.name + ": " + it.message) }
    }

    private fun createHardLink(root: File, target: File, linkName: String) {
        if (linkName.isBlank()) return
        val source = runCatching { root.safeResolve(linkName) }.getOrNull() ?: return
        target.delete()
        if (source.isFile) {
            val linked = runCatching { Files.createLink(target.toPath(), source.toPath()) }.isSuccess
            if (linked) return
            runCatching {
                source.copyTo(target, overwrite = true)
                target.setReadable(source.canRead(), false)
                target.setWritable(source.canWrite(), true)
                target.setExecutable(source.canExecute(), false)
            }
            return
        }
        // 乱序 tar：硬链目标还没出现。留 0 字节占位，避免后续依赖它的条目报错。
        runCatching { target.createNewFile() }
    }

    private fun InputStream.readTarHeader(): TarHeader? {
        val block = ByteArray(TAR_BLOCK_SIZE)
        val read = readFullyOrEnd(block)
        if (read == 0) return null
        if (read < TAR_BLOCK_SIZE) throw EOFException("Unexpected EOF while reading tar header")
        if (block.all { it == 0.toByte() }) return null
        val name = block.string(0, 100)
        val prefix = block.string(345, 155)
        val fullName = if (prefix.isBlank()) name else prefix + "/" + name
        // rhWsRootfs309: Alpine 的 './' 根条目规范化后为空，放行到 extractTar 的 blank 分支跳过，
        // 而不是在 normalizeTarPath 的 require(isNotBlank) 上抛死整个安装。
        val safeName = if (isBlankRootEntry(fullName)) "" else normalizeTarPath(fullName)
        return TarHeader(
            name = safeName,
            mode = block.number(100, 8).toInt(),
            size = block.number(124, 12),
            modTime = block.number(136, 12),
            type = when (block[156].toInt().toChar()) {
                '0', '\u0000' -> TarEntryType.FILE
                '5' -> TarEntryType.DIRECTORY
                '2' -> TarEntryType.SYMLINK
                '1' -> TarEntryType.HARDLINK
                'L' -> TarEntryType.LONG_NAME
                'K' -> TarEntryType.LONG_LINK
                'x' -> TarEntryType.PAX
                else -> TarEntryType.OTHER
            },
            linkName = block.string(157, 100),
        )
    }

    private fun parsePax(text: String): Map<String, String> {
        val result = mutableMapOf<String, String>()
        var index = 0
        while (index < text.length) {
            val space = text.indexOf(' ', index)
            if (space < 0) break
            val length = text.substring(index, space).toIntOrNull() ?: break
            if (length <= 0) break
            val end = (index + length).coerceAtMost(text.length)
            val record = text.substring(space + 1, end).trimEnd('\n')
            val equals = record.indexOf('=')
            if (equals > 0) {
                result[record.substring(0, equals)] = record.substring(equals + 1)
            }
            index += length
        }
        return result
    }

    // ---------------- 工具 ----------------

    private fun checkInterrupted() {
        if (Thread.currentThread().isInterrupted) {
            throw InterruptedException("Rootfs install cancelled")
        }
    }

    private fun InputStream.copyExactly(output: java.io.OutputStream, bytes: Long) {
        val buffer = ByteArray(BUFFER_SIZE)
        var remaining = bytes
        while (remaining > 0) {
            checkInterrupted()
            val read = read(buffer, 0, minOf(buffer.size.toLong(), remaining).toInt())
            if (read < 0) throw EOFException("tar 数据区意外截断（剩余 " + remaining + " 字节）")
            output.write(buffer, 0, read)
            remaining -= read
        }
    }

    private fun InputStream.readExactly(bytes: Long): ByteArray {
        require(bytes <= Int.MAX_VALUE) { "Tar entry is too large to buffer: " + bytes }
        val buffer = ByteArray(bytes.toInt())
        val read = readFullyOrEnd(buffer)
        if (read != buffer.size) throw EOFException("Unexpected EOF while reading tar entry")
        return buffer
    }

    private fun InputStream.skipFully(bytes: Long) {
        var remaining = bytes
        while (remaining > 0) {
            checkInterrupted()
            val skipped = skip(remaining)
            if (skipped > 0) {
                remaining -= skipped
            } else if (read() >= 0) {
                remaining--
            } else {
                throw EOFException("Unexpected EOF while skipping tar data")
            }
        }
    }

    private fun InputStream.readFullyOrEnd(buffer: ByteArray): Int {
        var offset = 0
        while (offset < buffer.size) {
            val read = read(buffer, offset, buffer.size - offset)
            if (read < 0) break
            offset += read
        }
        return offset
    }

    private fun File.safeResolve(path: String): File {
        val normalized = normalizeTarPath(path)
        val root = canonicalFile
        val target = File(root, normalized).canonicalFile
        require(target.path == root.path || target.path.startsWith(root.path + File.separator)) {
            "Rootfs entry escapes target directory: " + path
        }
        return target
    }

    private fun File.applyMode(mode: Int) {
        if (mode == 0) return
        setReadable(mode and 0b100_000_000 != 0, false)
        setWritable(mode and 0b010_000_000 != 0, true)
        // API < 29 上 rootfs 原生二进制才可能被执行；API 29+ 走 /usr/rh-bin 农场。
        setExecutable(mode and 0b001_000_000 != 0, false)
    }

    private fun isBlankRootEntry(raw: String): Boolean {
        val normalized = raw
            .replace('\\', '/')
            .trim()
            .trimStart('/')
            .removePrefix("./")
            .trim()
        return normalized.isBlank() || normalized == "."
    }

    private fun normalizeTarPath(path: String): String {
        val normalized = path
            .replace('\\', '/')
            .trim()
            .trimStart('/')
            .removePrefix("./")
        require(normalized.isNotBlank()) { "Rootfs entry path is blank" }
        require(!normalized.contains('\u0000')) { "Rootfs entry path contains invalid character" }
        require(normalized.split('/').none { it == ".." }) { "Rootfs entry escapes target directory: " + path }
        return normalized
    }

    private fun ByteArray.string(offset: Int, length: Int): String {
        val end = (offset until offset + length).firstOrNull { this[it] == 0.toByte() } ?: (offset + length)
        return copyOfRange(offset, end).toString(Charsets.UTF_8).trim()
    }

    /** 八进制字段；兼容 GNU base-256（首字节最高位为 1）。 */
    private fun ByteArray.number(offset: Int, length: Int): Long {
        val first = this[offset].toInt() and 0xFF
        if (first and 0x80 != 0) {
            var value = (first and 0x7F).toLong()
            for (i in 1 until length) {
                value = (value shl 8) or (this[offset + i].toLong() and 0xFF)
            }
            return value
        }
        val raw = string(offset, length).trim().lowercase(Locale.US).trimEnd('\u0000')
        return if (raw.isBlank()) 0L else raw.toLongOrNull(8) ?: 0L
    }

    private fun ByteArray.text(): String = toString(Charsets.UTF_8).trimEnd('\u0000', '\n')

    private fun Long.padding(): Long = (TAR_BLOCK_SIZE - (this % TAR_BLOCK_SIZE)) % TAR_BLOCK_SIZE

    private fun Long.padded(): Long = this + padding()

    private data class TarHeader(
        val name: String,
        val mode: Int,
        val size: Long,
        val modTime: Long,
        val type: TarEntryType,
        val linkName: String,
    )

    private enum class TarEntryType {
        FILE,
        DIRECTORY,
        SYMLINK,
        HARDLINK,
        LONG_NAME,
        LONG_LINK,
        PAX,
        OTHER,
    }

    enum class ArchiveFormat(val extension: String) {
        TAR_GZ("tar.gz") {
            override fun wrap(input: InputStream): InputStream = GZIPInputStream(input)
        },
        TAR_XZ("tar.xz") {
            override fun wrap(input: InputStream): InputStream = XZInputStream(input)
        },
        TAR("tar") {
            override fun wrap(input: InputStream): InputStream = input
        };

        abstract fun wrap(input: InputStream): InputStream

        companion object {
            /** 按文件头 magic 判定，不信 URL 后缀。 */
            fun detect(archive: File): ArchiveFormat {
                val head = ByteArray(6)
                val read = runCatching { archive.inputStream().use { it.read(head) } }.getOrDefault(0)
                if (read >= 6
                    && head[0] == 0xFD.toByte() && head[1] == 0x37.toByte()
                    && head[2] == 0x7A.toByte() && head[3] == 0x58.toByte()
                    && head[4] == 0x5A.toByte() && head[5] == 0x00.toByte()
                ) {
                    return TAR_XZ
                }
                if (read >= 2 && head[0] == 0x1F.toByte() && head[1] == 0x8B.toByte()) {
                    return TAR_GZ
                }
                return TAR
            }

            fun fromFile(file: File): ArchiveFormat = detect(file)
        }
    }

    private companion object {
        private const val TAR_BLOCK_SIZE = 512
        private const val BUFFER_SIZE = 64 * 1024
        private const val PROGRESS_STEP_BYTES = 512 * 1024
        private const val CONNECT_TIMEOUT_MS = 12_000
        private const val READ_TIMEOUT_MS = 30_000
        private const val RATE_WINDOW_MS = 5_000L
        private const val RATE_MIN_BYTES = 128L * 1024
        private val MIRROR_HOSTS = listOf(
            "dl-cdn.alpinelinux.org",
            "mirrors.tuna.tsinghua.edu.cn",
            "mirrors.ustc.edu.cn",
            "mirror.nju.edu.cn",
            "mirrors.aliyun.com",
            "mirrors.huaweicloud.com",
            "mirrors.cloud.tencent.com",
            "mirror.sjtu.edu.cn",
            "mirrors.bfsu.edu.cn",
        )
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


def read(rel):
    p = ROOT / rel
    if not p.exists():
        note('MISSING ' + rel)
        return None
    try:
        return p.read_text(encoding='utf-8')
    except Exception as exc:
        note('READ FAIL ' + rel + ' ' + str(exc)[:120])
        return None


def write(rel, text):
    (ROOT / rel).write_text(text, encoding='utf-8')


def patch_installer():
    bal = balance(SRC)
    if bal != 0:
        note('FATAL installer source balance=' + str(bal))
        return
    p = ROOT / RI
    if p.exists():
        try:
            if MARK in p.read_text(encoding='utf-8'):
                note('installer already applied')
                return
        except Exception:
            pass
    write(RI, SRC)
    text = read(RI) or ''
    for need in ['class RootfsInstaller(', 'ArchiveFormat.detect(archive)',
                 'WorkspaceBusybox.ensureFarm(staging, nativeLib)',
                 'manager.createRootfsStaging(root)', 'manager.commitRootfs(root, staging)',
                 'RootfsInstallStage.FINALIZING', 'MIRROR_HOSTS', 'isBlankRootEntry(fullName)']:
        if need not in text:
            note('SELFCHECK installer missing ' + need)
    note('installer written chars=' + str(len(SRC)) + ' balance=' + str(balance(text)))


def patch_stage_enum():
    text = read(WK)
    if text is None:
        return
    if 'FINALIZING' in text:
        note('stage enum already applied')
        return
    lines = text.split(NL)
    hits = [i for i, ln in enumerate(lines) if ln.strip() == 'INSTALLED,']
    if len(hits) != 1:
        note('ANCHOR stage INSTALLED count=' + str(len(hits)))
        return
    i = hits[0]
    ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    lines.insert(i, ind + 'FINALIZING,')
    out = NL.join(lines)
    if balance(out) != balance(text):
        note('BALANCE stage changed')
        return
    write(WK, out)
    note('stage enum adds FINALIZING (INSTALLED kept)')


def relax_visibility():
    text = read(WM)
    if text is None:
        return
    old = 'private val shellRunner: WorkspaceShellRunner = HostShellRunner(),'
    if old in text:
        text = text.replace(old, 'val shellRunner: WorkspaceShellRunner = HostShellRunner(),', 1)
        write(WM, text)
        note('WorkspaceManager.shellRunner -> public val')
    elif 'val shellRunner: WorkspaceShellRunner' in text:
        note('WorkspaceManager.shellRunner already visible')
    else:
        note('ANCHOR shellRunner not found')

    text = read(PR)
    if text is None:
        return
    old2 = 'private val nativeLibraryDir: File,'
    if old2 in text:
        text = text.replace(old2, 'val nativeLibraryDir: File,', 1)
        write(PR, text)
        note('ProotShellRunner.nativeLibraryDir -> public val')
    elif 'val nativeLibraryDir: File,' in text:
        note('ProotShellRunner.nativeLibraryDir already visible')
    else:
        note('ANCHOR nativeLibraryDir not found')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:
        print('::error::batch309 diag write failed ' + str(exc)[:200])


def main():
    for label, fn in [
        ('1 stage enum', patch_stage_enum),
        ('2 installer', patch_installer),
        ('3 visibility', relax_visibility),
    ]:
        try:
            fn()
        except Exception as exc:
            note(label + ' EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
        print('::error::batch309 part ' + label + ' done')
    write_diag()
    for line in report:
        print('::error::batch309 ' + str(line)[:700])
    print('::error::batch309 END lines=' + str(len(report)))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::error::batch309 crashed ' + str(exc)[:400])
    sys.exit(0)

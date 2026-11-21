#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch236: rootfs/shell 下载多镜像 fallback + 龟速检测

用户反馈: shell/rootfs 安装「一直在加载」(官方版很快)——现实现是单 URL 直连下载无 fallback,
首个源慢/被墙/龟速时卡死(连接 30s/读 60s 超时, 且 readTimeout 对龟速流不敏感)。

方案(最优解, 只动 workspace 模块 RootfsInstaller.kt 单文件, 调用链零改动):
  1. buildMirrorCandidates: 基于传入 url 生成镜像候选——仅当 path 含 /alpine/ 段时扩展为
     全部镜像 host(Alpine 镜像路径同构 <host>/alpine/<相同path>); 传入 url 永远排在第一位
     (尊重调用方选择), 其余按 MIRROR_HOSTS 顺序去重追加; 非 alpine 布局原样单源(旧行为)。
  2. downloadWithFallback: 逐源尝试, HTTP 错误/连接超时/读超时/龟速 自动切下一个;
     全部失败抛最后一个异常(保持原有错误语义给上层 UI/AI)。
  3. 龟速检测: 读循环 5s 窗口内不足 128KB(≈25KB/s) 判龟速换源; 超时收紧 12s/30s。

镜像表(路径同构已验证): dl-cdn(官方)/清华 TUNA/中科大/南大/阿里/华为/腾讯/上交/北外。

五查:
1. import 清单: 无新 import(Locale/IOException 文件已有)
2. 同文件冲突: RootfsInstaller.kt 在链被 batch215/218 改过(isBlankRootEntry/readTarHeader)——
   本批锚区全在 download/companion/install 调用行, 与 215/218 区域不相交; 锚点=snapshot 实读
3. 作用域: 新函数均为类成员; rateWindow 变量在 download 局部; MIRROR_HOSTS 在 companion
4. 括号配对: 插入块自平衡; 全文 balance 断言
5. 函数签名: 不改现有签名; install 改调 downloadWithFallback; download 保持 private 原样

Python 三查: 引号一律 Q 构造; NL 手写 concat; helper 先定义后用; fail-loud + 断言
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhMirror236'
F = 'workspace/src/main/java/me/rerere/workspace/RootfsInstaller.kt'


def fail(msg):
    print('::error::batch236 ' + str(msg)[:1400])
    sys.stdout.flush()
    sys.exit(0)


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def replace_once(text, old, new, label):
    n = text.count(old)
    if n == 0:
        fail(label + ': anchor not found. head=' + repr(old[:120]))
    if n != 1:
        fail(label + ': anchor count=' + str(n) + ' (expected 1). head=' + repr(old[:120]))
    return text.replace(old, new, 1)


def main():
    p = ROOT / F
    if not p.exists():
        fail('RootfsInstaller.kt missing')
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        print('batch236: already applied')
        sys.exit(0)
    bal0 = balance(t)

    # ---- 1. install 调用行 -> downloadWithFallback ----
    old1 = '            download(url, archive, onProgress)'
    new1 = '            downloadWithFallback(url, archive, onProgress) // ' + MARK
    t = replace_once(t, old1, new1, 'install call')

    # ---- 2. 读循环前加龟速窗口变量 ----
    old2 = ('                    val buffer = ByteArray(BUFFER_SIZE)' + NL
            + '                    var bytesRead = 0L' + NL
            + '                    var lastReportBytes = 0L' + NL
            + '                    while (true) {')
    new2 = ('                    val buffer = ByteArray(BUFFER_SIZE)' + NL
            + '                    var bytesRead = 0L' + NL
            + '                    var lastReportBytes = 0L' + NL
            + '                    // ' + MARK + ': 龟速源检测窗口(每 RATE_WINDOW_MS 检查一次增量)' + NL
            + '                    var rateWindowStartMs = System.currentTimeMillis()' + NL
            + '                    var rateWindowBytes = 0L' + NL
            + '                    while (true) {')
    t = replace_once(t, old2, new2, 'rate window vars')

    # ---- 3. 读循环内加龟速判定 ----
    old3 = ('                        output.write(buffer, 0, read)' + NL
            + '                        bytesRead += read')
    new3 = ('                        output.write(buffer, 0, read)' + NL
            + '                        bytesRead += read' + NL
            + '                        // ' + MARK + ': 窗口内增量不足则判龟速, 抛错触发换源' + NL
            + '                        val nowMs = System.currentTimeMillis()' + NL
            + '                        if (nowMs - rateWindowStartMs >= RATE_WINDOW_MS) {' + NL
            + '                            val windowDelta = bytesRead - rateWindowBytes' + NL
            + '                            val finished = totalBytes != null && bytesRead >= totalBytes' + NL
            + '                            if (!finished && windowDelta < RATE_MIN_BYTES) {' + NL
            + '                                throw IOException(' + Q + 'mirror too slow: ' + Q + ' + windowDelta + ' + Q + 'B in ' + Q + ' + (nowMs - rateWindowStartMs) + ' + Q + 'ms' + Q + ')' + NL
            + '                            }' + NL
            + '                            rateWindowStartMs = nowMs' + NL
            + '                            rateWindowBytes = bytesRead' + NL
            + '                        }')
    t = replace_once(t, old3, new3, 'rate check')

    # ---- 4. 新函数插在 download 定义前 ----
    old4 = ('    private fun download(' + NL
            + '        url: String,' + NL
            + '        target: File,' + NL
            + '        onProgress: (RootfsInstallProgress) -> Unit,' + NL
            + '    ) {')
    new_funcs = (
        '    /**' + NL
        + '     * ' + MARK + ': 基于传入 url 生成镜像候选列表。' + NL
        + '     * 仅当 path 含 /alpine/ 段(Alpine 镜像同构布局)时扩展到全部镜像 host;' + NL
        + '     * 传入 url 永远排第一位(尊重调用方选择), 其余按 MIRROR_HOSTS 顺序去重追加。' + NL
        + '     * 非 alpine 布局的 url 原样单源返回, 行为与旧版一致。' + NL
        + '     */' + NL
        + '    private fun buildMirrorCandidates(url: String): List<String> {' + NL
        + '        val plain = url.trim()' + NL
        + '        val schemeEnd = plain.indexOf(' + Q + '://' + Q + ')' + NL
        + '        if (schemeEnd <= 0) return listOf(plain)' + NL
        + '        val afterScheme = plain.substring(schemeEnd + 3)' + NL
        + '        val slash = afterScheme.indexOf(' + Q + '/' + Q + ')' + NL
        + '        if (slash <= 0) return listOf(plain)' + NL
        + '        val hostPort = afterScheme.substring(0, slash)' + NL
        + '        val host = hostPort.substringBefore(' + Q + ':' + Q + ').lowercase(Locale.US)' + NL
        + '        val path = afterScheme.substring(slash)' + NL
        + '        val alpineIndex = path.indexOf(' + Q + '/alpine/' + Q + ')' + NL
        + '        if (alpineIndex < 0) return listOf(plain)' + NL
        + '        val tail = path.substring(alpineIndex)' + NL
        + '        val candidates = mutableListOf(plain)' + NL
        + '        for (mirror in MIRROR_HOSTS) {' + NL
        + '            if (mirror == host) continue' + NL
        + '            val candidate = ' + Q + 'https://' + Q + ' + mirror + tail' + NL
        + '            if (candidate !in candidates) candidates.add(candidate)' + NL
        + '        }' + NL
        + '        return candidates' + NL
        + '    }' + NL
        + NL
        + '    /**' + NL
        + '     * ' + MARK + ': 多镜像 fallback 下载——逐源尝试, HTTP 错误/超时/龟速自动切下一个镜像。' + NL
        + '     * 全部失败时抛最后一个异常(保持原有错误语义给上层 UI/AI)。' + NL
        + '     */' + NL
        + '    private fun downloadWithFallback(' + NL
        + '        url: String,' + NL
        + '        target: File,' + NL
        + '        onProgress: (RootfsInstallProgress) -> Unit,' + NL
        + '    ) {' + NL
        + '        val candidates = buildMirrorCandidates(url)' + NL
        + '        var lastError: Exception? = null' + NL
        + '        for (candidate in candidates) {' + NL
        + '            checkInterrupted()' + NL
        + '            try {' + NL
        + '                download(candidate, target, onProgress)' + NL
        + '                return' + NL
        + '            } catch (e: InterruptedException) {' + NL
        + '                throw e' + NL
        + '            } catch (e: Exception) {' + NL
        + '                lastError = e' + NL
        + '                println(' + Q + 'RootfsInstaller: mirror failed, trying next: ' + Q + ' + candidate + ' + Q + ' (' + Q + ' + e.message + ' + Q + ')' + Q + ')' + NL
        + '                target.delete()' + NL
        + '                onProgress(RootfsInstallProgress(stage = RootfsInstallStage.DOWNLOADING, bytesRead = 0, totalBytes = null))' + NL
        + '            }' + NL
        + '        }' + NL
        + '        throw lastError ?: IOException(' + Q + 'Rootfs download failed: no mirror available' + Q + ')' + NL
        + '    }' + NL
        + NL
    )
    t = replace_once(t, old4, new_funcs + old4, 'insert mirror funcs')

    # ---- 5. companion 常量收紧 + 镜像表 ----
    old5 = ('    companion object {' + NL
            + '        private const val TAR_BLOCK_SIZE = 512' + NL
            + '        private const val BUFFER_SIZE = 64 * 1024' + NL
            + '        private const val PROGRESS_STEP_BYTES = 512 * 1024' + NL
            + '        private const val CONNECT_TIMEOUT_MS = 30_000' + NL
            + '        private const val READ_TIMEOUT_MS = 60_000' + NL
            + '    }')
    new5 = ('    companion object {' + NL
            + '        private const val TAR_BLOCK_SIZE = 512' + NL
            + '        private const val BUFFER_SIZE = 64 * 1024' + NL
            + '        private const val PROGRESS_STEP_BYTES = 512 * 1024' + NL
            + '        // ' + MARK + ': 超时收紧(30s/60s -> 12s/30s), 坏源更快让位给下一镜像' + NL
            + '        private const val CONNECT_TIMEOUT_MS = 12_000' + NL
            + '        private const val READ_TIMEOUT_MS = 30_000' + NL
            + '        // ' + MARK + ': 龟速检测(5s 窗口内 <128KB ≈ 25KB/s 视为龟速)' + NL
            + '        private const val RATE_WINDOW_MS = 5_000L' + NL
            + '        private const val RATE_MIN_BYTES = 128L * 1024' + NL
            + '        // ' + MARK + ': alpinelinux 镜像 host 表(路径同构 <host>/alpine/<相同path>), 按序 fallback' + NL
            + '        private val MIRROR_HOSTS = listOf(' + NL
            + '            ' + Q + 'dl-cdn.alpinelinux.org' + Q + ',' + NL
            + '            ' + Q + 'mirrors.tuna.tsinghua.edu.cn' + Q + ',' + NL
            + '            ' + Q + 'mirrors.ustc.edu.cn' + Q + ',' + NL
            + '            ' + Q + 'mirror.nju.edu.cn' + Q + ',' + NL
            + '            ' + Q + 'mirrors.aliyun.com' + Q + ',' + NL
            + '            ' + Q + 'mirrors.huaweicloud.com' + Q + ',' + NL
            + '            ' + Q + 'mirrors.cloud.tencent.com' + Q + ',' + NL
            + '            ' + Q + 'mirror.sjtu.edu.cn' + Q + ',' + NL
            + '            ' + Q + 'mirrors.bfsu.edu.cn' + Q + ',' + NL
            + '        )' + NL
            + '    }')
    t = replace_once(t, old5, new5, 'companion constants')

    # ---- 自检 ----
    if balance(t) != bal0:
        fail('balance changed ' + str(bal0) + '->' + str(balance(t)))
    if t.count('downloadWithFallback(') != 2:
        fail('downloadWithFallback count=' + str(t.count('downloadWithFallback(')) + ' (expected 2: def+call)')
    if t.count('MIRROR_HOSTS') != 2:
        fail('MIRROR_HOSTS count=' + str(t.count('MIRROR_HOSTS')) + ' (expected 2: def+use)')
    if t.count('RATE_WINDOW_MS') != 2:
        fail('RATE_WINDOW_MS count=' + str(t.count('RATE_WINDOW_MS')) + ' (expected 2: def+use)')
    if 'CONNECT_TIMEOUT_MS = 12_000' not in t:
        fail('connect timeout not tightened')
    p.write_text(t, encoding='utf-8')
    print('::notice::batch236 OK - rootfs mirror fallback (9 hosts) + slow-source detection (5s/128KB) + timeouts 12s/30s')


main()
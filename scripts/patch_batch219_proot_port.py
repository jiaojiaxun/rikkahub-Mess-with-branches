#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch219: 移植 proot 二进制回 fork —— workspace shell 可执行的最后一块拼图（warn-only）

对抗性复查终局发现: 问题不是"二进制被删", 而是移植时整个 workspace native 部分
从未带过来 —— 上游 workspace/src/main/ 有 jniLibs/(两个 proot 二进制) 与 cpp/(PTY
辅助库, fork 的 ProcessBuilder 执行链不需要), fork 只有 java/ + AndroidManifest。
ProotShellRunner.execute() 硬性要求:
  nativeLibraryDir/libproot_exec.so + nativeLibraryDir/libproot_loader.so
—— 缺任何一个就直接返回 exitCode=127 "proot executable not found"。

修法: 构建时从上游(AAAelina/rikkahub-agent master)下载两个 arm64 二进制写入
      workspace/src/main/jniLibs/arm64-v8a/, 用 git blob sha1 校验完整性:
        libproot_exec.so    233392B  blob 5e8d19a5dc065f5fdce6c33eb476e7f7fddf1c1c
        libproot_loader.so   18136B  blob f123455e5037a5d49e0d64c9b330949ff64e4d25
      仅 arm64: app 模块 abiFilters=arm64-v8a, x86_64 不会进 APK。
      app 已开 useLegacyPackaging=true → .so 会解压到 nativeLibraryDir(正是查找位置)。
下载源(顺序尝试): raw.githubusercontent.com → api.github.com(raw accept)。
幂等: 目标已存在且 blob sha 匹配 → 跳过。warn-only: 任何失败只 ::warning, 不阻塞构建。
许可注: proot 为 GPLv2 许可的开源工具; 二进制取自上游公开仓库, 仅随本次自用构建分发。
'''
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path.cwd()
BATCH = 'batch219'

FILES = (
    ('libproot_exec.so', 233392, '5e8d19a5dc065f5fdce6c33eb476e7f7fddf1c1c'),
    ('libproot_loader.so', 18136, 'f123455e5037a5d49e0d64c9b330949ff64e4d25'),
)
DEST_DIR = 'workspace/src/main/jniLibs/arm64-v8a'
SRC_RAW = 'https://raw.githubusercontent.com/AAAelina/rikkahub-agent/master/workspace/src/main/jniLibs/arm64-v8a/'
SRC_API = 'https://api.github.com/repos/AAAelina/rikkahub-agent/contents/workspace/src/main/jniLibs/arm64-v8a/'

applied = []
skipped = []


def joinlist(items):
    t = ''
    for i, s in enumerate(items):
        if i > 0:
            t += ','
        t += s
    return t


def git_blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\x00' + data).hexdigest()


def fetch(url, raw_accept=False):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'rikkahub-batch219/1.0',
    })
    if raw_accept:
        req.add_header('Accept', 'application/vnd.github.raw')
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()


def main():
    dest = ROOT / DEST_DIR
    dest.mkdir(parents=True, exist_ok=True)
    for name, size, blob in FILES:
        target = dest / name
        if target.exists():
            try:
                if git_blob_sha(target.read_bytes()) == blob:
                    applied.append(name + ':exists')
                    continue
            except Exception:
                pass
        data = None
        err = ''
        for src, ra in ((SRC_RAW + name, False), (SRC_API + name + '?ref=master', True)):
            try:
                data = fetch(src, ra)
                break
            except Exception as exc:
                err = str(exc)[:70]
        if data is None:
            skipped.append(name + '<download:' + err + '>')
            continue
        got = git_blob_sha(data)
        if got != blob or len(data) != size:
            skipped.append(name + '<sha-mismatch:' + got[:12] + '>')
            continue
        target.write_bytes(data)
        applied.append(name)
        print(BATCH + ': wrote ' + DEST_DIR + '/' + name + ' (' + str(len(data)) + ' bytes)')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        skipped.append('crash:' + str(exc)[:80])
    print('::warning::' + BATCH + ' applied=[' + joinlist(applied) + '] skipped=[' + joinlist(skipped) + ']')
    sys.exit(0)
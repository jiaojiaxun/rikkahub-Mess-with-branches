#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch307: WorkspaceManager — READY 判定认软链 + 原子 staging/commit

两个真实缺陷:
1. hasRootfs 只看 File(linuxDir,"bin/sh").isFile。安装后 bin/sh 是指向
   /rh-libs/libbusybox.so 的软链, 该目标在宿主上不存在 => isFile=false
   => checkIntegrity 把刚装好的 READY 重置成 DISABLED(用户看到"装完又变未安装")。
   必须用 Files.isSymbolicLink 兜底, 并追加 applet 农场判据。
2. RootfsInstaller 里 deleteRecursively+renameTo 不是原子的: 农场阶段失败时
   旧 rootfs 已删, 用户从坏环境变成没环境。改由 manager 提供 staging+commit(可回滚)。

锚点策略: 全部行级 strip().startswith(), 不依赖右侧表达式原文。
五查: import 新增 Files / 同文件仅 batch133 镜像在前 / 新函数为类成员 / 插入块自平衡 +
全文 balance 断言 / hasRootfs 与 cleanupAllTempDirs 签名不变。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhWsStage307'
F = 'workspace/src/main/java/me/rerere/workspace/WorkspaceManager.kt'
DIAG = 'ci_diag_batch307.txt'
report = []


def note(m):
    report.append(str(m)[:700])


def balance(t):
    return (t.count('(') - t.count(')')
            + t.count('{') - t.count('}')
            + t.count('[') - t.count(']'))


def unique(lines, pred, label):
    hits = [i for i, ln in enumerate(lines) if pred(ln)]
    if len(hits) != 1:
        note('ANCHOR-' + label + ' count=' + str(len(hits)))
        return -1
    return hits[0]


def apply():
    p = ROOT / F
    if not p.exists():
        note('MISSING ' + F)
        return
    text = p.read_text(encoding='utf-8')
    if MARK in text:
        note('already applied')
        return
    lines = text.split(NL)
    bal0 = balance(text)

    if 'import java.nio.file.Files' not in text:
        i = unique(lines, lambda ln: ln.strip() == 'import java.nio.charset.StandardCharsets', 'import')
        if i < 0:
            return
        lines.insert(i + 1, 'import java.nio.file.Files')

    i = unique(lines, lambda ln: ln.strip().startswith('fun hasRootfs(root: String)'), 'hasRootfs')
    if i < 0:
        return
    ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    block = [
        'fun hasRootfs(root: String): Boolean {',
        '    val dir = linuxDir(root)',
        '    val sh = File(dir, ' + Q + 'bin/sh' + Q + ')',
        '    // ' + MARK + ': 安装后 bin/sh 指向 /rh-libs/libbusybox.so, 该目标在宿主不存在;',
        '    // 只认 isFile 会让 checkIntegrity 把刚装好的 READY 误判为文件缺失并重置 DISABLED。',
        '    val shPresent = sh.isFile || Files.isSymbolicLink(sh.toPath())',
        '    // 同时要求 applet 农场已建: 旧版 rootfs(无 /usr/rh-bin)在 API 29+ 仍跑不了命令。',
        '    return shPresent && WorkspaceBusybox.hasFarm(dir)',
        '}',
    ]
    lines[i:i + 1] = [ind + b for b in block]

    i = unique(lines, lambda ln: ln.strip().startswith('const val DEFAULT_COMMAND_TIMEOUT_MS'), 'timeout')
    if i < 0:
        return
    cind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    lines.insert(i + 1, cind + '// ' + MARK + ': rootfs 安装中转目录 / 回滚备份目录(均置于 workspace 根下)')
    lines.insert(i + 2, cind + 'private const val ROOTFS_STAGING_DIR = ' + Q + 'rootfs.staging' + Q)
    lines.insert(i + 3, cind + 'private const val ROOTFS_BACKUP_DIR = ' + Q + 'rootfs.old' + Q)

    i = unique(lines, lambda ln: ln.strip().startswith('fun cleanupAllTempDirs()'), 'cleanup')
    if i < 0:
        return
    fn = [
        '/** ' + MARK + ': 在 workspace 根下开一个干净的中转目录, 失败就整体丢弃, 不碰现有 rootfs。 */',
        'fun createRootfsStaging(root: String): File {',
        '    val dir = File(workspaceDir(root), ROOTFS_STAGING_DIR)',
        '    dir.deleteRecursively()',
        '    dir.mkdirs()',
        '    require(dir.isDirectory) { ' + Q + 'Failed to create rootfs staging directory: ' + Q + ' + dir.absolutePath }',
        '    return dir',
        '}',
        '',
        '/** ' + MARK + ': 原子上线 — 旧 rootfs 先改名备份, 再换入 staging; 换入失败时回滚。 */',
        'fun commitRootfs(root: String, stagingDir: File) {',
        '    require(stagingDir.isDirectory) { ' + Q + 'Rootfs staging directory is missing: ' + Q + ' + stagingDir.absolutePath }',
        '    val target = linuxDir(root)',
        '    val backup = File(workspaceDir(root), ROOTFS_BACKUP_DIR)',
        '    backup.deleteRecursively()',
        '    if (target.exists() && !target.renameTo(backup)) {',
        '        error(' + Q + 'Failed to move existing rootfs aside: ' + Q + ' + target.absolutePath)',
        '    }',
        '    if (!stagingDir.renameTo(target)) {',
        '        if (backup.exists() && !target.exists()) {',
        '            backup.renameTo(target)',
        '        }',
        '        error(' + Q + 'Failed to move new rootfs into place: ' + Q + ' + target.absolutePath)',
        '    }',
        '    backup.deleteRecursively()',
        '}',
        '',
    ]
    lines[i:i] = fn

    out = NL.join(lines)
    if balance(out) != bal0:
        note('BALANCE ' + str(bal0) + ' -> ' + str(balance(out)))
        return
    for need in [MARK, 'fun hasRootfs(root: String): Boolean {',
                 'fun createRootfsStaging(root: String): File {',
                 'fun commitRootfs(root: String, stagingDir: File) {',
                 'import java.nio.file.Files',
                 'Files.isSymbolicLink(sh.toPath())',
                 'WorkspaceBusybox.hasFarm(dir)']:
        if need not in out:
            note('SELFCHECK missing ' + need)
            return
    p.write_text(out, encoding='utf-8')
    note('applied hasRootfs + staging + commit')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:
        print('::error::batch307 diag write failed ' + str(exc)[:200])


if __name__ == '__main__':
    try:
        apply()
    except Exception as exc:
        note('EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
    write_diag()
    for line in report:
        print('::error::batch307 ' + str(line)[:700])
    print('::error::batch307 END lines=' + str(len(report)))
    sys.exit(0)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch311: proot -b 的 guest 目标占位目录

【为什么需要】
proot 的 -b host:guest 在 guest 目标不存在时的行为不可靠: 部分版本会在 rootfs 内
自动 mkdir，部分直接报错退出。我们新增了三个之前不存在的 guest 路径:
    /rh-libs      <- 宿主 nativeLibraryDir
    /workspace    <- files 区
    /skills /tool_outputs /upload <- DI 传入的 bindMounts
只要有任何一条 bind 失败，proot 就在启动阶段死了，表现为 "命令没输出、exit 1"，
比 exec 被拒更难排查。预先建空目录是零成本保险: proot 要的只是一个存在的挂载点。

【两处】
1. WorkspaceBusybox.ensureFarm(安装收尾): 在 staging 里建 rh-libs / workspace，
   跟着 commit 一起进正式 rootfs。
2. WorkspaceManager.ensureWorkspace(每次进工作区): 按实际 bindMounts 补建 target,
   让【已经安装过旧 rootfs】的用户不需要重装也能拿到挂载点。
   WorkspaceRepository 的 executeCommand / startBackground / listFiles 前都会调它,
   时机正好在 proot 启动之前。

五查: 无新 import / 同文件仅 batch306/307 在前(锚点不相交) / 全为成员方法内语句 /
插入块无括号变化 / ensureFarm 与 ensureWorkspace 签名不变。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhWsBind311'
BB = 'workspace/src/main/java/me/rerere/workspace/WorkspaceBusybox.kt'
WM = 'workspace/src/main/java/me/rerere/workspace/WorkspaceManager.kt'
DIAG = 'ci_diag_batch311.txt'
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


def patch_busybox():
    text = read(BB)
    if text is None:
        return
    if MARK in text:
        note('busybox already applied')
        return
    lines = text.split(NL)
    bal0 = balance(text)
    anchor = 'File(linuxDir, ' + Q + 'usr/bin' + Q + ').mkdirs()'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == anchor]
    if len(hits) != 1:
        note('ANCHOR busybox usr/bin count=' + str(len(hits)))
        return
    i = hits[0]
    ind = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    block = [
        ind + '// ' + MARK + ': proot 的 -b 需要 guest 挂载点已存在, 否则部分版本直接启动失败',
        ind + 'File(linuxDir, ' + Q + 'rh-libs' + Q + ').mkdirs()',
        ind + 'File(linuxDir, ' + Q + 'workspace' + Q + ').mkdirs()',
    ]
    lines[i + 1:i + 1] = block
    out = NL.join(lines)
    if balance(out) != bal0:
        note('BALANCE busybox ' + str(bal0) + ' -> ' + str(balance(out)))
        return
    if MARK not in out:
        note('SELFCHECK busybox marker missing')
        return
    (ROOT / BB).write_text(out, encoding='utf-8')
    note('busybox: rh-libs + workspace placeholder created in staging')


def patch_manager():
    text = read(WM)
    if text is None:
        return
    if MARK in text:
        note('manager already applied')
        return
    lines = text.split(NL)
    bal0 = balance(text)
    start = -1
    for idx, ln in enumerate(lines):
        if ln.strip().startswith('fun ensureWorkspace(root: String): File {'):
            start = idx
            break
    if start < 0:
        note('ANCHOR ensureWorkspace not found')
        return
    ret = -1
    for k in range(start, min(start + 20, len(lines))):
        if lines[k].strip() == 'return dir':
            ret = k
            break
    if ret < 0:
        note('ANCHOR return dir not found in ensureWorkspace')
        return
    ind = lines[ret][:len(lines[ret]) - len(lines[ret].lstrip())]
    block = [
        ind + '// ' + MARK + ': proot 的 -b 要求 guest 挂载点存在。按 bindMounts 补建空目录,',
        ind + '// 已经装过旧 rootfs 的用户不需要重装; 每次.executeCommand 前都会走到这里。',
        ind + 'File(linuxDir(root), WorkspaceBusybox.RH_LIBS.trimStart(' + Q + '/' + Q + ')).mkdirs()',
        ind + 'File(linuxDir(root), ROOTFS_WORKSPACE_DIR.trimStart(' + Q + '/' + Q + ')).mkdirs()',
        ind + 'for (mount in sortedBindMounts) {',
        ind + '    File(linuxDir(root), mount.target.trimStart(' + Q + '/' + Q + ')).mkdirs()',
        ind + '}',
    ]
    lines[ret:ret] = block
    out = NL.join(lines)
    if balance(out) != bal0:
        note('BALANCE manager ' + str(bal0) + ' -> ' + str(balance(out)))
        return
    for need in [MARK, 'WorkspaceBusybox.RH_LIBS.trimStart', 'for (mount in sortedBindMounts)']:
        if need not in out:
            note('SELFCHECK manager missing ' + need)
            return
    (ROOT / WM).write_text(out, encoding='utf-8')
    note('manager: bind mount targets ensured in ensureWorkspace')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:
        print('::error::batch311 diag write failed ' + str(exc)[:200])


def main():
    for label, fn in [('1 busybox', patch_busybox), ('2 manager', patch_manager)]:
        try:
            fn()
        except Exception as exc:
            note(label + ' EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
        print('::error::batch311 part ' + label + ' done')
    write_diag()
    for line in report:
        print('::error::batch311 ' + str(line)[:700])
    print('::error::batch311 END lines=' + str(len(report)))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::error::batch311 crashed ' + str(exc)[:400])
    sys.exit(0)

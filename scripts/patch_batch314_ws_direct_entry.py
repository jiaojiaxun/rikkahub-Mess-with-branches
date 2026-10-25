#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch314: exec 入口直连 bind mount 的 busybox（降低对 proot 解析 rootfs 内软链的单点依赖）

【为什么要改】
batch308 把执行入口设为 `/usr/rh-bin/sh` —— 它是 rootfs 里的软链, 指向 /rh-libs/libbusybox.so。
这条链的可用性依赖两个前提: ① 农场里确实建出了 sh 软链; ② proot 能把 guest 内的绝对软链
正确重解析回 bind mount。第二条是 proot 的核心能力, 但一旦它有偏差, **所有命令都跑不了**,
而错误表现为 KBuffer 一致的 ENOENT, 很难定位。

新设计: 直接 exec bind mount 里的实体 `/rh-libs/libbusybox.so`, 并把 applet 名作为 argv[1]:
    [/rh-libs/libbusybox.so, "sh", "-c", <command>]
busybox 的 main 在 basename 不是已知 applet 时会拿 argv[1] 当 applet（就是 `busybox ls` 的形式）。
这样入口只依赖 bind mount（proot 最基础的功能）, 不再依赖软链解析。

保留不变:
- /usr/rh-bin 农场仍然建（PATH 首项）: ls/sed/awk/grep/stat 等子命令走它。
- bin/sh 仍改指 /rh-libs/libbusybox.so（让 #!/bin/sh 脚本能跑）。
- preflight 仍然要求 hasFarm + hasBinary（农场缺失时给用户明确提示）。

五查: 无新 import; 同文件仅 308/312 在前(整文件由它们写定), 本批只改 argv 尾部 3 行;
作用域不变; 插入不改变括号（只是多一行 argv +=）; buildArgv 签名不变。
Python 三查: 引号用 Q/SQ 构造; 无 f-string; 单行常量匹配 + 幂等 marker。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhWsDirect314'
F = 'workspace/src/main/java/me/rerere/workspace/ProotShellRunner.kt'
DIAG = 'ci_diag_batch314.txt'
report = []


def note(m):
    report.append(str(m)[:700])


def balance(t):
    return (t.count('(') - t.count(')')
            + t.count('{') - t.count('}')
            + t.count('[') - t.count(']'))


def main():
    p = ROOT / F
    if not p.exists():
        note('MISSING ' + F)
        return
    text = p.read_text(encoding='utf-8')
    if MARK in text:
        note('already applied')
        return
    old = ('        argv += WorkspaceBusybox.APPLET_PATH + ' + Q + '/' + Q + 'sh' + Q + NL
           + '        argv += ' + Q + '-c' + Q + NL)
    if old not in text:
        note('ANCHOR argv tail not found')
        return
    bal0 = balance(text)
    new = ('        // ' + MARK + ': 入口直连 bind mount 的实体, 不依赖 proot 重解析 rootfs 内软链;' + NL
           + '        // basename 不是已知 applet 时 busybox 会拿 argv[1] 当 applet（即 busybox ls 形式）。' + NL
           + '        argv += WorkspaceBusybox.EXEC_PATH' + NL
           + '        argv += ' + Q + 'sh' + Q + NL
           + '        argv += ' + Q + '-c' + Q + NL)
    text = text.replace(old, new, 1)
    if balance(text) != bal0:
        note('BALANCE ' + str(bal0) + ' -> ' + str(balance(text)))
        return
    for need in [MARK, 'argv += WorkspaceBusybox.EXEC_PATH', 'argv += ' + Q + 'sh' + Q]:
        if need not in text:
            note('SELFCHECK missing ' + need)
            return
    if 'WorkspaceBusybox.APPLET_PATH + ' + Q + '/' + Q + 'sh' + Q in text:
        note('SELFCHECK old entry still present')
        return
    p.write_text(text, encoding='utf-8')
    note('entry switched to EXEC_PATH + argv[1]=sh; farm/bin-sh untouched')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:
        print('::error::batch314 diag write failed ' + str(exc)[:200])


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        note('EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
    write_diag()
    for line in report:
        print('::error::batch314 ' + str(line)[:700])
    print('::error::batch314 END lines=' + str(len(report)))
    sys.exit(0)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rhShell337 -- workspace shell 入口加固：直连 bind mount 的 busybox 实体。

━━ 为什么不是 batch239 ━━
仓库态的 ProotShellRunner.kt 确实是你描述的那份旧实现
（/usr/bin/env + /bin/bash、cd -- "$1"、seccomp 只在兼容模式设），但 CI 链上的
batch308 是**整文件重写**（脚本开头：SRC = r'''package me.rerere.workspace...''')，
写 239 会在 308 之前执行、被整文件覆盖 → 等于没写。

按链上实际执行顺序，三处诉求的现状（逐条核实，不是不修，是已被 308 覆盖）：
  A guest shell 入口：CI 态是 `/usr/rh-bin/sh`（busybox 软链），不存在 /bin/bash；
  B cd --：CI 态命令作为单个 argv 交给 sh -c，没有 cd 包装；
  C seccomp：CI 态 prootProcess 里 `env["PROOT_NO_SECCOMP"] = "1"` 无条件设置。

━━ 真正还缺的一环 ━━
batch314 本来要做"入口直连 /rh-libs/libbusybox.so + argv[1]=sh"，但锚点失配：
snapshot 的 ci_diag_batch314.txt 只有一行 `ANCHOR argv tail not found`。
根因在 314 自己的引号拼接——它写的是
    Q + '/' + Q + 'sh' + Q   →   "/"sh"
多了一个 Q，正确的应该是 Q + '/sh' + Q → "/sh"。
所以 CI 态至今仍是 308 的软链入口，依赖 proot 把 guest 内绝对软链重解析回 bind mount。
一旦这条链有偏差，所有命令都是 ENOENT，且表现一致、极难定位。

━━ 本批做什么 ━━
只改 argv 尾部 1 行 → 2 行：
    argv += WorkspaceBusybox.APPLET_PATH + "/sh"
→   argv += WorkspaceBusybox.EXEC_PATH
    argv += "sh"
exec 目标变成 bind mount 里的实体 /rh-libs/libbusybox.so，busybox 的 main 在 basename
不是已知 applet 时拿 argv[1] 当 applet（就是 `busybox sh` 的形式）。只依赖 proot 最基础的
bind mount 能力，不再依赖软链重解析。

━━ 纪律 ━━
* 行级 strip 全等定位（不赌缩进/注释文本）
* 锚点字符串用 Q + '/sh' + Q 构造（314 就死在这一步）
* 括号三组差值必须为 0
* 幂等 MARK rhShell337
* 不改任何函数签名；不触碰 308/312/313 的其它内容
"""
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhShell337'
F = 'workspace/src/main/java/me/rerere/workspace/ProotShellRunner.kt'
DIAG = 'ci_diag_batch337_shell_entry.txt'
report = []


def note(m):
    report.append(str(m)[:700])
    print('::error::batch337 ' + str(m)[:700])


def parens(t):
    return (
        t.count('(') - t.count(')'),
        t.count('{') - t.count('}'),
        t.count('[') - t.count(']'),
    )


def write_diag():
    try:
        (ROOT / DIAG).write_text(NL.join(report) + NL, encoding='utf-8')
    except Exception as exc:  # noqa: BLE001
        print('::error::batch337 diag write failed ' + str(exc)[:200])


def main():
    p = ROOT / F
    if not p.exists():
        note('MISSING ' + F)
        return
    text = p.read_text(encoding='utf-8')
    if MARK in text:
        note('already applied')
        return
    if 'WorkspaceBusybox.EXEC_PATH' in text:
        note('EXEC_PATH already referenced, skip')
        return

    target = 'argv += WorkspaceBusybox.APPLET_PATH + ' + Q + '/sh' + Q
    lines = text.split(NL)
    idx = -1
    for i, line in enumerate(lines):
        if line.strip() == target:
            idx = i
            break
    if idx < 0:
        note('ANCHOR not found: ' + target)
        return

    line = lines[idx]
    indent = line[:len(line) - len(line.lstrip())]
    before = parens(text)
    replacement = [
        indent + '// ' + MARK + ': 入口直连 bind mount 实体，不依赖 proot 重解析 rootfs 内软链；',
        indent + '// basename 不是已知 applet 时 busybox 拿 argv[1] 当 applet（busybox sh 形式）。',
        indent + 'argv += WorkspaceBusybox.EXEC_PATH',
        indent + 'argv += ' + Q + 'sh' + Q,
    ]
    lines[idx:idx + 1] = replacement
    out = NL.join(lines)
    after = parens(out)

    if after != before:
        note('BALANCE ' + str(before) + ' -> ' + str(after))
        return
    for need in (MARK, 'argv += WorkspaceBusybox.EXEC_PATH', 'argv += ' + Q + 'sh' + Q):
        if need not in out:
            note('SELFCHECK missing ' + need)
            return
    if target in out:
        note('SELFCHECK old entry still present')
        return
    if 'import java.io.File' not in out:
        note('SELFCHECK File import missing')
        return
    pos_exec = out.find('argv += WorkspaceBusybox.EXEC_PATH')
    pos_sh = out.find('argv += ' + Q + 'sh' + Q)
    if not (0 <= pos_exec < pos_sh):
        note('SELFCHECK EXEC_PATH not before sh')
        return

    p.write_text(out, encoding='utf-8')
    note('entry switched: APPLET_PATH/sh -> EXEC_PATH + argv[1]=sh (line ' + str(idx + 1) + ')')
    note('parens before=' + str(before) + ' after=' + str(after))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        note('EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
    write_diag()
    print('::error::batch337 END lines=' + str(len(report)))
    sys.exit(0)
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch218: 修 batch215 Rootfs 修复的不完整——真正让 './' 根条目不再崩溃（warn-only）

对抗性复查发现 batch215 的修复是"假完成":
  batch215 改的是 extractTar 里的 blank 跳过检查, 但 './' 条目的崩溃发生在更早的
  readTarHeader -> normalizeTarPath(fullName) 的 require(isNotBlank) 上——
  异常在 readTarHeader 里就抛了, extractTar 的检查根本执行不到!
  (batch215 改的检查只对 PAX/LONG_NAME 注入 pendingName="./" 的旁路有效)

修法: readTarHeader 里 name = normalizeTarPath(fullName) 改为
      name = if (isBlankRootEntry(fullName)) "" else normalizeTarPath(fullName)。
      blank 名字返回后, extractTar 既有的 blank 检查会正确跳过该条目(目录条目 size=0,
      skipFully(0) 无副作用); 后续条目正常解压。
      安全属性保留: '..' 逃逸与 NUL 仍照常抛错(isBlankRootEntry 只对"规范化后为空"返回 true)。
      依赖: isBlankRootEntry 由 batch215 注入(本脚本检查其存在, 缺则跳过)。

锚点: name = normalizeTarPath(fullName), (readTarHeader 内唯一)。
幂等 marker: rhRootfsSkip218。warn-only; balance 校验; 失败只 ::warning。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch218'
MARK = 'rhRootfsSkip218'

RI = 'workspace/src/main/java/me/rerere/workspace/RootfsInstaller.kt'

applied = []
skipped = []


def ok(tag):
    if tag not in applied:
        applied.append(tag)


def skip(tag, why):
    skipped.append(tag + '<' + str(why)[:80] + '>')


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def concat(lines):
    t = ''
    for i, ln in enumerate(lines):
        if i > 0:
            t += NL
        t += ln
    return t


def joinlist(items):
    t = ''
    for i, s in enumerate(items):
        if i > 0:
            t += ','
        t += s
    return t


def read(path):
    p = ROOT / path
    if not p.exists():
        return None
    try:
        return p.read_text(encoding='utf-8')
    except Exception:
        return None


def write(path, text):
    p = ROOT / path
    if not p.parent.exists():
        p.parent.mkdir(parents=True)
    p.write_text(text, encoding='utf-8')


def main():
    src = read(RI)
    if src is None:
        skip('rootfs218', 'missing')
        return
    if MARK in src:
        ok('rootfs218-exists')
        return
    if 'isBlankRootEntry' not in src:
        skip('rootfs218', 'batch215-helper-missing')
        return
    lines = src.split(NL)
    bal0 = balance(src)

    anchor = 'name = normalizeTarPath(fullName),'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == anchor]
    if len(hits) != 1:
        skip('rootfs218', 'anchor=' + str(len(hits)))
        return
    ci = hits[0]
    d = ind(lines[ci])
    lines[ci] = d + 'name = if (isBlankRootEntry(fullName)) "" else normalizeTarPath(fullName), // ' + MARK + ' (batch218)'

    out = concat(lines)
    if balance(out) != bal0:
        skip('rootfs218', 'balance')
        return
    if MARK not in out:
        skip('rootfs218', 'selfcheck')
        return
    write(RI, out)
    ok('rootfs218')
    print('::warning::' + BATCH + ' applied=[' + joinlist(applied) + '] skipped=[' + joinlist(skipped) + ']')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::warning::' + BATCH + ' crashed: ' + str(exc)[:400])
    sys.exit(0)
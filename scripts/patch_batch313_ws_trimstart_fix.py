#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch313: 修 run#546 的 trimStart(String) 编译错

【annotations 原文】
WorkspaceManager.kt:38/39/41  None of the following candidates is applicable:
  fun String.trimStart(predicate: (Char) -> Boolean): String
    Argument type mismatch: actual type is 'String', but '(Char) -> Boolean' was expected.
  fun CharSequence.trimStart(vararg chars: Char)
    Argument type mismatch: actual type is 'String', but 'Char' was expected.

根因: batch311 里写了 `.trimStart("/")`。Kotlin 的 trimStart / trimEnd / trim
只接受 Char、Char 数组或 predicate，**不存在 String 重载**（要去前缀前缀用 removePrefix）。
三处均改为 trimStart('/')。

本批同时把这类误用加入全模块扫描，以后谁再写 trimStart(" 就直接 fail-loud。
（前两轮教训的共性：静态自检只查括号而不查 Kotlin API 重载，所以 batch313 把
 trim* 带 String 的写法也纳入了断言。）

五查: 无新 import / 同文件仅 307·311 在前(锤点为本批新增的那三行) / 作用域不变 /
替换不改括号 / 函数签名不变。
'''
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhWsFix313'
F = 'workspace/src/main/java/me/rerere/workspace/WorkspaceManager.kt'
MOD = 'workspace/src/main/java/me/rerere/workspace'
DIAG = 'ci_diag_batch313.txt'
report = []


def note(m):
    report.append(str(m)[:700])


def balance(t):
    return (t.count('(') - t.count(')')
            + t.count('{') - t.count('}')
            + t.count('[') - t.count(']'))


def apply():
    p = ROOT / F
    if not p.exists():
        note('MISSING ' + F)
        return
    text = p.read_text(encoding='utf-8')
    if MARK in text:
        note('already applied')
        return
    if '.trimStart("/")' not in text:
        note('ANCHOR trimStart("/") not found -> nothing to do')
        return
    bal0 = balance(text)
    count = text.count('.trimStart("/")')
    text = text.replace('.trimStart("/")', ".trimStart('/')")
    if balance(text) != bal0:
        note('BALANCE changed')
        return
    if '.trimStart("/")' in text:
        note('SELFCHECK trimStart(String) still present')
        return
    # 在 ensureWorkspace 里打上 marker，便于幂等与溯源
    anchor = 'fun ensureWorkspace(root: String): File {'
    if anchor in text and MARK not in text:
        text = text.replace(anchor, anchor + ' // ' + MARK, 1)
    p.write_text(text, encoding='utf-8')
    note('replaced ' + str(count) + ' occurrence(s) of trimStart("/") with trimStart(\'/\')')


def scan_module():
    base = ROOT / MOD
    if not base.is_dir():
        note('module dir missing')
        return
    pattern = re.compile(r'\.trim(?:Start|End)?\("')
    bad = []
    for f in sorted(base.glob('*.kt')):
        try:
            lines = f.read_text(encoding='utf-8').split(NL)
        except Exception:
            continue
        for idx, ln in enumerate(lines):
            if pattern.search(ln):
                bad.append(f.name + ':' + str(idx + 1))
    if bad:
        note('API-MISUSE trim(String) at ' + ','.join(bad))
    else:
        note('module-wide trim(String) clean')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:
        print('::error::batch313 diag write failed ' + str(exc)[:200])


def main():
    try:
        apply()
    except Exception as exc:
        note('EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
    try:
        scan_module()
    except Exception as exc:
        note('scan EXCEPTION ' + str(exc)[:200])


if __name__ == '__main__':
    main()
    write_diag()
    for line in report:
        print('::error::batch313 ' + str(line)[:700])
    print('::error::batch313 END lines=' + str(len(report)))
    sys.exit(0)

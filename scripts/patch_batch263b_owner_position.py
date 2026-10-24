#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch263b: 空操作（no-op）。修正逻辑已并入 batch263 v2。

【为什么废弃】
workflow 的执行方式是 ls scripts/patch_batch*.py | sort -V 后逐个运行。
GNU version sort 把下划线视为大于字母的特殊字符，于是
    patch_batch263b_owner_position.py     排在
    patch_batch263_merge_memory_ownership.py   之前。
本脚本原先要求文件里已有 rhMergeMem263（batch263 的产物），可它先执行时那个标记
还不存在 => 恒 ABORT（实证：ci_diag_batch263b.txt = ABORT prerequisite missing）。
结果是修正从未生效，而 batch263 的错位插入照旧发生 => run#488 的编译红。

现在 batch263 v2 一次做完（签名 + 调用点 + ownerId 位置 + 两处替换），本文件保留为空操作，
只写 diag 说明，不再改任何源码。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch263b.txt'

body = 'NOOP: superseded by batch263 v2' + NL
body += 'reason: sort -V runs patch_batch263b before patch_batch263; prerequisite never existed' + NL
body += 'no source file touched' + NL

try:
    (ROOT / DIAG).write_text(body, encoding='utf-8')
    print('::error::batch263b NOOP (superseded by batch263 v2)')
except Exception as e:
    print('::error::batch263b diag write FAILED ' + str(e)[:200])
sys.stdout.flush()

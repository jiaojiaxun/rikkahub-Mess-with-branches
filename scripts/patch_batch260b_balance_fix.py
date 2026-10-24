#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch260b: 空操作（no-op）。修正逻辑已并入 batch260 v2。

【为什么废弃】
本脚本原先是 batch260 的完整副本，只把 expected balance delta 从 -1 改成 -3。
但 CI 上两批都报 ABORT balance delta unexpected: 0（ci_diag_batch260.txt 与
ci_diag_batch260b.txt 实证）=> 全局 delta 建模与实际文件不符，靠改预期值救不回来。

batch260 v2 改用逐处局部括号断言（每行 0 / -1），不再依赖全局 delta，
并且同样受 sort -V 影响：patch_batch260b 排在 patch_batch260 之前，留着它会在
修正前后各跑一次，徒增噪音。故本文件保留为空操作。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch260b.txt'

body = 'NOOP: superseded by batch260 v2' + NL
body += 'reason: global balance expectation was unmodelable; v2 asserts per-line parens instead' + NL
body += 'no source file touched' + NL

try:
    (ROOT / DIAG).write_text(body, encoding='utf-8')
    print('::error::batch260b NOOP (superseded by batch260 v2)')
except Exception as e:
    print('::error::batch260b diag write FAILED ' + str(e)[:200])
sys.stdout.flush()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch257b（已作废，改为 no-op 占位）

原意图：把 batch257 误插的 `.sample(80.milliseconds)` 换成
`kotlin.time.Duration.parse("PT0.08S")`（零 import）。
run#473 实测：`ANCHOR-MISS .sample(80.milliseconds) count=0` —— 找不到该行，
因为 batch257 的插入位置与形态与预期不同（插在第 1652 行参数列表中间，且同批执行顺序存在偏差）。

本文件不再修改任何源码。T-P2 改由 batch258 在唯一锚点 `}.collect { chunk ->` 上实现。
'''
import sys

print('::error::batch257b no-op: superseded by batch258')
sys.exit(0)
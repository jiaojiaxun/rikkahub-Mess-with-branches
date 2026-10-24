#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch257（已作废，改为 no-op 占位）

作废原因（run#472 实测）：
本脚本的锚点 `).onCompletion { completionCause ->` 在 ChatService.kt 中**不止一处**，
脚本取"第一个匹配"，结果把 `.sample(80.milliseconds)` 插到了第 1652 行的
参数列表中间（`).onCompletion` 的 `)` 之前），语法被截断 =>
    ChatService.kt:1652 Unresolved reference 'milliseconds' / Syntax error: Expecting ')'
    ChatService.kt:1668 Suspension functions can only be called within coroutine body
    ChatService.kt:1689 Unresolved reference 'collect'
    ChatService.kt:1362 Cannot infer type for type parameter 'R'
（后 4 条都是连锁反应）

为什么改成 no-op 而不是修：
batch257c 的回滚在 run#474 里报 `nothing to roll back (already clean)`，
说明"写入"与"回滚"两个脚本在同一批 runner 上的实际先后与我的预期不一致。
把本文件静默成 no-op，可以彻底消除这个变量，让构建先恢复绿。
T-P2 改由 batch258 在**唯一锚点** `}.collect { chunk ->` 上重新实现（脚本内强制 count==1）。

本文件不再修改任何源码。
'''
import sys

print('::error::batch257 no-op: superseded by batch258 (unique-anchor reimplementation)')
sys.exit(0)
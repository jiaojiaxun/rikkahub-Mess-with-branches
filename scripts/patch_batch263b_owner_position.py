#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch263b: 修 batch263 的编译红 —— 我把 val ownerId 插进了函数调用的参数列表中间

【run#487 编译红真因（annotations 实读）】
    MergeDecisionApplier.kt:307:17  Syntax error: Expecting ')' / Expecting an argument
    MergeDecisionApplier.kt:307:21  Unresolved reference 'ownerId'
    MergeDecisionApplier.kt:307:29  Syntax error: Expecting an element
    MergeDecisionApplier.kt:308:92  Syntax error: Unexpected tokens
    MergeDecisionApplier.kt:309:25  Unresolved reference 'ownerId'
    MergeDecisionApplier.kt:310:13  Syntax error: Expecting an element / Unexpected tokens

【我的错（承认是同一类错误的第二次翻车）】
batch263 把「注释 + val ownerId = ...」插在了 `"SELECT 1 FROM ..."` 行的**前面**。
而那行是 `target.query(` 的第一个参数 —— 结果变成了：
    target.query(
        // rhMergeMem263: ...
        val ownerId = ...        ← 参数列表中间出现 val，语法错乱
        "SELECT 1 FROM ...",
        arrayOf(ownerId, ...),
    )
=> 与 batch257 在 1652 行翻车是同一类：插入点选在函数调用的参数列表中间。

【本批修正】
1. 删除 batch263 误插的两行（按内容匹配，不依赖行号）
2. 把 `val ownerId = ...` 移到 `memories.forEach { memory ->` 之后、`target.query(` 之前
3. 查重 `arrayOf(ownerId, memory.content)` 与 `put("assistant_id", ownerId)` 已由 batch263 做过 ✓ 不重做

五查:
 1. import 清单: 零新增
 2. 同文件冲突: 只动 batch263 自己写的两行（含 rhMergeMem263 / val ownerId）
 3. 作用域: ownerId 定义移到 forEach 块开头，query/insert 都在其后
 4. 括号配对: 删除两行（各 1 对 `()`）+ 新增两行（各 1 对）=> balance 不变（断言）
 5. 函数签名: 零改动（mergeMemories 的签名 batch263 已加参数 ✓ 保留）
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败即中止不写盘

【教训（第二次，写死）】
插入点绝不能选在「函数调用的参数列表中间」：锚点若是一行参数（形如 `"..."`、`arrayOf(...)`、
`foo(...)`），新语句必须插在 `foo(` 那一行的**前面**，而不是参数行前面。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch263b.txt'

APPLIER = 'app/src/main/java/me/rerere/rikkahub/data/sync/merge/MergeDecisionApplier.kt'

report = []


def note(msg):
    report.append(str(msg)[:900])


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def lines_to_text(lines):
    out = ''
    for idx, line in enumerate(lines):
        if idx > 0:
            out += NL
        out += line
    return out


def ind_of(line):
    s = line.lstrip()
    return line[:len(line) - len(s)]


class Abort(Exception):
    pass


def unique(lines, needle, label):
    hits = [i for i, ln in enumerate(lines) if ln.strip() == needle]
    if len(hits) != 1:
        note('ABORT ' + label + ': count=' + str(len(hits)) + ' (need 1) -> ' + repr(needle))
        raise Abort(label)
    return hits[0]


def patch():
    p = ROOT / APPLIER
    if not p.exists():
        note('ABORT missing MergeDecisionApplier.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhMergeMem263b' in t:
        note('already applied')
        return
    if 'rhMergeMem263' not in t:
        note('ABORT prerequisite missing: batch263 not applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    # 1. 删除 batch263 误插的两行
    kept = []
    removed = 0
    for ln in lines:
        s = ln.strip()
        if s.startswith('// rhMergeMem263:') or s.startswith('val ownerId = if (memory.assistantId in validAssistantIds)'):
            removed += 1
            continue
        kept.append(ln)
    if removed != 2:
        note('ABORT expected to remove 2 lines, got ' + str(removed))
        raise Abort('remove count')
    lines = kept

    # 2. 在 forEach 开头插入 ownerId
    a = unique(lines, 'memories.forEach { memory ->', 'forEach start')
    ai = ind_of(lines[a])
    lines = lines[:a + 1] + [
        ai + '    // rhMergeMem263b: ownerId 必须在 query 之前定义（batch263 误插在参数列表中间）',
        ai + '    val ownerId = if (memory.assistantId in validAssistantIds) memory.assistantId else defaultAssistantId',
    ] + lines[a + 1:]

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        raise Abort('balance')

    for need in ['val ownerId = if (memory.assistantId in validAssistantIds) memory.assistantId else defaultAssistantId',
                 'arrayOf(ownerId, memory.content),',
                 'put("assistant_id", ownerId)']:
        if need not in t2:
            note('ABORT selfcheck missing ' + need)
            raise Abort('selfcheck')

    # 关键：ownerId 定义必须在 target.query( 之前
    idx_def = -1
    idx_query = -1
    for i, ln in enumerate(t2.split(NL)):
        if 'val ownerId = if (memory.assistantId' in ln:
            idx_def = i
        if ln.strip() == 'target.query(':
            idx_query = i
    if idx_def < 0 or idx_query < 0:
        note('ABORT def/query positions not found')
        raise Abort('position')
    if idx_def >= idx_query:
        note('ABORT ownerId def(' + str(idx_def) + ') is not before query(' + str(idx_query) + ')')
        raise Abort('order')

    p.write_text(t2, encoding='utf-8')
    note('MergeDecisionApplier OK: ownerId defined before target.query, outside param list')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch263b diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch263b diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    try:
        patch()
        note('1 merge memory ownership fix DONE')
    except Abort as e:
        note('1 merge memory ownership fix ABORTED (no file written): ' + str(e))
    except Exception as e:
        note('1 merge memory ownership fix EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::batch263b part: merge memory ownership fix')
    sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch263b ' + str(line)[:800])
    print('::error::batch263b END lines=' + str(len(report)))


main()
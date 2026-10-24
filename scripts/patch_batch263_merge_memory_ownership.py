#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch263 v2: 合并备份后记忆不显示 —— mergeMemories 归属归一（修正插入位置）

【现象】覆盖恢复记忆正常，合并恢复后一条记忆都不显示（用户实测）。

【根因】mergeMemories 直接拿旧备份里的 memory.assistantId 查重与写入。
旧设备 / 别的助手的 assistant_id 在本机不存在；用户没开全局记忆时，记忆页按
「当前助手 id」查询（getMemoriesOfAssistantFlow）=> 写入的那批挂在孤儿 id 下，全部隐藏。

【修法】写入侧归一（不是查询侧兼容）：
    val ownerId = if (memory.assistantId in validAssistantIds) memory.assistantId else defaultAssistantId
查重与写入都用 ownerId。归属合法的原样写入（行为不变）；孤儿归属归到当前默认助手 => 立刻可见。

【v2 修正（run#488 编译红的真因）】
batch263 把注释 + val ownerId 插在 SELECT 语句那一行前面，而那一行是 target.query( 的
第一个参数 => 参数列表中间出现 val，Kotlin 语法错乱：
    MergeDecisionApplier.kt:307:17 Syntax error: Expecting an argument
本 v2 把 ownerId 定义放进 memories.forEach { memory -> 之后、target.query( 之前。

【为什么同时把 batch263b 改成空操作】
workflow 用 ls scripts/patch_batch*.py | sort -V 逐个执行。GNU version sort 把下划线
视为大于字母的特殊字符，于是 patch_batch263b_... 排在 patch_batch263_... 之前。
batch263b 要求文件里已有 rhMergeMem263（batch263 的产物），而它先执行时那个标记
还不存在 => 恒 ABORT（ci_diag_batch263b.txt 实证）。修正逻辑已并入本批。

五查:
 1. import 清单: 零新增（SupportSQLiteDatabase / ImportedMemory / Set / String 都已在用）
 2. 同文件冲突: MergeDecisionApplier.kt 由 batch153 创建，之后无他批改动
 3. 作用域: validAssistantIds / defaultAssistantId 是 apply() 的参数，同文件可见
 4. 括号配对: 签名 1 对换 1 对; 插入行自平衡; 两处替换自平衡 => 全局不变（断言）
 5. 函数签名: 只有 private fun mergeMemories 增加两个参数，唯一调用点同步补实参
Python 三查: 引号用 Q 构造; NL 显式 concat; helper 先定义后用; 失败即中止不写盘
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
DIAG = 'ci_diag_batch263.txt'

APPLIER = 'app/src/main/java/me/rerere/rikkahub/data/sync/merge/MergeDecisionApplier.kt'

MARK = 'rhMergeMem263'
SIG_OLD = 'private fun mergeMemories(target: SupportSQLiteDatabase, memories: List<ImportedMemory>) {'
CALL_OLD = 'mergeMemories(target, importedMemories)'
ARR_OLD = 'arrayOf(memory.assistantId, memory.content),'
PUT_OLD = 'put(' + Q + 'assistant_id' + Q + ', memory.assistantId)'
FOREACH = 'memories.forEach { memory ->'
QUERY = 'target.query('
OWNER = 'val ownerId = if (memory.assistantId in validAssistantIds) memory.assistantId else defaultAssistantId'
ARR_NEW = 'arrayOf(ownerId, memory.content),'
PUT_NEW = 'put(' + Q + 'assistant_id' + Q + ', ownerId)'
CALL_NEW = 'mergeMemories(target, importedMemories, validAssistantIds, defaultAssistantId) // ' + MARK

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
    if MARK in t:
        note('already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    a = unique(lines, SIG_OLD, 'mergeMemories signature')
    ai = ind_of(lines[a])
    lines[a:a + 1] = [
        ai + 'private fun mergeMemories(',
        ai + '    target: SupportSQLiteDatabase,',
        ai + '    memories: List<ImportedMemory>,',
        ai + '    validAssistantIds: Set<String>,',
        ai + '    defaultAssistantId: String,',
        ai + ') {',
    ]

    b = unique(lines, CALL_OLD, 'mergeMemories call site')
    lines[b] = ind_of(lines[b]) + CALL_NEW

    fe = unique(lines, FOREACH, 'memories forEach')
    fi = ind_of(lines[fe])
    lines[fe + 1:fe + 1] = [
        fi + '    // ' + MARK + ': 旧备份的 assistant_id 可能是本机不存在的助手 -> 归到当前默认助手',
        fi + '    ' + OWNER,
    ]

    d = unique(lines, ARR_OLD, 'dedupe args')
    lines[d] = ind_of(lines[d]) + ARR_NEW

    e = unique(lines, PUT_OLD, 'insert assistant_id')
    lines[e] = ind_of(lines[e]) + PUT_NEW

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        raise Abort('balance')

    ls2 = t2.split(NL)

    fn_hits = [i for i, ln in enumerate(ls2) if ln.strip().startswith('private fun mergeMemories(')]
    if len(fn_hits) != 1:
        note('ABORT signature count after patch=' + str(len(fn_hits)))
        raise Abort('signature')
    fn_i = fn_hits[0]

    fe_hits = [i for i, ln in enumerate(ls2) if ln.strip() == FOREACH and i > fn_i]
    if len(fe_hits) < 1:
        note('ABORT forEach not found after signature')
        raise Abort('foreach')
    fe_i = fe_hits[0]

    own_hits = [i for i, ln in enumerate(ls2) if ln.strip() == OWNER]
    if len(own_hits) != 1:
        note('ABORT ownerId definition count=' + str(len(own_hits)))
        raise Abort('owner')
    own_i = own_hits[0]

    q_hits = [i for i, ln in enumerate(ls2) if ln.strip() == QUERY and i > fe_i]
    if len(q_hits) < 1:
        note('ABORT target.query not found after forEach')
        raise Abort('query')
    q_i = q_hits[0]

    if not (fn_i < fe_i < own_i < q_i):
        note('ABORT order wrong fn=' + str(fn_i) + ' fe=' + str(fe_i) + ' own=' + str(own_i) + ' q=' + str(q_i))
        raise Abort('order')

    for need in ['validAssistantIds: Set<String>,',
                 'defaultAssistantId: String,',
                 CALL_NEW,
                 OWNER,
                 ARR_NEW,
                 PUT_NEW]:
        if len([i for i, ln in enumerate(ls2) if ln.strip() == need]) < 1:
            note('ABORT selfcheck missing line: ' + need)
            raise Abort('selfcheck')

    stale = [i for i, ln in enumerate(ls2) if ln.strip() == CALL_OLD]
    if len(stale) > 0:
        note('ABORT old call site still present')
        raise Abort('stale')

    p.write_text(t2, encoding='utf-8')
    note('MergeDecisionApplier OK: ownerId right after forEach, before target.query')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch263 v2 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch263 v2 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    try:
        patch()
        note('1 merge memory ownership DONE')
    except Abort as e:
        note('1 merge memory ownership ABORTED (no file written): ' + str(e))
    except Exception as e:
        note('1 merge memory ownership EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::batch263 v2 part: merge memory ownership')
    sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch263 v2 ' + str(line)[:800])
    print('::error::batch263 v2 END lines=' + str(len(report)))


main()

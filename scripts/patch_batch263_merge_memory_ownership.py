#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch263: 合并备份后记忆仍不显示 —— mergeMemories 的归属没有归一（用户实测反馈）

【现象】用户实测：覆盖恢复记忆正常，但**合并恢复**后记忆一条都不显示。

【根因（实读 MergeDecisionApplier.kt）】
    apply() 的调用链：
        mergeMemories(target, importedMemories)          // ← 只传了数据，没带归属上下文
    private fun mergeMemories(target, memories) {
        memories.forEach { memory ->
            // 查重
            query("SELECT 1 FROM MemoryEntity WHERE assistant_id = ? AND content = ?", [memory.assistantId, memory.content])
            // 写入
            insert(MemoryEntity, { put("assistant_id", memory.assistantId); put("content", memory.content) })
        }
    }
而 batch230 给 MemoryEntity 加了 `conversation_id`（`NOT NULL DEFAULT ''`），所以 `conversation_id`
缺省为 '' → 这没问题（会进长期记忆）。**问题在于 assistant_id 来自旧备份设备，而本地当前
助手的 id 往往不同**（换机 / 重新安装 / 备份来自别的助手）。
用户若没开全局记忆（useGlobalMemory=false），记忆页走：
    getMemoriesOfAssistantFlow(assistantId = 当前助手id)
⇒ 写入的那批记忆挂在**旧设备的助手 id** 下，本地按当前助手 id 查询 ⇒ 一条都不显示。
这与 batch256 修的「全局模式兼容孤儿」是同一类问题，但**只改了全局查询**，没改合并写入侧。

【修法（写入侧归一，而不是靠查询兼容）】
apply() 里本来就有 `validAssistantIds` 与 `defaultAssistantId`（sanitizeEntity 已用它们给对话兜底）。
mergeMemories 也用上：
    val ownerId = if (memory.assistantId in validAssistantIds) memory.assistantId else defaultAssistantId
然后查重与写入都用 ownerId。这样：
· 归属合法的 → 原样写入（行为不变）
· 归属是孤儿（旧备份 id）→ 归到当前默认助手 → 本地按当前助手查询立刻可见

【为什么不沿用 batch256 的"查询侧兼容"】
查询侧兼容是把"查不到"变"全查到"（读放大），写入侧归一是把"挂错归属"在写入时修正（数据正确）。
后者更干净，且不会把别的助手的记忆也显示出来。

五查:
 1. import 清单: 零新增（两个参数都在 apply() 作用域，mergeMemories 是 private fun）
 2. 同文件冲突: MergeDecisionApplier.kt 被 batch153(创建) 后无他批改动，锚点唯一
 3. 作用域: validAssistantIds / defaultAssistantId 已在 apply() 签名内；mergeMemories 新增
    参数仅影响本文件唯一调用点
 4. 括号配对: 只换表达式与参数列表，括号 1 对 1 => balance 不变（断言）
 5. 函数签名: mergeMemories 增加两个参数（private + 唯一调用点同步改）；apply 签名不动
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败即中止不写盘
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch263.txt'

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
    if 'rhMergeMem263' in t:
        note('already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    # 1. mergeMemories 签名加两个参数
    a = unique(lines, 'private fun mergeMemories(target: SupportSQLiteDatabase, memories: List<ImportedMemory>) {',
               'mergeMemories signature')
    ai = ind_of(lines[a])
    lines = lines[:a] + [
        ai + 'private fun mergeMemories(',
        ai + '    target: SupportSQLiteDatabase,',
        ai + '    memories: List<ImportedMemory>,',
        ai + '    validAssistantIds: Set<String>,',
        ai + '    defaultAssistantId: String,',
        ai + ') {',
    ] + lines[a + 1:]

    # 2. 调用点补参数
    b = unique(lines, 'mergeMemories(target, importedMemories)', 'mergeMemories call site')
    lines[b] = ind_of(lines[b]) + 'mergeMemories(target, importedMemories, validAssistantIds, defaultAssistantId) // rhMergeMem263'

    # 3. 写入侧归一：查重与写入都用 ownerId
    c = unique(lines, '"SELECT 1 FROM MemoryEntity WHERE assistant_id = ? AND content = ? LIMIT 1",',
               'memory dedupe query')
    ci = ind_of(lines[c])
    lines = lines[:c] + [
        ci + '// rhMergeMem263: 旧备份记忆的归属可能是本机不存在的助手 id → 归到当前默认助手，否则写入后查不到',
        ci + 'val ownerId = if (memory.assistantId in validAssistantIds) memory.assistantId else defaultAssistantId',
        lines[c],
    ] + lines[c + 1:]

    d = unique(lines, 'arrayOf(memory.assistantId, memory.content),', 'dedupe args')
    lines[d] = ind_of(lines[d]) + 'arrayOf(ownerId, memory.content),'

    e = unique(lines, 'put("assistant_id", memory.assistantId)', 'insert assistant_id')
    lines[e] = ind_of(lines[e]) + 'put("assistant_id", ownerId)'

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        raise Abort('balance')
    for need in ['validAssistantIds: Set<String>,',
                 'defaultAssistantId: String,',
                 'mergeMemories(target, importedMemories, validAssistantIds, defaultAssistantId)',
                 'val ownerId = if (memory.assistantId in validAssistantIds) memory.assistantId else defaultAssistantId',
                 'arrayOf(ownerId, memory.content),',
                 'put("assistant_id", ownerId)']:
        if need not in t2:
            note('ABORT selfcheck missing ' + need)
            raise Abort('selfcheck')
    if 'mergeMemories(target, importedMemories)' in t2.replace('mergeMemories(target, importedMemories, validAssistantIds, defaultAssistantId)', ''):
        note('ABORT old call still present')
        raise Abort('stale')
    p.write_text(t2, encoding='utf-8')
    note('MergeDecisionApplier OK: mergeMemories normalizes orphan assistant_id to default assistant')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch263 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch263 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    try:
        patch()
        note('1 merge memory ownership DONE')
    except Abort as e:
        note('1 merge memory ownership ABORTED (no file written): ' + str(e))
    except Exception as e:
        note('1 merge memory ownership EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::batch263 part: merge memory ownership')
    sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch263 ' + str(line)[:800])
    print('::error::batch263 END lines=' + str(len(report)))


main()
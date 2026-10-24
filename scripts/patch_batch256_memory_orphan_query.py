#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch256: 记忆「旧备份导入后一条都不显示」修复（全局记忆查询兼容孤儿归属）

【已排除的三个假设（都读代码证伪，不是拍脑袋）】
1) "Migration_36_37 缺 DEFAULT 导致 NULL" —— 证伪：实读 AppDatabase.kt 末尾
   `ALTER TABLE memoryentity ADD COLUMN conversation_id TEXT NOT NULL DEFAULT ''`，带默认值。
2) "ImportedDatabaseReconciler 重映射 assistant_id 却没覆盖 memoryentity" —— 证伪：
   它是**结构协调器**（CREATE TABLE / INDEX / workspaces_new 重建 + REMOVED_FEATURE_TABLES），
   不做任何 assistant_id 重映射。
3) "恢复是逐表 insert 丢列" —— 证伪：恢复是**整库快照替换**（atomicReplace + reconcile）。

【真正的形状（读 MemoryDAO + AssistantDetailVM 得出）】
MemoryDAO 的长期/全局查询只有一条 SQL：
    SELECT * FROM memoryentity WHERE assistant_id = :assistantId AND conversation_id = ''
MemoryRepository:
    getGlobalMemoriesFlow()      -> getMemoriesOfAssistantFlow(GLOBAL_MEMORY_ID)
    getMemoriesOfAssistantFlow(a)-> 上面那条 SQL
AssistantDetailVM:
    if (enableShortMemory)      -> getSessionMemoriesOfAssistantFlow(assistantId)   // conversation_id != ''
    else if (useGlobalMemory)   -> getGlobalMemoriesFlow()                          // assistant_id = 'global'
    else                        -> getMemoriesOfAssistantFlow(assistantId)
=> 旧备份里的记忆挂在**备份当时那个助手的 id** 下。只要当前是「全局记忆」模式
   （或在换机/换助手后 id 对不上），`assistant_id = 'global'` 就查不到那批记录，
   而它们其实都是长期记忆（旧版本没有短期记忆概念，conversation_id 恒为空串）
   => 记忆页显示为空。与用户描述「原本的记忆全部按照长期记忆来计数」完全吻合。

【修法（只改 SQL，不动数据、不动 UI、零 import 风险）】
把两条长期查询改成：
    SELECT * FROM memoryentity
    WHERE (assistant_id = :assistantId OR :assistantId = 'global')
      AND (conversation_id IS NULL OR conversation_id = '')
语义：
· 查具体助手（assistantId != 'global'）=> 行为与原来完全一致（只多容忍 NULL）
· 查全局（assistantId == 'global'）=> 返回**所有**长期记忆，包括挂在旧助手 id 下的孤儿行
  => 旧备份的记忆立刻可见，且仍按长期记忆计数
· 不改任何行、不删任何行 => 不需要回滚路径；想恢复严格模式只要把 SQL 改回去

【为什么不用"恢复时把归属改到当前助手"】
那需要读 settings.assistants 做真实 id 集合，而 BackupArchiveRestorer 的修复点位于
非 suspend 的收尾函数里（没有 settings 作用域），要引入 runBlocking 或改签名；
相比之下 SQL 侧兼容是纯读放大，风险与收益更划算。

五查:
 1. import 清单: 零新增（只改 @Query 字符串）
 2. 同文件冲突: MemoryDAO.kt 被 batch230 改过（新增会话查询 + 长期查询加 conversation_id 过滤），
    本批直接改那两条既有 SQL，锚点唯一
 3. 作用域: :assistantId 是既有参数名，GLOBAL_MEMORY_ID 常量值需为 "global"
    （MemoryRepository.getGlobalMemoriesFlow 传的就是它；本批在同批 dump 里回读确认）
 4. 括号配对: SQL 字符串内括号成对增加，整文件 balance 不变（脚本断言）
 5. 函数签名: 零改动
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败记录并继续
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SQ = chr(39)
DIAG = 'ci_diag_batch256.txt'

DAO = 'app/src/main/java/me/rerere/rikkahub/data/db/dao/MemoryDAO.kt'
REPO = 'app/src/main/java/me/rerere/rikkahub/data/repository/MemoryRepository.kt'

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


def patch_dao():
    p = ROOT / DAO
    if not p.exists():
        note('MISSING MemoryDAO.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhMemOrphan256' in t:
        note('dao already applied')
        return
    bal0 = balance(t)

    old_sql = '@Query(' + Q + 'SELECT * FROM memoryentity WHERE assistant_id = :assistantId AND conversation_id = ' + SQ + SQ + Q + ')'
    new_sql = ('@Query(' + Q + 'SELECT * FROM memoryentity WHERE (assistant_id = :assistantId OR :assistantId = ' + SQ + 'global' + SQ + ') '
               'AND (conversation_id IS NULL OR conversation_id = ' + SQ + SQ + '))' + Q + ') // rhMemOrphan256')

    n = t.count(old_sql)
    if n == 0:
        note('dao anchor not found; head=' + repr(old_sql[:120]))
        return
    if n > 2:
        note('dao anchor count unexpected=' + str(n))
        return
    t2 = t.replace(old_sql, new_sql)
    if balance(t2) != bal0:
        note('dao balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        return
    if old_sql in t2:
        note('dao old sql still present')
        return
    p.write_text(t2, encoding='utf-8')
    note('dao OK: global query tolerates orphan ownership (' + str(n) + ' SQL replaced)')


def probe_repo():
    p = ROOT / REPO
    if not p.exists():
        note('probe missing MemoryRepository.kt')
        return
    lines = p.read_text(encoding='utf-8').split(NL)
    for i, ln in enumerate(lines):
        s = ln.strip()
        if 'GLOBAL_MEMORY_ID' in s:
            note('repo L' + str(i + 1) + ':' + s[:160])


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch256 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch256 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    for name, fn in [
        ('1 MemoryDAO global query', patch_dao),
        ('2 GLOBAL_MEMORY_ID probe', probe_repo),
    ]:
        try:
            fn()
            note(name + ' DONE')
        except Exception as e:
            note(name + ' EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
        print('::error::batch256 part: ' + name)
        sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch256 ' + str(line)[:800])
    print('::error::batch256 END lines=' + str(len(report)))


main()
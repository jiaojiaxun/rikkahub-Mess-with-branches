#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch228: 合并"忽视 +1" —— 备份对话 ID 对不上时按去掉 +N 的原名回落匹配本地对话

用户要求: 合并备份时默认忽视"+1"，只拿原本名字来对比。
根因: fork 出的对话标题是 nextForkTitle 生成的"原名+N"(MergeDecisionApplier),
      但扫描器(BackupMergeScanner.scan) 只按 conversation ID 匹配本地 → fork 的
      ID 对不上 → 被当"新对话"重复导入。

修法(两处, 不破坏现有 ID 匹配逻辑):
  1. ConversationDAO.kt 加轻量查询 getAllIdTitles() + ConversationIdTitle 数据类
     (只读 id+title, 不加载节点, 避免大库全量加载拖慢扫描)。
  2. BackupMergeScanner.scan: 备份对话 ID 对不上(localEntity==null)时, 按
     stripForkSuffix(title) 原名回落匹配本地对话, 命中就加载该本地实体+节点做对比,
     而不是直接判 NEW 导入。
     原名提取: 去掉末尾的 "+N"(如 "聊天+1"→"聊天"), 且仅当原名非空时才回落。

幂等 marker rhMergeIgnorePlusN; 锚点要求唯一; warn-only; 括号差值断言。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch228'
MARK = 'rhMergeIgnorePlusN'

DAO = 'app/src/main/java/me/rerere/rikkahub/data/db/dao/ConversationDAO.kt'
SCANNER = 'app/src/main/java/me/rerere/rikkahub/data/sync/merge/BackupMergeScanner.kt'

applied = []
skipped = []


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


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def fail_skip(tag, why):
    skipped.append(tag + '<' + str(why)[:60] + '>')


def main():
    # ============ 1. DAO: 轻量 (id,title) 查询 ============
    dao = read(DAO)
    if dao is None:
        fail_skip('dao', 'missing')
        print('::error::' + BATCH + ' SKIP dao missing')
        return
    if MARK not in dao:
        lines = dao.split(NL)
        bal0 = balance(dao)
        # 1a. 在 getAllIds() 方法后插入 getAllIdTitles()
        anchor1 = '    suspend fun getAllIds(): List<String>'
        hits = [i for i, ln in enumerate(lines) if ln.strip() == 'suspend fun getAllIds(): List<String>']
        if len(hits) != 1:
            fail_skip('dao', 'getAllIds count=' + str(len(hits)))
            print('::error::' + BATCH + ' SKIP dao getAllIds count=' + str(len(hits)))
            return
        gi = hits[0]
        # getAllIds 上一行是 @Query("SELECT id FROM conversationentity")
        insert_block = [
            '',
            '    /** [batch228] 合并"忽视+N"用：只取 id+title，不加载节点（大库友好）。 */',
            '    @Query("SELECT id, title FROM conversationentity")',
            '    suspend fun getAllIdTitles(): List<ConversationIdTitle>',
        ]
        lines[gi + 1:gi + 1] = insert_block
        # 1b. 文件末尾的 ConversationDayCount 数据类后加 ConversationIdTitle
        anchor2 = 'data class ConversationDayCount(val day: String, val count: Int)'
        hits2 = [i for i, ln in enumerate(lines) if ln.strip() == anchor2]
        if len(hits2) != 1:
            fail_skip('dao', 'daycount count=' + str(len(hits2)))
            print('::error::' + BATCH + ' SKIP dao daycount count=' + str(len(hits2)))
            return
        di = hits2[0]
        lines.insert(di + 1, '')
        lines.insert(di + 2, 'data class ConversationIdTitle(val id: String, val title: String) // ' + MARK)
        dao_out = NL.join(lines)
        if balance(dao_out) != bal0:
            fail_skip('dao', 'balance')
            print('::error::' + BATCH + ' SKIP dao balance')
            return
        if 'getAllIdTitles' not in dao_out or 'ConversationIdTitle' not in dao_out:
            fail_skip('dao', 'selfcheck')
            print('::error::' + BATCH + ' SKIP dao selfcheck')
            return
        write(DAO, dao_out)
        applied.append('dao')
    else:
        applied.append('dao-exists')

    # ============ 2. Scanner: 原名回落匹配 ============
    sc = read(SCANNER)
    if sc is None:
        fail_skip('scanner', 'missing')
        print('::error::' + BATCH + ' SKIP scanner missing')
        return
    if MARK not in sc:
        lines = sc.split(NL)
        bal0 = balance(sc)
        # 2a. 在 val localNodes = ... 之后插入原名索引
        anchor3 = '            val conversationItems = stagedConversations.map { backupConv ->'
        hits3 = [i for i, ln in enumerate(lines) if ln.strip() == 'val conversationItems = stagedConversations.map { backupConv ->']
        if len(hits3) != 1:
            fail_skip('scanner', 'conversationItems count=' + str(len(hits3)))
            print('::error::' + BATCH + ' SKIP scanner conversationItems count=' + str(len(hits3)))
            return
        ci = hits3[0]
        idx_block = [
            '            // [batch228] 忽视+N: 备份对话 ID 对不上时, 按去掉 +N 的原名回落匹配',
            '            val stripForkSuffix = { t: String -> t.replace(Regex("\\\\s*\\\\+\\\\s*\\\\d+\\\\s*$"), "").trim() }',
            '            val localIdByBaseTitle = appDatabase.conversationDao().getAllIdTitles()',
            '                .filter { stripForkSuffix(it.title).isNotBlank() }',
            '                .groupBy({ stripForkSuffix(it.title) }, { it.id })',
            '                .mapValues { it.value.first() }',
            '',
        ]
        lines[ci:ci] = idx_block
        # 2b. 替换 localEntity 赋值行为"ID 优先, 落空则按原名回落"
        anchor4 = '                val localEntity = localEntities[backupConv.id]'
        hits4 = [i for i, ln in enumerate(lines) if ln.strip() == 'val localEntity = localEntities[backupConv.id]']
        if len(hits4) != 1:
            fail_skip('scanner', 'localEntity count=' + str(len(hits4)))
            print('::error::' + BATCH + ' SKIP scanner localEntity count=' + str(len(hits4)))
            return
        li = hits4[0]
        # 找 localEntity 之后的 localSnapshot 赋值行（在其前插入回落逻辑）
        # 结构: localEntity = ...; val localSnapshot = localEntity?.let { ... }
        # 我们把 localEntity 的赋值改为带回落的表达式
        lines[li] = (
            '                val localEntity = localEntities[backupConv.id]\n'
            '                    ?: localIdByBaseTitle[stripForkSuffix(backupConv.title)]\n'
            '                        ?.let { matchedId ->\n'
            '                            appDatabase.conversationDao().getConversationById(matchedId)\n'
            '                        } // ' + MARK
        )
        # 但回落命中的本地对话, 它的节点没在 localNodes 里(只加载了备份 ID 的)。
        # 需要同步回落加载节点: localNodes 的 key 换成命中 ID。
        # localSnapshot 那行用 localNodes[backupConv.id] —— 改为回落后的 localEntity.id
        anchor5 = '                val localSnapshot = localEntity?.let { entity ->'
        hits5 = [i for i, ln in enumerate(lines) if ln.strip() == 'val localSnapshot = localEntity?.let { entity ->']
        if len(hits5) != 1:
            fail_skip('scanner', 'localSnapshot count=' + str(len(hits5)))
            print('::error::' + BATCH + ' SKIP scanner localSnapshot count=' + str(len(hits5)))
            return
        si = hits5[0]
        # localSnapshot 块: toSnapshot(entity, localNodes[backupConv.id].orEmpty())
        # 把 localNodes[backupConv.id] 改为 localNodes[entity.id] —— 但回落命中的 entity.id
        # 不在 localNodes 里, 需现加载。改为: localNodes[entity.id] ?: 现加载
        found_nodes_line = -1
        for j in range(si, min(si + 8, len(lines))):
            if 'localNodes[backupConv.id]' in lines[j]:
                found_nodes_line = j
                break
        if found_nodes_line < 0:
            fail_skip('scanner', 'nodes-line not found')
            print('::error::' + BATCH + ' SKIP scanner nodes-line not found')
            return
        lines[found_nodes_line] = lines[found_nodes_line].replace(
            'localNodes[backupConv.id].orEmpty()',
            '(localNodes[entity.id] ?: appDatabase.messageNodeDao().getNodesOfConversation(entity.id))',
        )
        sc_out = NL.join(lines)
        if balance(sc_out) != bal0:
            fail_skip('scanner', 'balance')
            print('::error::' + BATCH + ' SKIP scanner balance')
            return
        for need in ('localIdByBaseTitle', 'stripForkSuffix', MARK):
            if need not in sc_out:
                fail_skip('scanner', 'selfcheck:' + need)
                print('::error::' + BATCH + ' SKIP scanner selfcheck ' + need)
                return
        write(SCANNER, sc_out)
        applied.append('scanner')
    else:
        applied.append('scanner-exists')

    print('::error::' + BATCH + ' applied=[' + joinlist(applied) + '] skipped=[' + joinlist(skipped) + ']')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::error::' + BATCH + ' crashed: ' + str(exc)[:300])
    sys.exit(0)
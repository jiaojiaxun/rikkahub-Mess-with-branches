#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch230 v3: 短期记忆(会话级私有) — 数据层 + 消费侧

需求(用户 2026-10-17):
- 新增「短期记忆」: 只针对单个会话, 会话之间互不可见(私有)
- 原「记忆」变为「长期记忆」: 该助手下所有会话共享(公共)
- 长期/短期互斥, 不能同时开启; 只作用于单个助手
- 管理页按会话分类(UI 在 batch231)

改动(9 文件):
1. MemoryEntity.kt: +conversation_id 列(空串=长期/全局)
2. MemoryDAO.kt: v3 整文件重写(1248B 小文件, 绕开锚点失配未解之谜; 长期查询排除会话记忆 +会话/全短期查询)
3. MemoryRepository.kt: addMemory +conversationId; 映射带 conversationId; +会话/全短期方法
4. Assistant.kt: Assistant +enableShortMemory; AssistantMemory +conversationId
5. AppDatabase.kt: version 36->37; +Migration_36_37(手写, 延续 35_36 先例)
6. DataSourceModule.kt: import + addMigrations 注册 Migration_36_37
7. GenerationHandler.kt: generateText +conversationId 参数; 工具注册与 prompt 门控支持短期
8. MemoryTools.kt: buildMemoryTools +sessionScoped 描述分支(短期时描述只讲会话私有, 长期只讲跨会话)
9. ChatService.kt: memories 装配/memoryText 估算/generateText 调用 三处短期优先

互斥语义: UI 层互斥(batch231); 消费侧「短期优先」裁决兜底(双开时短期生效, 行为确定)。

v1 -> v2 -> v3 演进:
- v1: patch_entity 成功后 patch_dao 起全死; warn-only sed 吞 exit(0), ::error 超 annotation 配额被丢弃
- v2: 失败不连坐(每文件独立 SystemExit 捕获) + ci_diag dump 通道。
  run440 结果: 仅 dao 失败(编译错 MemoryRepository 调 DAO 不存在的方法), 其余 8 文件全建成
  (repo/model 都成功——编译无 enableShortMemory unresolved)。锚点在 snapshot 真实字节模拟命中但 CI 失败,
  fail 点在 balance/count 检查(无 dump_probe 输出), 死因不可见。
- v3: patch_dao 整文件重写(绕开锚点), 重写前 dump CI 真实原文进 ci_diag(复盘留证)。
  snapshot 已验证 MemoryDAO 与仓库态 SHA 相同(无在链 patch), 重写无覆盖风险。

五查:
1. import 清单: DataSourceModule +Migration_36_37; 其余文件无新 import; dao 重写保持原 import 清单
2. 同文件冲突: 目标文件 snapshot 与仓库态 SHA 相同(无在链 patch); ChatService 与并行 batch232 锚点不相交
3. 作用域: conversationId 在 handleMessageComplete 参数与 .also 块内可用; generateText 新参数在 flow 块内可用
4. 括号配对: 每文件改后 balance 自检(dao 重写后全文 balance)
5. 函数签名: buildMemoryTools/generateText/addMemory 新参数均带默认值, 既有调用方兼容

Python 三查: 引号一律 Q/SQ 变量构造且同一字面量只拼一次抽常量(dao 整文件用三引号块, 非拼接, 无引号闭合风险);
NL 手写 concat 禁 join/f-string/walrus; helper 先定义后用; fail-loud + dump 现场
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SQ = chr(39)
KNL = chr(92) + 'n'
MARK = 'rhShortMem'
DIAG = 'ci_diag_batch230.txt'
FAILED = []


def note(msg):
    print('batch230: ' + str(msg))


def fail(msg):
    print('::error::batch230 ' + str(msg)[:1400])
    sys.stdout.flush()
    sys.exit(0)


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def load(rel):
    p = ROOT / rel
    if not p.exists():
        fail('file missing: ' + rel)
    return p.read_text(encoding='utf-8')


def save(rel, text):
    (ROOT / rel).write_text(text, encoding='utf-8')


def diag_write(lines):
    try:
        p = ROOT / DIAG
        old = ''
        if p.exists():
            old = p.read_text(encoding='utf-8')
        body = old
        for ln in lines:
            body += str(ln) + NL
        p.write_text(body, encoding='utf-8')
    except Exception as e:
        print('::error::batch230 diag write failed: ' + str(e)[:200])


def dump_probe(rel, text, anchor, label):
    probe_src = anchor.split(NL)[0].strip()
    probe = probe_src[:40] if len(probe_src) > 0 else label
    if len(probe) < 8 and NL in anchor:
        probe = anchor.split(NL)[1].strip()[:40]
    hits = []
    for i, ln in enumerate(text.split(NL)):
        if probe in ln:
            hits.append('L' + str(i + 1) + ': ' + ln.strip()[:120])
    head = '=== batch230 ' + label + ' anchor miss in ' + rel + ' probe=' + repr(probe)
    out = [head]
    if hits:
        for h in hits[:20]:
            out.append(h)
    else:
        out.append('(no line contains probe; file head follows)')
        for ln in text.split(NL)[:15]:
            out.append('  ' + ln[:120])
    diag_write(out)


def replace_once(text, old, new, label, rel):
    n = text.count(old)
    if n == 0:
        dump_probe(rel, text, old, label)
        fail(label + ': anchor not found. head=' + repr(old[:120]))
    if n != 1:
        dump_probe(rel, text, old, label)
        fail(label + ': anchor count=' + str(n) + ' (expected 1). head=' + repr(old[:120]))
    return text.replace(old, new, 1)


def run_patch(label, fn):
    try:
        fn()
    except SystemExit:
        FAILED.append(label)
    except Exception as e:
        FAILED.append(label + ' EX')
        print('::error::batch230 ' + label + ' exception: ' + str(e)[:300])


def patch_entity():
    rel = 'app/src/main/java/me/rerere/rikkahub/data/db/entity/MemoryEntity.kt'
    t = load(rel)
    if MARK in t:
        note(rel + ' already applied')
        return
    bal0 = balance(t)
    old = ('    @ColumnInfo(' + Q + 'content' + Q + ')' + NL
           + '    val content: String = ' + Q + Q + ',' + NL
           + ')')
    new = ('    @ColumnInfo(' + Q + 'content' + Q + ')' + NL
           + '    val content: String = ' + Q + Q + ',' + NL
           + '    // ' + MARK + ': 短期记忆归属的会话 id; 空串 = 长期/全局记忆' + NL
           + '    @ColumnInfo(' + Q + 'conversation_id' + Q + ')' + NL
           + '    val conversationId: String = ' + Q + Q + ',' + NL
           + ')')
    t = replace_once(t, old, new, 'MemoryEntity', rel)
    if balance(t) != bal0:
        fail('MemoryEntity: balance changed')
    save(rel, t)
    note('MemoryEntity OK')


DAO_FULL = '''package me.rerere.rikkahub.data.db.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import androidx.room.Update
import kotlinx.coroutines.flow.Flow
import me.rerere.rikkahub.data.db.entity.MemoryEntity

@Dao
interface MemoryDAO {
    // rhShortMem: 长期/全局查询只看 conversation_id 为空的记录, 会话私有记忆不走这里
    @Query("SELECT * FROM memoryentity WHERE assistant_id = :assistantId AND conversation_id = ''")
    fun getMemoriesOfAssistantFlow(assistantId: String): Flow<List<MemoryEntity>>

    @Query("SELECT * FROM memoryentity WHERE assistant_id = :assistantId AND conversation_id = ''")
    suspend fun getMemoriesOfAssistant(assistantId: String): List<MemoryEntity>

    // rhShortMem: 单个会话的短期记忆(生成时注入用)
    @Query("SELECT * FROM memoryentity WHERE assistant_id = :assistantId AND conversation_id = :conversationId")
    fun getMemoriesOfConversationFlow(assistantId: String, conversationId: String): Flow<List<MemoryEntity>>

    @Query("SELECT * FROM memoryentity WHERE assistant_id = :assistantId AND conversation_id = :conversationId")
    suspend fun getMemoriesOfConversation(assistantId: String, conversationId: String): List<MemoryEntity>

    // rhShortMem: 该助手名下全部短期记忆(管理页按会话分组用)
    @Query("SELECT * FROM memoryentity WHERE assistant_id = :assistantId AND conversation_id != ''")
    fun getSessionMemoriesOfAssistantFlow(assistantId: String): Flow<List<MemoryEntity>>

    @Query("SELECT * FROM memoryentity")
    fun getAllMemoriesFlow(): Flow<List<MemoryEntity>>

    @Query("SELECT * FROM memoryentity")
    suspend fun getAllMemories(): List<MemoryEntity>

    @Query("SELECT * FROM memoryentity WHERE id = :id")
    suspend fun getMemoryById(id: Int): MemoryEntity?

    @Insert
    suspend fun insertMemory(memory: MemoryEntity): Long

    @Update
    suspend fun updateMemory(memory: MemoryEntity)

    @Query("DELETE FROM memoryentity WHERE id = :id")
    suspend fun deleteMemory(id: Int)

    @Query("DELETE FROM memoryentity WHERE assistant_id = :assistantId")
    suspend fun deleteMemoriesOfAssistant(assistantId: String)
}
'''


def patch_dao():
    rel = 'app/src/main/java/me/rerere/rikkahub/data/db/dao/MemoryDAO.kt'
    t = load(rel)
    if MARK in t:
        note(rel + ' already applied')
        return
    # v3: dump CI 真实原文(复盘留证: 锚点模拟命中但 CI 失败, 死因留档)
    dump = ['=== batch230 dao CI 原文(' + str(len(t)) + ' chars) ===']
    for ln in t.split(NL):
        dump.append(ln[:150])
    diag_write(dump)
    # 整文件重写(文件仅 1248B, 绕开锚点失配; snapshot 已验证与仓库态 SHA 相同, 无在链 patch, 重写无覆盖风险)
    save(rel, DAO_FULL)
    t2 = load(rel)
    if balance(t2) != 0:
        fail('MemoryDAO rewrite: balance != 0')
    if t2.count('conversation_id') != 5:
        fail('MemoryDAO rewrite: conversation_id count=' + str(t2.count('conversation_id')) + ' (expected 5)')
    if 'getSessionMemoriesOfAssistantFlow' not in t2:
        fail('MemoryDAO rewrite: session method missing')
    note('MemoryDAO OK (v3 full rewrite)')


def patch_repo():
    rel = 'app/src/main/java/me/rerere/rikkahub/data/repository/MemoryRepository.kt'
    t = load(rel)
    if MARK in t:
        note(rel + ' already applied')
        return
    bal0 = balance(t)
    old_map = 'AssistantMemory(it.id, it.content)'
    if t.count(old_map) != 4:
        dump_probe(rel, t, old_map, 'MemoryRepository map')
        fail('MemoryRepository: map anchor count=' + str(t.count(old_map)) + ' (expected 4)')
    t = t.replace(old_map, 'AssistantMemory(it.id, it.content, it.conversationId)')

    old_upd = ('        return AssistantMemory(' + NL
               + '            id = newMemory.id,' + NL
               + '            content = newMemory.content,' + NL
               + '        )')
    new_upd = ('        return AssistantMemory(' + NL
               + '            id = newMemory.id,' + NL
               + '            content = newMemory.content,' + NL
               + '            conversationId = newMemory.conversationId,' + NL
               + '        )')
    t = replace_once(t, old_upd, new_upd, 'MemoryRepository updateContent', rel)

    old_add = ('    suspend fun addMemory(assistantId: String, content: String): AssistantMemory {' + NL
               + '        val memory = AssistantMemory(' + NL
               + '            id = 0,' + NL
               + '            content = content,' + NL
               + '        )' + NL
               + '        val newMemory = memory.copy(' + NL
               + '            id = memoryDAO.insertMemory(' + NL
               + '                MemoryEntity(' + NL
               + '                    assistantId = assistantId,' + NL
               + '                    content = memory.content' + NL
               + '                )' + NL
               + '            ).toInt()' + NL
               + '        )' + NL
               + '        return newMemory' + NL
               + '    }')
    new_add = ('    suspend fun addMemory(assistantId: String, content: String, conversationId: String = ' + Q + Q + '): AssistantMemory {' + NL
               + '        val memory = AssistantMemory(' + NL
               + '            id = 0,' + NL
               + '            content = content,' + NL
               + '            conversationId = conversationId,' + NL
               + '        )' + NL
               + '        val newMemory = memory.copy(' + NL
               + '            id = memoryDAO.insertMemory(' + NL
               + '                MemoryEntity(' + NL
               + '                    assistantId = assistantId,' + NL
               + '                    content = memory.content,' + NL
               + '                    conversationId = conversationId,' + NL
               + '                )' + NL
               + '            ).toInt()' + NL
               + '        )' + NL
               + '        return newMemory' + NL
               + '    }' + NL
               + NL
               + '    // ' + MARK + ': 单个会话的短期记忆' + NL
               + '    fun getMemoriesOfConversationFlow(assistantId: String, conversationId: String): Flow<List<AssistantMemory>> =' + NL
               + '        memoryDAO.getMemoriesOfConversationFlow(assistantId, conversationId)' + NL
               + '            .map { entities ->' + NL
               + '                entities.map { AssistantMemory(it.id, it.content, it.conversationId) }' + NL
               + '            }' + NL
               + NL
               + '    suspend fun getMemoriesOfConversation(assistantId: String, conversationId: String): List<AssistantMemory> {' + NL
               + '        return memoryDAO.getMemoriesOfConversation(assistantId, conversationId)' + NL
               + '            .map { AssistantMemory(it.id, it.content, it.conversationId) }' + NL
               + '    }' + NL
               + NL
               + '    // ' + MARK + ': 该助手名下全部短期记忆(管理页按会话分组用)' + NL
               + '    fun getSessionMemoriesOfAssistantFlow(assistantId: String): Flow<List<AssistantMemory>> =' + NL
               + '        memoryDAO.getSessionMemoriesOfAssistantFlow(assistantId)' + NL
               + '            .map { entities ->' + NL
               + '                entities.map { AssistantMemory(it.id, it.content, it.conversationId) }' + NL
               + '            }')
    t = replace_once(t, old_add, new_add, 'MemoryRepository addMemory', rel)
    if balance(t) != bal0:
        fail('MemoryRepository: balance changed')
    if t.count('getSessionMemoriesOfAssistantFlow') != 2:
        fail('MemoryRepository: session method count != 2')
    save(rel, t)
    note('MemoryRepository OK')


def patch_model():
    rel = 'app/src/main/java/me/rerere/rikkahub/data/model/Assistant.kt'
    t = load(rel)
    if MARK in t:
        note(rel + ' already applied')
        return
    bal0 = balance(t)
    old_flag = ('    val enableMemory: Boolean = false,' + NL
                + '    val useGlobalMemory: Boolean = false, // 使用全局共享记忆而非助手隔离记忆' + NL)
    new_flag = ('    val enableMemory: Boolean = false,' + NL
                + '    val useGlobalMemory: Boolean = false, // 使用全局共享记忆而非助手隔离记忆' + NL
                + '    // ' + MARK + ': 短期记忆(会话级私有), 与 enableMemory 互斥(UI 层互斥, 消费侧短期优先)' + NL
                + '    val enableShortMemory: Boolean = false,' + NL)
    t = replace_once(t, old_flag, new_flag, 'Assistant flag', rel)

    old_mem = ('@Serializable' + NL
               + 'data class AssistantMemory(' + NL
               + '    val id: Int,' + NL
               + '    val content: String = ' + Q + Q + ',' + NL
               + ')')
    new_mem = ('@Serializable' + NL
               + 'data class AssistantMemory(' + NL
               + '    val id: Int,' + NL
               + '    val content: String = ' + Q + Q + ',' + NL
               + '    // ' + MARK + ': 短期记忆归属会话 id; 空串 = 长期/全局' + NL
               + '    val conversationId: String = ' + Q + Q + ',' + NL
               + ')')
    t = replace_once(t, old_mem, new_mem, 'AssistantMemory', rel)
    if balance(t) != bal0:
        fail('Assistant: balance changed')
    save(rel, t)
    note('Assistant OK')


def patch_database():
    rel = 'app/src/main/java/me/rerere/rikkahub/data/db/AppDatabase.kt'
    t = load(rel)
    if MARK in t:
        note(rel + ' already applied')
        return
    bal0 = balance(t)
    if '    version = 37,' in t:
        note('AppDatabase version already 37')
    else:
        t = replace_once(t, '    version = 36,', '    version = 37,', 'AppDatabase version', rel)

    new_cls = ('// ' + MARK + ': v37 adds conversation_id to MemoryEntity for per-conversation short-term memory.' + NL
               + '// Hand-written like 35->36: the 36.json schema export was never committed either.' + NL
               + 'class Migration_36_37 : Migration(36, 37) {' + NL
               + '    override fun migrate(db: SupportSQLiteDatabase) {' + NL
               + '        db.execSQL(' + Q + 'ALTER TABLE memoryentity ADD COLUMN conversation_id TEXT NOT NULL DEFAULT ' + SQ + SQ + Q + ')' + NL
               + '    }' + NL
               + '}' + NL
               + NL)
    t = replace_once(t, 'object TokenUsageConverter {', new_cls + 'object TokenUsageConverter {', 'AppDatabase migration', rel)
    if balance(t) != bal0:
        fail('AppDatabase: balance changed')
    save(rel, t)
    note('AppDatabase OK')


def patch_di():
    rel = 'app/src/main/java/me/rerere/rikkahub/di/DataSourceModule.kt'
    t = load(rel)
    if MARK in t:
        note(rel + ' already applied')
        return
    bal0 = balance(t)
    old_imp = 'import me.rerere.rikkahub.data.db.Migration_35_36'
    new_imp = (old_imp + NL
               + 'import me.rerere.rikkahub.data.db.Migration_36_37 // ' + MARK)
    t = replace_once(t, old_imp, new_imp, 'DataSourceModule import', rel)

    old_reg = 'Migration_35_36())'
    new_reg = 'Migration_35_36(), Migration_36_37())'
    t = replace_once(t, old_reg, new_reg, 'DataSourceModule addMigrations', rel)
    if balance(t) != bal0:
        fail('DataSourceModule: balance changed')
    save(rel, t)
    note('DataSourceModule OK')


def patch_handler():
    rel = 'app/src/main/java/me/rerere/rikkahub/data/ai/GenerationHandler.kt'
    t = load(rel)
    if MARK in t:
        note(rel + ' already applied')
        return
    bal0 = balance(t)

    old_sig = ('        workspaceCwd: String? = null,' + NL
               + '    ): Flow<GenerationChunk> = flow {')
    new_sig = ('        workspaceCwd: String? = null,' + NL
               + '        // ' + MARK + ': 短期记忆写入路由需要会话 id; 非会话调用(压缩/标题等)保持空串' + NL
               + '        conversationId: String = ' + Q + Q + ',' + NL
               + '    ): Flow<GenerationChunk> = flow {')
    t = replace_once(t, old_sig, new_sig, 'GenerationHandler signature', rel)

    old_tools = ('                if (assistant.enableMemory) {' + NL
                 + '                    val memoryAssistantId = if (assistant.useGlobalMemory) {' + NL
                 + '                        MemoryRepository.GLOBAL_MEMORY_ID' + NL
                 + '                    } else {' + NL
                 + '                        assistant.id.toString()' + NL
                 + '                    }' + NL
                 + '                    buildMemoryTools(' + NL
                 + '                        json = json,' + NL
                 + '                        onCreation = { content ->' + NL
                 + '                            memoryRepo.addMemory(memoryAssistantId, content)' + NL
                 + '                        },')
    new_tools = ('                if (assistant.enableMemory || assistant.enableShortMemory) {' + NL
                 + '                    // ' + MARK + ': 短期模式跳过全局开关并把写入绑定到当前会话; 消费侧短期优先' + NL
                 + '                    val memoryAssistantId = if (assistant.useGlobalMemory && !assistant.enableShortMemory) {' + NL
                 + '                        MemoryRepository.GLOBAL_MEMORY_ID' + NL
                 + '                    } else {' + NL
                 + '                        assistant.id.toString()' + NL
                 + '                    }' + NL
                 + '                    val memoryConversationId = if (assistant.enableShortMemory) conversationId else ' + Q + Q + NL
                 + '                    buildMemoryTools(' + NL
                 + '                        json = json,' + NL
                 + '                        sessionScoped = assistant.enableShortMemory,' + NL
                 + '                        onCreation = { content ->' + NL
                 + '                            memoryRepo.addMemory(memoryAssistantId, content, memoryConversationId)' + NL
                 + '                        },')
    t = replace_once(t, old_tools, new_tools, 'GenerationHandler tools', rel)

    old_gate = ('            val memoryPrompt = if (assistant.enableMemory) {' + NL
                + '                buildMemoryPrompt(memories = memories)' + NL
                + '            } else ' + Q + Q)
    new_gate = ('            val memoryPrompt = if (assistant.enableMemory || assistant.enableShortMemory) {' + NL
                + '                buildMemoryPrompt(memories = memories)' + NL
                + '            } else ' + Q + Q)
    t = replace_once(t, old_gate, new_gate, 'GenerationHandler prompt gate', rel)

    if balance(t) != bal0:
        fail('GenerationHandler: balance changed')
    if t.count('sessionScoped = assistant.enableShortMemory') != 1:
        fail('GenerationHandler: sessionScoped wire missing')
    save(rel, t)
    note('GenerationHandler OK')


def patch_tools():
    rel = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/MemoryTools.kt'
    t = load(rel)
    if MARK in t:
        note(rel + ' already applied')
        return
    bal0 = balance(t)
    old_sig = ('fun buildMemoryTools(' + NL
               + '    json: Json,' + NL
               + '    onCreation: suspend (String) -> AssistantMemory,')
    new_sig = ('fun buildMemoryTools(' + NL
               + '    json: Json,' + NL
               + '    // ' + MARK + ': true = 短期记忆(会话私有), 描述里向模型申明作用域; 只显示当前模式的介绍' + NL
               + '    sessionScoped: Boolean = false,' + NL
               + '    onCreation: suspend (String) -> AssistantMemory,')
    t = replace_once(t, old_sig, new_sig, 'MemoryTools signature', rel)

    old_desc = '        description = ' + Q * 3
    new_desc = ('        description = (if (sessionScoped) '
                + Q + 'SCOPE: SHORT-TERM memory, private to THIS conversation only; saved memories will NOT appear in other conversations.' + Q
                + ' + ' + Q + KNL + KNL + Q + ' else ' + Q + Q + ') + ' + Q * 3)
    t = replace_once(t, old_desc, new_desc, 'MemoryTools description', rel)
    if balance(t) != bal0:
        fail('MemoryTools: balance changed')
    save(rel, t)
    note('MemoryTools OK')


def patch_service():
    rel = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
    t = load(rel)
    if MARK in t:
        note(rel + ' already applied')
        return
    bal0 = balance(t)

    old_call = ('                workspaceCwd = conversation.workspaceCwd,' + NL
                + '                memories = if (assistant.useGlobalMemory) {' + NL
                + '                    memoryRepository.getGlobalMemories()' + NL
                + '                } else {' + NL
                + '                    memoryRepository.getMemoriesOfAssistant(assistant.id.toString())' + NL
                + '                },')
    new_call = ('                workspaceCwd = conversation.workspaceCwd,' + NL
                + '                // ' + MARK + ': 短期记忆绑定当前会话' + NL
                + '                conversationId = conversationId.toString(),' + NL
                + '                memories = if (assistant.enableShortMemory) {' + NL
                + '                    memoryRepository.getMemoriesOfConversation(assistant.id.toString(), conversationId.toString())' + NL
                + '                } else if (assistant.useGlobalMemory) {' + NL
                + '                    memoryRepository.getGlobalMemories()' + NL
                + '                } else {' + NL
                + '                    memoryRepository.getMemoriesOfAssistant(assistant.id.toString())' + NL
                + '                },')
    t = replace_once(t, old_call, new_call, 'ChatService generateText call', rel)

    old_est = ('                            memoryText = (' + NL
               + '                                if (assistant.useGlobalMemory) {' + NL
               + '                                    memoryRepository.getGlobalMemories()' + NL
               + '                                } else {' + NL
               + '                                    memoryRepository.getMemoriesOfAssistant(assistant.id.toString())' + NL
               + '                                }' + NL
               + '                            ).joinToString(' + Q + KNL + Q + ') { it.content },')
    new_est = ('                            memoryText = (' + NL
               + '                                if (assistant.enableShortMemory) {' + NL
               + '                                    memoryRepository.getMemoriesOfConversation(assistant.id.toString(), conversationId.toString())' + NL
               + '                                } else if (assistant.useGlobalMemory) {' + NL
               + '                                    memoryRepository.getGlobalMemories()' + NL
               + '                                } else {' + NL
               + '                                    memoryRepository.getMemoriesOfAssistant(assistant.id.toString())' + NL
               + '                                }' + NL
               + '                            ).joinToString(' + Q + KNL + Q + ') { it.content },')
    t = replace_once(t, old_est, new_est, 'ChatService memoryText', rel)

    if balance(t) != bal0:
        fail('ChatService: balance changed')
    if t.count('getMemoriesOfConversation(assistant.id.toString(), conversationId.toString())') != 2:
        fail('ChatService: short-memory read count != 2')
    save(rel, t)
    note('ChatService OK')


def main():
    run_patch('entity', patch_entity)
    run_patch('dao', patch_dao)
    run_patch('repo', patch_repo)
    run_patch('model', patch_model)
    run_patch('database', patch_database)
    run_patch('di', patch_di)
    run_patch('handler', patch_handler)
    run_patch('tools', patch_tools)
    run_patch('service', patch_service)
    if FAILED:
        diag_write(['=== batch230 v3 FAILED files: ' + ', '.join(FAILED)])
        print('::error::batch230 FAILED: ' + ', '.join(FAILED))
    else:
        print('::notice::batch230 v3 OK - short-term(session-scoped) memory: entity+dao+repo+model+db37+di+handler+tools+service')


main()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch230: 短期记忆(会话级私有) — 数据层 + 消费侧

需求(用户 2026-10-17):
- 新增「短期记忆」: 只针对单个会话, 会话之间互不可见(私有)
- 原「记忆」变为「长期记忆」: 该助手下所有会话共享(公共)
- 长期/短期互斥, 不能同时开启; 只作用于单个助手
- 管理页按会话分类(本批只做数据+链路, UI 在 batch231)

改动(9 文件):
1. MemoryEntity.kt: +conversation_id 列(空串=长期/全局)
2. MemoryDAO.kt: 长期查询排除会话记忆; +会话查询/全短期查询
3. MemoryRepository.kt: addMemory +conversationId; 映射带 conversationId; +会话/全短期方法
4. Assistant.kt: Assistant +enableShortMemory; AssistantMemory +conversationId
5. AppDatabase.kt: version 36->37; +Migration_36_37(手写, 延续 35_36 先例)
6. DataSourceModule.kt: import + addMigrations 注册 Migration_36_37
7. GenerationHandler.kt: generateText +conversationId 参数; 工具注册与 prompt 门控支持短期
8. MemoryTools.kt: buildMemoryTools +sessionScoped 描述分支
9. ChatService.kt: memories 装配/memoryText 估算/generateText 调用 三处短期优先

互斥语义: UI 层互斥(batch231); 消费侧「短期优先」裁决兜底(双开时短期生效, 行为确定)。

五查:
1. import 清单: DataSourceModule +Migration_36_37; 其余文件无新 import
2. 同文件冲突: MemoryEntity/MemoryDAO/MemoryRepository/MemoryTools snapshot 与仓库态 SHA 相同(无在链 patch);
   Assistant.kt 差异在 batch28 注释与 localTools 行, 锚点区域不相交;
   AppDatabase/DataSourceModule/GenerationHandler/ChatService 锚点取自 CI 形态(snapshot 分支实读)
3. 作用域: conversationId 在 handleMessageComplete 参数与 .also 块内可用;
   generateText 新参数在 flow 块内(toolsInternal 装配处)可用
4. 括号配对: 每文件改后 balance 自检
5. 函数签名: buildMemoryTools/generateText/addMemory 新参数均带默认值, 既有调用方兼容

Python 三查: 引号一律 Q/SQ 变量构造且同一字面量只拼一次抽常量; NL 手写 concat 禁 join/f-string/walrus;
helper 先定义后用; 失败显式 exit(1) + ::error 输出现场
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SQ = chr(39)
KNL = chr(92) + 'n'
MARK = 'rhShortMem'


def fail(msg):
    print('::error::batch230 ' + str(msg)[:1400])
    sys.stdout.flush()
    sys.exit(1)


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


def replace_once(text, old, new, label):
    n = text.count(old)
    if n == 0:
        fail(label + ': anchor not found. head=' + repr(old[:120]))
    if n != 1:
        fail(label + ': anchor count=' + str(n) + ' (expected 1). head=' + repr(old[:120]))
    return text.replace(old, new, 1)


def patch_entity():
    rel = 'app/src/main/java/me/rerere/rikkahub/data/db/entity/MemoryEntity.kt'
    t = load(rel)
    if MARK in t:
        print('batch230: ' + rel + ' already applied')
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
    t = replace_once(t, old, new, 'MemoryEntity')
    if balance(t) != bal0:
        fail('MemoryEntity: balance changed')
    save(rel, t)
    print('batch230: MemoryEntity OK')


def patch_dao():
    rel = 'app/src/main/java/me/rerere/rikkahub/data/db/dao/MemoryDAO.kt'
    t = load(rel)
    if MARK in t:
        print('batch230: ' + rel + ' already applied')
        return
    bal0 = balance(t)
    old_flow = ('    @Query(' + Q + 'SELECT * FROM memoryentity WHERE assistant_id = :assistantId' + Q + ')' + NL
                + '    fun getMemoriesOfAssistantFlow(assistantId: String): Flow<List<MemoryEntity>>')
    new_flow = ('    // ' + MARK + ': 长期/全局查询只看 conversation_id 为空的记录, 会话私有记忆不走这里' + NL
                + '    @Query(' + Q + 'SELECT * FROM memoryentity WHERE assistant_id = :assistantId AND conversation_id = ' + SQ + SQ + Q + ')' + NL
                + '    fun getMemoriesOfAssistantFlow(assistantId: String): Flow<List<MemoryEntity>>')
    t = replace_once(t, old_flow, new_flow, 'MemoryDAO flow')

    old_suspend = ('    @Query(' + Q + 'SELECT * FROM memoryentity WHERE assistant_id = :assistantId' + Q + ')' + NL
                   + '    suspend fun getMemoriesOfAssistant(assistantId: String): List<MemoryEntity>')
    new_suspend = ('    @Query(' + Q + 'SELECT * FROM memoryentity WHERE assistant_id = :assistantId AND conversation_id = ' + SQ + SQ + Q + ')' + NL
                   + '    suspend fun getMemoriesOfAssistant(assistantId: String): List<MemoryEntity>' + NL
                   + NL
                   + '    // ' + MARK + ': 单个会话的短期记忆(生成时注入用)' + NL
                   + '    @Query(' + Q + 'SELECT * FROM memoryentity WHERE assistant_id = :assistantId AND conversation_id = :conversationId' + Q + ')' + NL
                   + '    fun getMemoriesOfConversationFlow(assistantId: String, conversationId: String): Flow<List<MemoryEntity>>' + NL
                   + NL
                   + '    @Query(' + Q + 'SELECT * FROM memoryentity WHERE assistant_id = :assistantId AND conversation_id = :conversationId' + Q + ')' + NL
                   + '    suspend fun getMemoriesOfConversation(assistantId: String, conversationId: String): List<MemoryEntity>' + NL
                   + NL
                   + '    // ' + MARK + ': 该助手名下全部短期记忆(管理页按会话分组用)' + NL
                   + '    @Query(' + Q + 'SELECT * FROM memoryentity WHERE assistant_id = :assistantId AND conversation_id != ' + SQ + SQ + Q + ')' + NL
                   + '    fun getSessionMemoriesOfAssistantFlow(assistantId: String): Flow<List<MemoryEntity>>')
    t = replace_once(t, old_suspend, new_suspend, 'MemoryDAO suspend')
    if balance(t) != bal0:
        fail('MemoryDAO: balance changed')
    if t.count('conversation_id') != 5:
        fail('MemoryDAO: conversation_id count=' + str(t.count('conversation_id')) + ' (expected 5)')
    save(rel, t)
    print('batch230: MemoryDAO OK')


def patch_repo():
    rel = 'app/src/main/java/me/rerere/rikkahub/data/repository/MemoryRepository.kt'
    t = load(rel)
    if MARK in t:
        print('batch230: ' + rel + ' already applied')
        return
    bal0 = balance(t)
    old_map = 'AssistantMemory(it.id, it.content)'
    if t.count(old_map) != 4:
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
    t = replace_once(t, old_upd, new_upd, 'MemoryRepository updateContent')

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
    t = replace_once(t, old_add, new_add, 'MemoryRepository addMemory')
    if balance(t) != bal0:
        fail('MemoryRepository: balance changed')
    if t.count('getSessionMemoriesOfAssistantFlow') != 2:
        fail('MemoryRepository: session method count != 2')
    save(rel, t)
    print('batch230: MemoryRepository OK')


def patch_model():
    rel = 'app/src/main/java/me/rerere/rikkahub/data/model/Assistant.kt'
    t = load(rel)
    if MARK in t:
        print('batch230: ' + rel + ' already applied')
        return
    bal0 = balance(t)
    old_flag = ('    val enableMemory: Boolean = false,' + NL
                + '    val useGlobalMemory: Boolean = false, // 使用全局共享记忆而非助手隔离记忆' + NL)
    new_flag = ('    val enableMemory: Boolean = false,' + NL
                + '    val useGlobalMemory: Boolean = false, // 使用全局共享记忆而非助手隔离记忆' + NL
                + '    // ' + MARK + ': 短期记忆(会话级私有), 与 enableMemory 互斥(UI 层互斥, 消费侧短期优先)' + NL
                + '    val enableShortMemory: Boolean = false,' + NL)
    t = replace_once(t, old_flag, new_flag, 'Assistant flag')

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
    t = replace_once(t, old_mem, new_mem, 'AssistantMemory')
    if balance(t) != bal0:
        fail('Assistant: balance changed')
    save(rel, t)
    print('batch230: Assistant OK')


def patch_database():
    rel = 'app/src/main/java/me/rerere/rikkahub/data/db/AppDatabase.kt'
    t = load(rel)
    if MARK in t:
        print('batch230: ' + rel + ' already applied')
        return
    bal0 = balance(t)
    t = replace_once(t, '    version = 36,', '    version = 37,', 'AppDatabase version')

    new_cls = ('// ' + MARK + ': v37 adds conversation_id to MemoryEntity for per-conversation short-term memory.' + NL
               + '// Hand-written like 35->36: the 36.json schema export was never committed either.' + NL
               + 'class Migration_36_37 : Migration(36, 37) {' + NL
               + '    override fun migrate(db: SupportSQLiteDatabase) {' + NL
               + '        db.execSQL(' + Q + 'ALTER TABLE memoryentity ADD COLUMN conversation_id TEXT NOT NULL DEFAULT ' + SQ + SQ + Q + ')' + NL
               + '    }' + NL
               + '}' + NL
               + NL)
    t = replace_once(t, 'object TokenUsageConverter {', new_cls + 'object TokenUsageConverter {', 'AppDatabase migration')
    if balance(t) != bal0:
        fail('AppDatabase: balance changed')
    save(rel, t)
    print('batch230: AppDatabase OK')


def patch_di():
    rel = 'app/src/main/java/me/rerere/rikkahub/di/DataSourceModule.kt'
    t = load(rel)
    if MARK in t:
        print('batch230: ' + rel + ' already applied')
        return
    bal0 = balance(t)
    old_imp = 'import me.rerere.rikkahub.data.db.Migration_35_36'
    new_imp = (old_imp + NL
               + 'import me.rerere.rikkahub.data.db.Migration_36_37 // ' + MARK)
    t = replace_once(t, old_imp, new_imp, 'DataSourceModule import')

    old_reg = 'Migration_35_36())'
    new_reg = 'Migration_35_36(), Migration_36_37())'
    t = replace_once(t, old_reg, new_reg, 'DataSourceModule addMigrations')
    if balance(t) != bal0:
        fail('DataSourceModule: balance changed')
    save(rel, t)
    print('batch230: DataSourceModule OK')


def patch_handler():
    rel = 'app/src/main/java/me/rerere/rikkahub/data/ai/GenerationHandler.kt'
    t = load(rel)
    if MARK in t:
        print('batch230: ' + rel + ' already applied')
        return
    bal0 = balance(t)

    old_sig = ('        workspaceCwd: String? = null,' + NL
               + '    ): Flow<GenerationChunk> = flow {')
    new_sig = ('        workspaceCwd: String? = null,' + NL
               + '        // ' + MARK + ': 短期记忆写入路由需要会话 id; 非会话调用(压缩/标题等)保持空串' + NL
               + '        conversationId: String = ' + Q + Q + ',' + NL
               + '    ): Flow<GenerationChunk> = flow {')
    t = replace_once(t, old_sig, new_sig, 'GenerationHandler signature')

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
    t = replace_once(t, old_tools, new_tools, 'GenerationHandler tools')

    old_gate = ('            val memoryPrompt = if (assistant.enableMemory) {' + NL
                + '                buildMemoryPrompt(memories = memories)' + NL
                + '            } else ' + Q + Q)
    new_gate = ('            val memoryPrompt = if (assistant.enableMemory || assistant.enableShortMemory) {' + NL
                + '                buildMemoryPrompt(memories = memories)' + NL
                + '            } else ' + Q + Q)
    t = replace_once(t, old_gate, new_gate, 'GenerationHandler prompt gate')

    if balance(t) != bal0:
        fail('GenerationHandler: balance changed')
    if t.count('sessionScoped = assistant.enableShortMemory') != 1:
        fail('GenerationHandler: sessionScoped wire missing')
    save(rel, t)
    print('batch230: GenerationHandler OK')


def patch_tools():
    rel = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/MemoryTools.kt'
    t = load(rel)
    if MARK in t:
        print('batch230: ' + rel + ' already applied')
        return
    bal0 = balance(t)
    old_sig = ('fun buildMemoryTools(' + NL
               + '    json: Json,' + NL
               + '    onCreation: suspend (String) -> AssistantMemory,')
    new_sig = ('fun buildMemoryTools(' + NL
               + '    json: Json,' + NL
               + '    // ' + MARK + ': true = 短期记忆(会话私有), 描述里向模型申明作用域' + NL
               + '    sessionScoped: Boolean = false,' + NL
               + '    onCreation: suspend (String) -> AssistantMemory,')
    t = replace_once(t, old_sig, new_sig, 'MemoryTools signature')

    old_desc = '        description = ' + Q * 3
    new_desc = ('        description = (if (sessionScoped) '
                + Q + 'SCOPE: SHORT-TERM memory, private to THIS conversation only; saved memories will NOT appear in other conversations.' + Q
                + ' + ' + Q + KNL + KNL + Q + ' else ' + Q + Q + ') + ' + Q * 3)
    t = replace_once(t, old_desc, new_desc, 'MemoryTools description')
    if balance(t) != bal0:
        fail('MemoryTools: balance changed')
    save(rel, t)
    print('batch230: MemoryTools OK')


def patch_service():
    rel = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
    t = load(rel)
    if MARK in t:
        print('batch230: ' + rel + ' already applied')
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
    t = replace_once(t, old_call, new_call, 'ChatService generateText call')

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
    t = replace_once(t, old_est, new_est, 'ChatService memoryText')

    if balance(t) != bal0:
        fail('ChatService: balance changed')
    if t.count('getMemoriesOfConversation(assistant.id.toString(), conversationId.toString())') != 2:
        fail('ChatService: short-memory read count != 2')
    save(rel, t)
    print('batch230: ChatService OK')


def main():
    patch_entity()
    patch_dao()
    patch_repo()
    patch_model()
    patch_database()
    patch_di()
    patch_handler()
    patch_tools()
    patch_service()
    print('::notice::batch230 OK - short-term(session-scoped) memory: entity+dao+repo+model+db37+di+handler+tools+service')


main()

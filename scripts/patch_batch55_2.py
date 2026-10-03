#!/usr/bin/env python3
'''batch55-2: 引擎填值——子代理对话落 parentChatId + Repository 映射补全

改动（三文件，全部锚点实读 2026-10-03 22:25）：
1. SubAgentEngine.executeRun 签名四参→五参（+parentConversationId: Uuid?）
2. dispatch 内 executeRun 调用处加参数
3. executeRun 的 .copy 加 parentChatId = parentConversationId
4. ConversationRepository.conversationToConversationEntity 正映射加一行
5. ConversationRepository.conversationEntityToConversation 反映射加一行
6. Migration_34_35 SQL 表名统一小写 conversationentity（55-1 大写能跑，风格统一）

前置链勘测：三文件均无人碰过（55-1 是同批推的，本脚本字典序在后，
执行时 55-1 已应用——Repository 映射的锚点用 55-1 后的形态？不：
55-1 没碰 Repository。SubAgentEngine 也没碰。均为原始形态 ✅）'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhEngineParent'


def fail(path, msg):
    print('::error file=' + path + '::batch55-2 ' + str(msg)[:1500])
    raise SystemExit(1)


# ============================================================
# 1. SubAgentEngine.kt — executeRun 五参 + copy 填值
# ============================================================
SE = 'app/src/main/java/me/rerere/rikkahub/subagent/SubAgentEngine.kt'
s = (ROOT / SE).read_text(encoding='utf-8')
if 'rhEngineParent' not in s:
    # 1a. 调用处加参数
    OLD_1A = 'executeRun(runId, parentAssistantId, cleaned, profile)'
    NEW_1A = 'executeRun(runId, parentAssistantId, parentConversationId, cleaned, profile)'
    if OLD_1A not in s:
        fail(SE, 'executeRun call anchor not found')
    if s.count(OLD_1A) != 1:
        fail(SE, 'executeRun call anchor not unique')
    s = s.replace(OLD_1A, NEW_1A, 1)

    # 1b. executeRun 签名加参数
    OLD_1B = (
        '    private suspend fun executeRun(' + NL +
        '        runId: String,' + NL +
        '        parentAssistantId: Uuid,' + NL +
        '        request: SubAgentRequest,' + NL +
        '        profile: SubAgentExecutionProfile,' + NL +
        '    ) {'
    )
    NEW_1B = (
        '    private suspend fun executeRun(' + NL +
        '        runId: String,' + NL +
        '        parentAssistantId: Uuid,' + NL +
        '        // ' + MARK + ' (batch55-2): 父对话 id，写进子对话的 parentChatId' + NL +
        '        parentConversationId: Uuid?,' + NL +
        '        request: SubAgentRequest,' + NL +
        '        profile: SubAgentExecutionProfile,' + NL +
        '    ) {'
    )
    if OLD_1B not in s:
        fail(SE, 'executeRun signature anchor not found')
    s = s.replace(OLD_1B, NEW_1B, 1)

    # 1c. .copy 加 parentChatId
    OLD_1C = (
        '        ).copy(' + NL +
        '            title = "[Sub-agent] ${request.label?.take(40) ?: request.task.take(40)}",' + NL +
        '            // fork 适配：Conversation.customSystemPrompt 承载子代理有效提示词，' + NL +
        '            // chatModelId 承载有效模型；子对话复用父助手 → 工具开关自然继承。' + NL +
        '            customSystemPrompt = profile.effectiveSystemPrompt,' + NL +
        '            chatModelId = profile.effectiveModelId,' + NL +
        '        )'
    )
    NEW_1C = (
        '        ).copy(' + NL +
        '            title = "[Sub-agent] ${request.label?.take(40) ?: request.task.take(40)}",' + NL +
        '            // fork 适配：Conversation.customSystemPrompt 承载子代理有效提示词，' + NL +
        '            // chatModelId 承载有效模型；子对话复用父助手 → 工具开关自然继承。' + NL +
        '            customSystemPrompt = profile.effectiveSystemPrompt,' + NL +
        '            chatModelId = profile.effectiveModelId,' + NL +
        '            // ' + MARK + ' (batch55-2): 父子关系落库——折叠树/审批继承的数据基础' + NL +
        '            parentChatId = parentConversationId,' + NL +
        '        )'
    )
    if OLD_1C not in s:
        fail(SE, 'copy anchor not found')
    s = s.replace(OLD_1C, NEW_1C, 1)

    for need in [MARK, 'parentConversationId,', 'parentChatId = parentConversationId']:
        if need not in s:
            fail(SE, 'selfcheck missing: ' + need)
    (ROOT / SE).write_text(s, encoding='utf-8')
    print('batch55-2: SubAgentEngine OK')
else:
    print('batch55-2: SubAgentEngine already applied')

# ============================================================
# 2. ConversationRepository.kt — 正/反映射加 parentChatId
# ============================================================
CR = 'app/src/main/java/me/rerere/rikkahub/data/repository/ConversationRepository.kt'
r = (ROOT / CR).read_text(encoding='utf-8')
if 'rhRepoParent' not in r:
    # 2a. 正映射（Conversation → Entity）
    OLD_2A = (
        '            folderId = conversation.folderId?.toString() ?: "",' + NL +
        '            chatModelId = encodeChatModelId(conversation.chatModelId),' + NL +
        '        )' + NL +
        '    }' + NL + NL +
        '    fun conversationEntityToConversation('
    )
    NEW_2A = (
        '            folderId = conversation.folderId?.toString() ?: "",' + NL +
        '            chatModelId = encodeChatModelId(conversation.chatModelId),' + NL +
        '            // rhRepoParent (batch55-2): 子代理对话的父对话 id 落库' + NL +
        '            parentChatId = conversation.parentChatId?.toString() ?: "",' + NL +
        '        )' + NL +
        '    }' + NL + NL +
        '    fun conversationEntityToConversation('
    )
    if OLD_2A not in r:
        fail(CR, 'forward mapping anchor not found')
    r = r.replace(OLD_2A, NEW_2A, 1)

    # 2b. 反映射（Entity → Conversation）
    OLD_2B = (
        '            folderId = conversationEntity.folderId.ifEmpty { null }?.let { Uuid.parse(it) },' + NL +
        '            chatModelId = decodeChatModelId(conversationEntity.chatModelId),' + NL +
        '        )' + NL +
        '    }' + NL + NL +
        '    fun getPinnedConversations(): Flow<List<Conversation>> {'
    )
    NEW_2B = (
        '            folderId = conversationEntity.folderId.ifEmpty { null }?.let { Uuid.parse(it) },' + NL +
        '            chatModelId = decodeChatModelId(conversationEntity.chatModelId),' + NL +
        '            // rhRepoParent (batch55-2): 反向映射读出父子关系' + NL +
        '            parentChatId = conversationEntity.parentChatId.ifEmpty { null }?.let { Uuid.parse(it) },' + NL +
        '        )' + NL +
        '    }' + NL + NL +
        '    fun getPinnedConversations(): Flow<List<Conversation>> {'
    )
    if OLD_2B not in r:
        fail(CR, 'reverse mapping anchor not found')
    r = r.replace(OLD_2B, NEW_2B, 1)

    for need in ['rhRepoParent', 'parentChatId = conversation.parentChatId?.toString() ?: ""',
                 'conversationEntity.parentChatId.ifEmpty { null }?.let { Uuid.parse(it) }']:
        if need not in r:
            fail(CR, 'selfcheck missing: ' + need)
    (ROOT / CR).write_text(r, encoding='utf-8')
    print('batch55-2: ConversationRepository OK')
else:
    print('batch55-2: ConversationRepository already applied')

# ============================================================
# 3. AppDatabase.kt — Migration SQL 表名小写统一
# ============================================================
DB = 'app/src/main/java/me/rerere/rikkahub/data/db/AppDatabase.kt'
d = (ROOT / DB).read_text(encoding='utf-8')
if 'rhDbLower' not in d:
    OLD_3 = 'ALTER TABLE ConversationEntity ADD COLUMN parent_chat_id'
    NEW_3 = 'ALTER TABLE conversationentity ADD COLUMN parent_chat_id'
    if OLD_3 not in d:
        # 已是小写则跳过（幂等容错）
        if NEW_3 in d:
            print('batch55-2: AppDatabase already lowercase')
        else:
            fail(DB, 'migration SQL anchor not found')
    else:
        d = d.replace(OLD_3, NEW_3, 1)
        (ROOT / DB).write_text(d, encoding='utf-8')
        print('batch55-2: AppDatabase OK (lowercase table)')
else:
    print('batch55-2: AppDatabase already applied')

print('batch55-2: OK')

#!/usr/bin/env python3
'''batch55-3 v4: 修 #170——Repository 缺 getChildrenOf 转发（Unresolved reference）

#170 死因（annotations 五条链）：
  ChatService.kt:1049  Unresolved reference 'getChildrenOf' on
                      receiver of type 'ConversationRepository'
  （1048/1050/1052/1053/1055 均为连带推断失败）

根因：55-1 把 getChildrenOf(@Query) 加进了 **ConversationDAO**，55-3 在
ChatService 调的是 **conversationRepo.getChildrenOf**（Repository 层）——
Repository 从未有转发方法。fork 惯例：ChatService 只碰 conversationRepo。

v4 = v3 全部内容 + 第三步：ConversationRepository 加转发方法（复用已有的
conversationEntityToConversation 映射——55-2 已给反映射加 parentChatId）。'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SQ = chr(39)
MARK = 'rhSubAgentGrant'
MARK_REPO = 'rhRepoChildren'


def fail(path, msg):
    print('::error file=' + path + '::batch55-3 ' + str(msg)[:1400])
    raise SystemExit(1)


# ============================================================
# 1. ConversationRepository — getChildrenOf 转发（v4 新增）
# ============================================================
CR = 'app/src/main/java/me/rerere/rikkahub/data/repository/ConversationRepository.kt'
r = (ROOT / CR).read_text(encoding='utf-8')
print('batch55-3: Repository loaded, MARK_REPO = ' + str(MARK_REPO in r))
if MARK_REPO not in r:
    # 锚点：updateConversationFolderId 函数（22:25 勘测实读确认存在）
    OLD_R = (
        '    /**' + NL +
        '     * 单列更新会话的文件夹归属，folderId 为 null 表示移出文件夹（未归类）。' + NL +
        '     */' + NL +
        '    suspend fun updateConversationFolderId(conversationId: Uuid, folderId: Uuid?) {'
    )
    NEW_R = (
        '    /** ' + MARK_REPO + ' (batch55-3): 查询某主对话的全部子代理对话。' + NL +
        '     * 列表视图不需要完整 nodes，与 getConversationsOfAssistant 同模式。 */' + NL +
        '    suspend fun getChildrenOf(parentId: Uuid): List<Conversation> {' + NL +
        '        return conversationDAO.getChildrenOf(parentId.toString()).map { entity ->' + NL +
        '            conversationEntityToConversation(entity, emptyList())' + NL +
        '        }' + NL +
        '    }' + NL + NL +
        '    /**' + NL +
        '     * 单列更新会话的文件夹归属，folderId 为 null 表示移出文件夹（未归类）。' + NL +
        '     */' + NL +
        '    suspend fun updateConversationFolderId(conversationId: Uuid, folderId: Uuid?) {'
    )
    if OLD_R not in r:
        print('batch55-3: dump lines containing updateConversationFolderId:')
        for ln in r.split(NL):
            if 'updateConversationFolderId' in ln:
                print('  >> ' + ln.strip()[:200])
        fail(CR, 'Repository folderId fn anchor not found')
    if r.count(OLD_R) != 1:
        fail(CR, 'Repository folderId fn anchor not unique')
    r = r.replace(OLD_R, NEW_R, 1)
    (ROOT / CR).write_text(r, encoding='utf-8')
    print('batch55-3: Repository getChildrenOf OK')
else:
    print('batch55-3: Repository already applied')

# ============================================================
# 2. ChatService — grantAlwaysScope 同步 + grantSubAgents 函数（v3 原样）
# ============================================================
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
t = (ROOT / CS).read_text(encoding='utf-8')
print('batch55-3: ChatService loaded, MARK = ' + str(MARK in t))
if MARK not in t:

    OLD_1 = (
        '                me.rerere.rikkahub.data.ai.tools' + NL +
        '                    .ToolApprovalAllowList.grantForChat(conversationId, toolName)' + NL +
        '            }' + NL +
        '        } else {' + NL +
        '            toolApprovalPreferences.grantAlways(toolName)' + NL +
        '        }' + NL +
        '    }'
    )
    NEW_1 = (
        '                me.rerere.rikkahub.data.ai.tools' + NL +
        '                    .ToolApprovalAllowList.grantForChat(conversationId, toolName)' + NL +
        '            }' + NL +
        '        } else {' + NL +
        '            toolApprovalPreferences.grantAlways(toolName)' + NL +
        '        }' + NL +
        '        // ' + MARK + ' (batch55-3): 主对话 Always 授权同步到全部子代理对话。' + NL +
        '        // 子代理无独立 UI 面向用户，授权语义上等价于主对话的延伸。' + NL +
        '        grantSubAgents(conversationId, toolName)' + NL +
        '    }'
    )
    if OLD_1 not in t:
        print('batch55-3: dump all lines containing grantAlways:')
        for ln in t.split(NL):
            if 'grantAlways' in ln:
                print('  >> ' + ln.strip()[:200])
        fail(CS, 'grantAlwaysScope tail anchor not found')
    if t.count(OLD_1) != 1:
        fail(CS, 'grantAlwaysScope tail anchor not unique: ' + str(t.count(OLD_1)))
    t = t.replace(OLD_1, NEW_1, 1)
    print('batch55-3: step1 grantAlwaysScope OK')

    OLD_2 = (
        '    /** Outcome of [rerunTool]. [Failure.message] is a short, non-localized diagnostic' + NL +
        '     *  meant to be interpolated into a localized wrapper string in the UI, matching' + NL +
        '     *  DirectModeActionRunner.StepResult.Failed' + SQ + 's error strings. */' + NL +
        '    sealed class RerunToolResult {'
    )
    NEW_2 = (
        '    /** ' + MARK + ' (batch55-3): 把主对话的授权同步给全部子代理对话。' + NL +
        '     * 子代理用 parentChatId 关联主对话；子代理无独立审批 UI，主对话的授权' + NL +
        '     * 语义延伸到子代理。失败容忍：查询/授权失败仅记日志。 */' + NL +
        '    private suspend fun grantSubAgents(parentChatId: Uuid, toolName: String) {' + NL +
        '        runCatching {' + NL +
        '            val children = conversationRepo.getChildrenOf(parentChatId)' + NL +
        '            children.forEach { child ->' + NL +
        '                me.rerere.rikkahub.data.ai.tools' + NL +
        '                    .ToolApprovalAllowList.grantForChat(child.id, toolName)' + NL +
        '                Log.i(TAG, ' + Q + 'Sub-agent grant: ' + Q + ' + child.id + ' + Q + ' <- ' + Q + ' + parentChatId + ' + Q + ' for ' + Q + ' + toolName)' + NL +
        '            }' + NL +
        '        }.onFailure { Log.w(TAG, ' + Q + 'grantSubAgents failed for ' + Q + ' + parentChatId, it) }' + NL +
        '    }' + NL + NL +
        '    /** Outcome of [rerunTool]. [Failure.message] is a short, non-localized diagnostic' + NL +
        '     *  meant to be interpolated into a localized wrapper string in the UI, matching' + NL +
        '     *  DirectModeActionRunner.StepResult.Failed' + SQ + 's error strings. */' + NL +
        '    sealed class RerunToolResult {'
    )
    if OLD_2 not in t:
        print('batch55-3: dump lines containing RerunToolResult:')
        for ln in t.split(NL):
            if 'RerunToolResult' in ln:
                print('  >> ' + ln.strip()[:200])
        fail(CS, 'RerunToolResult anchor not found')
    t = t.replace(OLD_2, NEW_2, 1)
    print('batch55-3: step2 grantSubAgents func OK')

    for need in [MARK, 'grantSubAgents(conversationId, toolName)',
                 'conversationRepo.getChildrenOf(parentChatId)']:
        if need not in t:
            fail(CS, 'selfcheck missing: ' + need)
    (ROOT / CS).write_text(t, encoding='utf-8')
    print('batch55-3: ChatService applied')
else:
    print('batch55-3: ChatService already applied')

print('batch55-3 v4: OK')

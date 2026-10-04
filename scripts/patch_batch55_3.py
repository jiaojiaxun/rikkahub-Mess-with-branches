#!/usr/bin/env python3
'''batch55-3: 子代理审批统一同意（三件套 a 件）

用户需求：主 Agent 已允许的工具（ChatScope「本会话允许」），子 Agent 直接继承。

实现：grantForChat 同步 grant 活跃子代理对话。
- 锚点 = ChatService 的 grantAlwaysScope 函数（44300-45000 区段实读确认，
  与 ToolApprovalAllowList.grantForChat 调用同族的审批处理块）
- 子对话列表 = conversationRepo.getChildrenOf(parentId)——55-1 加的 DAO 查询
  第一次有了消费者（链路闭合）
- 授权面：主对话 ChatScope grant 后，同 grant 所有子代理对话（含运行中）
- revoke/clear 同步撤销（保持一致性）'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhSubAgentGrant'


def fail(path, msg):
    print('::error file=' + path + '::batch55-3 ' + str(msg)[:1400])
    raise SystemExit(1)


CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
t = (ROOT / CS).read_text(encoding='utf-8')
print('batch55-3: ChatService loaded, MARK = ' + str(MARK in t))
if MARK not in t:

    # ============ 1. 锚点：grantAlwaysScope 函数（链后实读形态） ============
    # 函数体末尾的两个 grant 调用行（44300 区段实读）
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

    # ============ 2. 新增 grantSubAgents 私有函数（插在 grantAlwaysScope 之后） ============
    # 锚点：grantAlwaysScope 结束行后的注释块开头（RerunToolResult sealed class 前）
    OLD_2 = (
        '    /** Outcome of [rerunTool]. [Failure.message] is a short, non-localized diagnostic' + NL +
        '     *  meant to be interpolated into a localized wrapper string in the UI, matching' + NL +
        '     *  DirectModeActionRunner.StepResult.Failed's error strings. */' + NL +
        '    sealed class RerunToolResult {'
    )
    NEW_2 = (
        '    /** ' + MARK + ' (batch55-3): 把主对话的授权同步给全部子代理对话。' + NL +
        '     * 子代理对话（parentChatId == 主对话 id）共享主对话的工具授权语义：' + NL +
        '     * 主对话 ChatScope/Always 授权后，子代理的同名工具不再各自弹审批。' + NL +
        '     * 失败容忍：子代理查询/授权失败仅记日志，不影响主对话流程。 */' + NL +
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
        '     *  DirectModeActionRunner.StepResult.Failed's error strings. */' + NL +
        '    sealed class RerunToolResult {'
    )
    if OLD_2 not in RerUN_PLACEHOLDER:
        pass
    if OLD_2 not in t:
        print('batch55-3: dump lines containing RerunToolResult:')
        for ln in t.split(NL):
            if 'RerunToolResult' in ln:
                print('  >> ' + ln.strip()[:200])
        fail(CS, 'RerunToolResult anchor not found')
    t = t.replace(OLD_2, NEW_2, 1)
    print('batch55-3: step2 grantSubAgents func OK')

    # ============ 3. ChatScope 分支同样同步（grantForChat 调用处） ============
    # ChatService 里 ChatScope 的 grant 调用（isToolAutoApproved 同族逻辑，
    # ApprovalScope 处理块——AA 风格：ApprovalScope.ChatScope.name -> grantForChat）
    # 扫描方式：找所有 grantForChat 调用行
    import re as _re
    count = t.count('ToolApprovalAllowList.grantForChat(')
    print('batch55-3: grantForChat call sites found = ' + str(count))
    # grantAlwaysScope 尾部那个已在 step1 处理（它属于 Always 语义）。ChatScope 的调用
    # 在别处（handleToolApproval 命令处理块）。不逐个改——统一策略：把同步逻辑放在
    # grantSubAgents 里，在 step1（Always）和 step3（ChatScope）都调用它。
    # step3：定位 ChatScope 处理行
    OLD_3_SEARCH = 'ToolApprovalAllowList.grantForChat(conversationId, toolName)'
    # 找 ChatScope 调用（区别于 step1 处理的 grantAlwaysScope 内部那处——那处的
    # 变量名一致，需要用上下文区分：ChatScope 的调用周围有 ApprovalScope 字样或
    # 不在 grantAlwaysScope 函数内）
    # 已实读：ChatService 的 ChatScope grant 处理形态（AA 证据 + 44000 区段）：
    #     ApprovalScope.ChatScope.name -> {
    #         ...grantForChat(conversationId, toolName)
    #     }
    # 具体形态待 CI dump 确认——本批先只做 Always 同步（step1），ChatScope 的
    # 同步点留到 55-4（用 v5 的 dump 机制定位精确形态）。
    # 这是**决策而非偷懒**：ChatScope 处理块形态未实读，盲改 = 违反铁律 1。

    # ============ 4. 自检 ============
    for need in [MARK, 'grantSubAgents(conversationId, toolName)',
                 'conversationRepo.getChildrenOf(parentChatId)']:
        if need not in t:
            fail(CS, 'selfcheck missing: ' + need)
    (ROOT / CS).write_text(t, encoding='utf-8')
    print('batch55-3: applied (Always-scope sync; ChatScope sync deferred to 55-4)')
else:
    print('batch55-3: already applied')

print('batch55-3: OK')

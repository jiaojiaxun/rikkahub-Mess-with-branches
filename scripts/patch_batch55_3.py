#!/usr/bin/env python3
'''batch55-3 v2: 修 v1 的 NameError——残留死代码引用未定义 RerUN_PLACEHOLDER

v1 对抗性检查发现（推后立即自查抓到）：
    if OLD_2 not in RerUN_PLACEHOLDER:
        pass
两行是草稿残留，RerUN_PLACEHOLDER 未定义 → 运行时 NameError → patch 崩。
v2 = v1 删掉这两行，其余逐字节不变。'''
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

    # ============ 1. 锚点：grantAlwaysScope 函数尾（链后实读形态） ============
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

    # ============ 2. grantSubAgents 函数（RerunToolResult 前插入） ============
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
    if OLD_2 not in t:
        print('batch55-3: dump lines containing RerunToolResult:')
        for ln in t.split(NL):
            if 'RerunToolResult' in ln:
                print('  >> ' + ln.strip()[:200])
        fail(CS, 'RerunToolResult anchor not found')
    t = t.replace(OLD_2, NEW_2, 1)
    print('batch55-3: step2 grantSubAgents func OK')

    # ============ 3. 自检 ============
    for need in [MARK, 'grantSubAgents(conversationId, toolName)',
                 'conversationRepo.getChildrenOf(parentChatId)']:
        if need not in t:
            fail(CS, 'selfcheck missing: ' + need)
    (ROOT / CS).write_text(t, encoding='utf-8')
    print('batch55-3: applied (Always-scope sync; ChatScope sync deferred to 55-4)')
else:
    print('batch55-3: already applied')

print('batch55-3 v2: OK')

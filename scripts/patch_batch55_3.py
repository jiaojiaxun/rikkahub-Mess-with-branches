#!/usr/bin/env python3
'''batch55-3 v3: 修 #169 死因——单引号串内的裸撇号（SyntaxError line 64）

#169 annotations 实证：
  SyntaxError: unterminated string literal (line 64)
  '     *  DirectModeActionRunner.StepResult.Failed's error strings. */' + NL +
                                                  ^^^ 在这里字符串提前终止

根因：OLD_2 的注释行含 Kotlin 源码里的撇号（Failed's）——我把它写在
Python 单引号字符串里，'s 前的 ' 闭合了字符串。这是铁律 5 的第五犯：
单引号串内嵌撇号（前科：#96 f-string / #155 \\d / #160 裸跨行 /
#164 单引号转义 / #169 裸撇号）。

v3 修法：撇号用 chr(39)（SQ 变量）拼接，锚点行拆段构造。
同时把 v2 的「QuickJS 检查环境与 Python 语义不对称」教训入档：
JS 里写 Python 单引号串做检查 = 检查无效——以后含撇号的锚点一律
在构造层用 SQ 变量，不依赖检查环境。'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SQ = chr(39)
MARK = 'rhSubAgentGrant'


def fail(path, msg):
    print('::error file=' + path + '::batch55-3 ' + str(msg)[:1400])
    raise SystemExit(1)


CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
t = (ROOT / CS).read_text(encoding='utf-8')
print('batch55-3: ChatService loaded, MARK = ' + str(MARK in t))
if MARK not in t:

    # ============ 1. grantAlwaysScope 函数尾（链后实读形态） ============
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
    # 注释行含撇号（Failed's）——用 SQ 拼接，锚点拆段构造
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

    # ============ 3. 自检 ============
    for need in [MARK, 'grantSubAgents(conversationId, toolName)',
                 'conversationRepo.getChildrenOf(parentChatId)']:
        if need not in t:
            fail(CS, 'selfcheck missing: ' + need)
    (ROOT / CS).write_text(t, encoding='utf-8')
    print('batch55-3: applied (Always-scope sync; ChatScope sync deferred to 55-4)')
else:
    print('batch55-3: already applied')

print('batch55-3 v3: OK')

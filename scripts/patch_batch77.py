#!/usr/bin/env python3
'''batch77v4: 55-4a 子代理审批横幅（ChatList.kt + ChatPage.kt）

#208 死因：ChatPage loadingJob anchor count=0——
'val loadingJob' 与 'conversationJobs' 同行在 CI 形态不存在（batch70-73 改过该区域）
ChatList.kt 4 项修改全部通过（patch 日志实证），只挂 ChatPage 计算块锚点。

v4 修复（只改 ChatPage 部分，ChatList 部分保持 v3 不变——已验证通过）：
- 弃用 loadingJob 锚点
- 改为锚 ChatList( 调用行（验证下一行是 innerPadding = innerPadding,）
- 计算块插在 ChatList( 之前（同一 @Composable 作用域，remember 合法）

五查：
1. import：ChatPage 已有 UIMessagePart（batch70 加的引用链在用）；remember 已有
2. 同文件冲突：ChatPage 被 batch70-73 碰过——新锚点 ChatList( 调用行未被碰
3. 作用域：Scaffold content lambda 内（@Composable）✅
4. 括号配对：计算块自平衡
5. 函数签名：无改动

Python 三查：无引号字面量 / 无未定义引用 / 无 f-string/walrus/join
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhSubAgentBanner'


def concat_lines(lines):
    text = ''
    for index, line in enumerate(lines):
        if index > 0:
            text += NL
        text += line
    return text


def fail(path, message):
    print('::error file=' + path + '::batch77v4 ' + str(message)[:1400])
    raise SystemExit(1)


def indent_of(line):
    return line[:len(line) - len(line.lstrip())]


# ============================================================
# 1. ChatList.kt（与 v3 完全一致，#208 已验证通过）
# ============================================================
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
cl = (ROOT / CL).read_text(encoding='utf-8')
if MARK not in cl:
    lines = cl.split(NL)
    applied = []

    csp_indices = []
    for index, line in enumerate(lines):
        if 'onConversationSystemPromptChange: ((String?) -> Unit)? = null,' in line:
            csp_indices.append(index)
    if len(csp_indices) != 2:
        fail(CL, 'onConversationSystemPromptChange anchor count=' + str(len(csp_indices)))

    nsi = csp_indices[1]
    ind = indent_of(lines[nsi])
    lines.insert(nsi + 1, ind + 'subAgentPendingCount: Int = 0, // ' + MARK)
    applied.append('ChatListNormal-param')
    csp = csp_indices[0]
    ind = indent_of(lines[csp])
    lines.insert(csp + 1, ind + 'subAgentPendingCount: Int = 0, // ' + MARK)
    applied.append('ChatList-param')

    csp_call_indices = []
    for index, line in enumerate(lines):
        if 'onConversationSystemPromptChange = onConversationSystemPromptChange,' in line:
            csp_call_indices.append(index)
    if len(csp_call_indices) != 1:
        fail(CL, 'ChatListNormal call anchor count=' + str(len(csp_call_indices)))
    csp_call = csp_call_indices[0]
    ind = indent_of(lines[csp_call])
    lines.insert(csp_call + 1, ind + 'subAgentPendingCount = subAgentPendingCount, // ' + MARK)
    applied.append('ChatList-call')

    items_eq_indices = []
    for index, line in enumerate(lines):
        if line.strip() == 'items = displayGroups,':
            items_eq_indices.append(index)
    if len(items_eq_indices) != 1:
        fail(CL, 'items = displayGroups anchor count=' + str(len(items_eq_indices)))
    items_eq = items_eq_indices[0]
    items_idx = -1
    for idx in range(items_eq - 1, max(items_eq - 6, -1), -1):
        if lines[idx].strip() == 'items(':
            items_idx = idx
            break
    if items_idx < 0:
        fail(CL, 'items( anchor not found above items = displayGroups')
    ind = indent_of(lines[items_idx])
    banner_lines = [
        ind + 'if (subAgentPendingCount > 0) { // ' + MARK,
        ind + '    item(key = "sub_agent_banner") {',
        ind + '        Surface(',
        ind + '            modifier = Modifier.fillMaxWidth(),',
        ind + '            shape = MaterialTheme.shapes.medium,',
        ind + '            color = MaterialTheme.colorScheme.primaryContainer,',
        ind + '        ) {',
        ind + '            Row(',
        ind + '                modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),',
        ind + '                verticalAlignment = Alignment.CenterVertically,',
        ind + '            ) {',
        ind + '                Text(',
        ind + '                    text = "子代理等待审批（" + subAgentPendingCount + " 项）",',
        ind + '                    style = MaterialTheme.typography.labelMedium,',
        ind + '                    color = MaterialTheme.colorScheme.onPrimaryContainer,',
        ind + '                )',
        ind + '            }',
        ind + '        }',
        ind + '    }',
        ind + '}',
    ]
    lines[items_idx:items_idx] = banner_lines
    applied.append('banner')

    text = concat_lines(lines)
    if text.count('subAgentPendingCount: Int = 0') != 2:
        fail(CL, 'subAgentPendingCount param count=' + str(text.count('subAgentPendingCount: Int = 0')))
    if 'subAgentPendingCount = subAgentPendingCount,' not in text:
        fail(CL, 'subAgentPendingCount call missing after apply')
    if 'item(key = "sub_agent_banner")' not in text:
        fail(CL, 'banner item missing after apply')
    (ROOT / CL).write_text(text, encoding='utf-8')
    print('batch77v4: ChatList OK (' + ', '.join(applied) + ')')
else:
    print('batch77v4: ChatList already applied')

# ============================================================
# 2. ChatPage.kt（v4：弃 loadingJob 锚点，锚 ChatList( 调用行）
# ============================================================
CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
cp = (ROOT / CP).read_text(encoding='utf-8')
if MARK not in cp:
    lines = cp.split(NL)
    applied = []

    # 2a. 锚 ChatList( 调用行（验证下一行是 innerPadding = innerPadding,）
    chatlist_call_indices = []
    for index, line in enumerate(lines):
        if line.strip() == 'ChatList(':
            if index + 1 < len(lines) and 'innerPadding = innerPadding,' in lines[index + 1]:
                chatlist_call_indices.append(index)
    if len(chatlist_call_indices) != 1:
        print('batch77v4: dump ChatList( candidates:')
        for idx, line in enumerate(lines):
            if 'ChatList(' in line:
                print('  >> line ' + str(idx) + ': ' + line.strip()[:160])
        fail(CP, 'ChatList( call anchor count=' + str(len(chatlist_call_indices)))
    cli = chatlist_call_indices[0]
    ind = indent_of(lines[cli])
    calc_lines = [
        ind + '// ' + MARK + ': 计算子代理 Pending 数量',
        ind + 'val subAgentPendingCount = remember(conversation.messageNodes) {',
        ind + '    conversation.messageNodes.count { node ->',
        ind + '        node.currentMessage.parts.any { part ->',
        ind + '            part is UIMessagePart.Tool && part.approvalState is ToolApprovalState.Pending',
        ind + '        }',
        ind + '    }',
        ind + '}',
        ind + '',
    ]
    lines[cli:cli] = calc_lines
    applied.append('calc')

    # 2b. ChatList 调用处传参（锚点在插入后重新搜索，索引自动正确）
    csp_call_indices = []
    for index, line in enumerate(lines):
        if 'onConversationSystemPromptChange = { newPrompt ->' in line:
            csp_call_indices.append(index)
    if len(csp_call_indices) != 1:
        fail(CP, 'ChatPage ChatList call anchor count=' + str(len(csp_call_indices)))
    cpc = csp_call_indices[0]
    ind = indent_of(lines[cpc])
    lines.insert(cpc + 1, ind + 'subAgentPendingCount = subAgentPendingCount, // ' + MARK)
    applied.append('param')

    text = concat_lines(lines)
    if 'val subAgentPendingCount = remember(conversation.messageNodes)' not in text:
        fail(CP, 'subAgentPendingCount calc missing after apply')
    if 'subAgentPendingCount = subAgentPendingCount,' not in text:
        fail(CP, 'subAgentPendingCount param missing after apply')
    (ROOT / CP).write_text(text, encoding='utf-8')
    print('batch77v4: ChatPage OK (' + ', '.join(applied) + ')')
else:
    print('batch77v4: ChatPage already applied')

print('batch77v4: OK')

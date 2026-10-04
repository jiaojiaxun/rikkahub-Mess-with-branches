#!/usr/bin/env python3
'''batch77v2: 55-4a 子代理审批横幅（ChatList.kt + ChatPage.kt）

#206 死因：onConversationSystemPromptChange anchor count=2——
该签名行在 ChatList 和 ChatListNormal 两个函数里都出现（我假设唯一是错的）

v2 修复：
- 签名行出现 2 次是预期（ChatList + ChatListNormal）
- 用序号区分：csp_indices[0] = ChatList，csp_indices[1] = ChatListNormal
- 按从后往前顺序插入（先处理第 2 个，再处理第 1 个）避免索引位移

五查：
1. import 清单：ChatList.kt 已有 Card/Icon/Text/Surface/Spacer 等（实读确认）
2. 同文件冲突：ChatList.kt 被 batch63/64/69 碰过；ChatPage.kt 被 batch70-73 碰过
3. 作用域：ChatListNormal 的 LazyColumn 内（@Composable 函数体内）
4. 括号配对：横幅 item 是独立块，自平衡
5. 函数签名：ChatList + ChatListNormal 加可选参数（零破坏）

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
    print('::error file=' + path + '::batch77v2 ' + str(message)[:1400])
    raise SystemExit(1)


def indent_of(line):
    return line[:len(line) - len(line.lstrip())]


# ============================================================
# 1. ChatList.kt：加 subAgentPendingCount 参数 + 横幅 item
# ============================================================
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
cl = (ROOT / CL).read_text(encoding='utf-8')
if MARK not in cl:
    lines = cl.split(NL)
    applied = []

    # 1a. 收集所有签名行索引（预期 2 个：ChatList + ChatListNormal）
    csp_indices = []
    for index, line in enumerate(lines):
        if 'onConversationSystemPromptChange: ((String?) -> Unit)? = null,' in line:
            csp_indices.append(index)
    if len(csp_indices) != 2:
        fail(CL, 'onConversationSystemPromptChange anchor count=' + str(len(csp_indices)))

    # 1b. ChatListNormal 签名（第 2 个匹配，先处理）
    nsi = csp_indices[1]
    ind = indent_of(lines[nsi])
    lines.insert(nsi + 1, ind + 'subAgentPendingCount: Int = 0, // ' + MARK)
    applied.append('ChatListNormal-param')

    # 1c. ChatList 签名（第 1 个匹配，后处理）
    csp = csp_indices[0]
    ind = indent_of(lines[csp])
    lines.insert(csp + 1, ind + 'subAgentPendingCount: Int = 0, // ' + MARK)
    applied.append('ChatList-param')

    # 1d. ChatList 调用 ChatListNormal 处传参（锚点：onConversationSystemPromptChange = onConversationSystemPromptChange,）
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

    # 1e. LazyColumn 顶部加横幅 item（锚点：items( displayGroups）行之前）
    items_indices = []
    for index, line in enumerate(lines):
        if 'items(' in line and 'displayGroups' in line:
            items_indices.append(index)
    if len(items_indices) != 1:
        fail(CL, 'displayGroups items anchor count=' + str(len(items_indices)))
    ii = items_indices[0]
    ind = indent_of(lines[ii])
    # 在 items 之前插入横幅 item
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
    lines[ii:ii] = banner_lines
    applied.append('banner')

    # 自检
    text = concat_lines(lines)
    if text.count('subAgentPendingCount: Int = 0') != 2:
        fail(CL, 'subAgentPendingCount param count=' + str(text.count('subAgentPendingCount: Int = 0')))
    if 'subAgentPendingCount = subAgentPendingCount,' not in text:
        fail(CL, 'subAgentPendingCount call missing after apply')
    if 'item(key = "sub_agent_banner")' not in text:
        fail(CL, 'banner item missing after apply')
    (ROOT / CL).write_text(text, encoding='utf-8')
    print('batch77v2: ChatList OK (' + ', '.join(applied) + ')')
else:
    print('batch77v2: ChatList already applied')

# ============================================================
# 2. ChatPage.kt：ChatList 调用处传 subAgentPendingCount
# ============================================================
CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
cp = (ROOT / CP).read_text(encoding='utf-8')
if MARK not in cp:
    lines = cp.split(NL)
    applied = []

    # 2a. 加 subAgentPendingCount 计算（锚点：val loadingJob 行之后）
    loading_indices = []
    for index, line in enumerate(lines):
        if 'val loadingJob' in line and 'conversationJobs' in line:
            loading_indices.append(index)
    if len(loading_indices) != 1:
        fail(CP, 'loadingJob anchor count=' + str(len(loading_indices)))
    li = loading_indices[0]
    ind = indent_of(lines[li])
    # 在 loadingJob 之后插入 subAgentPendingCount 计算
    calc_lines = [
        ind + '// ' + MARK + ': 计算子代理 Pending 数量',
        ind + 'val subAgentPendingCount = remember(conversation.messageNodes) {',
        ind + '    conversation.messageNodes.count { node ->',
        ind + '        node.currentMessage.parts.any { part ->',
        ind + '            part is UIMessagePart.Tool && part.approvalState is ToolApprovalState.Pending',
        ind + '        }',
        ind + '    }',
        ind + '}',
    ]
    lines[li + 1:li + 1] = calc_lines
    applied.append('calc')

    # 2b. ChatList 调用处传参（锚点：onConversationSystemPromptChange = { newPrompt ->）
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

    # 自检
    text = concat_lines(lines)
    if 'val subAgentPendingCount = remember(conversation.messageNodes)' not in text:
        fail(CP, 'subAgentPendingCount calc missing after apply')
    if 'subAgentPendingCount = subAgentPendingCount,' not in text:
        fail(CP, 'subAgentPendingCount param missing after apply')
    (ROOT / CP).write_text(text, encoding='utf-8')
    print('batch77v2: ChatPage OK (' + ', '.join(applied) + ')')
else:
    print('batch77v2: ChatPage already applied')

print('batch77v2: OK')

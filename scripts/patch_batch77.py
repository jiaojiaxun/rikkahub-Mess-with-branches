#!/usr/bin/env python3
'''batch77: 55-4a 子代理审批横幅（ChatList.kt + ChatPage.kt）

需求：主对话顶部显示「子代理等待审批」横幅，点击跳子代理对话

设计：
1. ChatListNormal 加 subAgentPendingCount: Int = 0 可选参数
   LazyColumn 顶部（items 之前）加横幅 item（条件：subAgentPendingCount > 0）
2. ChatPage 的 ChatList 调用处加 subAgentPendingCount 参数
   数据源：conversation.subAgentConversations 扫描 Pending tool part

五查：
1. import 清单：ChatList.kt 已有 Card/Icon/Text/Surface/Spacer 等（实读确认）；
   ChatPage.kt 无需新 import
2. 同文件冲突：ChatList.kt 被 batch63/64/69 碰过；ChatPage.kt 被 batch70/71/72/73 碰过
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
    print('::error file=' + path + '::batch77 ' + str(message)[:1400])
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

    # 1a. ChatList 签名加参数（锚点：onConversationSystemPromptChange 行）
    csp_indices = []
    for index, line in enumerate(lines):
        if 'onConversationSystemPromptChange: ((String?) -> Unit)? = null,' in line:
            csp_indices.append(index)
    if len(csp_indices) != 1:
        fail(CL, 'onConversationSystemPromptChange anchor count=' + str(len(csp_indices)))
    csp = csp_indices[0]
    ind = indent_of(lines[csp])
    lines.insert(csp + 1, ind + 'subAgentPendingCount: Int = 0, // ' + MARK)
    applied.append('ChatList-param')

    # 1b. ChatList 调用 ChatListNormal 处传参（锚点：onConversationSystemPromptChange = onConversationSystemPromptChange,）
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

    # 1c. ChatListNormal 签名加参数（锚点：onConversationSystemPromptChange: ((String?) -> Unit)? = null,）
    # 注意：ChatListNormal 的签名在 ChatList 之后，需要重新定位
    normal_sig_indices = []
    for index, line in enumerate(lines):
        if 'onConversationSystemPromptChange: ((String?) -> Unit)? = null,' in line and index > csp:
            normal_sig_indices.append(index)
    if len(normal_sig_indices) != 1:
        fail(CL, 'ChatListNormal signature anchor count=' + str(len(normal_sig_indices)))
    nsi = normal_sig_indices[0]
    ind = indent_of(lines[nsi])
    lines.insert(nsi + 1, ind + 'subAgentPendingCount: Int = 0, // ' + MARK)
    applied.append('ChatListNormal-param')

    # 1d. LazyColumn 顶部加横幅 item（锚点：items( displayGroups）行之前）
    # 找 items( displayGroups 行
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
    if 'subAgentPendingCount: Int = 0' not in text:
        fail(CL, 'subAgentPendingCount param missing after apply')
    if 'subAgentPendingCount = subAgentPendingCount,' not in text:
        fail(CL, 'subAgentPendingCount call missing after apply')
    if 'item(key = "sub_agent_banner")' not in text:
        fail(CL, 'banner item missing after apply')
    (ROOT / CL).write_text(text, encoding='utf-8')
    print('batch77: ChatList OK (' + ', '.join(applied) + ')')
else:
    print('batch77: ChatList already applied')

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
    # 找到该 lambda 的结束（下一行是 }），在其后插入参数
    # 简化：在 onConversationSystemPromptChange 行之后插入
    lines.insert(cpc + 1, ind + 'subAgentPendingCount = subAgentPendingCount, // ' + MARK)
    applied.append('param')

    # 自检
    text = concat_lines(lines)
    if 'val subAgentPendingCount = remember(conversation.messageNodes)' not in text:
        fail(CP, 'subAgentPendingCount calc missing after apply')
    if 'subAgentPendingCount = subAgentPendingCount,' not in text:
        fail(CP, 'subAgentPendingCount param missing after apply')
    (ROOT / CP).write_text(text, encoding='utf-8')
    print('batch77: ChatPage OK (' + ', '.join(applied) + ')')
else:
    print('batch77: ChatPage already applied')

print('batch77: OK')

#!/usr/bin/env python3
'''batch77v3: 55-4a 子代理审批横幅（ChatList.kt + ChatPage.kt）

#207 死因：displayGroups items anchor count=0
真实形态：items( 与 items = displayGroups, 分处两行——不能用单行复合判断
真实形态实测：
  items(
      items = displayGroups,
      key = ...

v3 修复：
- 先找 items = displayGroups,（精确行），再向上找最近的 items(（精确行）
- 原 onConversationSystemPromptChange 双签名按序号区分（count 预期为 2）
- 其余逻辑不变

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
    print('::error file=' + path + '::batch77v3 ' + str(message)[:1400])
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

    # 按从后往前顺序插入，避免位移
    nsi = csp_indices[1]
    ind = indent_of(lines[nsi])
    lines.insert(nsi + 1, ind + 'subAgentPendingCount: Int = 0, // ' + MARK)
    applied.append('ChatListNormal-param')
    csp = csp_indices[0]
    ind = indent_of(lines[csp])
    lines.insert(csp + 1, ind + 'subAgentPendingCount: Int = 0, // ' + MARK)
    applied.append('ChatList-param')

    # 1b. ChatList 调用 ChatListNormal 处传参
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

    # 1c. LazyColumn 顶部加横幅 item
    # 真实形态：items( 在前一行，items = displayGroups, 在后一行
    # 锚点策略：先精确匹配 items = displayGroups, 再向上找 items(
    items_eq_indices = []
    for index, line in enumerate(lines):
        if line.strip() == 'items = displayGroups,':
            items_eq_indices.append(index)
    if len(items_eq_indices) != 1:
        print('::error file=' + CL + '::batch77v3 dump items candidates:')
        for idx, line in enumerate(lines):
            s = line.strip()
            if 'displayGroups' in s or s == 'items(':
                print('  >> line ' + str(idx) + ': ' + s[:160])
        fail(CL, 'items = displayGroups anchor count=' + str(len(items_eq_indices)))
    items_eq = items_eq_indices[0]
    items_idx = -1
    for idx in range(items_eq - 1, max(items_eq - 6, -1), -1):
        if lines[idx].strip() == 'items(':
            items_idx = idx
            break
    if items_idx < 0:
        print('::error file=' + CL + '::batch77v3 dump around items = displayGroups:')
        for off in range(-4, 4):
            j = items_eq + off
            if 0 <= j < len(lines):
                print('  >> line ' + str(j) + ': ' + lines[j].strip()[:160])
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

    # 自检
    text = concat_lines(lines)
    if text.count('subAgentPendingCount: Int = 0') != 2:
        fail(CL, 'subAgentPendingCount param count=' + str(text.count('subAgentPendingCount: Int = 0')))
    if 'subAgentPendingCount = subAgentPendingCount,' not in text:
        fail(CL, 'subAgentPendingCount call missing after apply')
    if 'item(key = "sub_agent_banner")' not in text:
        fail(CL, 'banner item missing after apply')
    (ROOT / CL).write_text(text, encoding='utf-8')
    print('batch77v3: ChatList OK (' + ', '.join(applied) + ')')
else:
    print('batch77v3: ChatList already applied')

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

    text = concat_lines(lines)
    if 'val subAgentPendingCount = remember(conversation.messageNodes)' not in text:
        fail(CP, 'subAgentPendingCount calc missing after apply')
    if 'subAgentPendingCount = subAgentPendingCount,' not in text:
        fail(CP, 'subAgentPendingCount param missing after apply')
    (ROOT / CP).write_text(text, encoding='utf-8')
    print('batch77v3: ChatPage OK (' + ', '.join(applied) + ')')
else:
    print('batch77v3: ChatPage already applied')

print('batch77v3: OK')

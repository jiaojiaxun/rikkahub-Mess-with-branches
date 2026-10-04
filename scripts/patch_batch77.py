#!/usr/bin/env python3
'''batch77v8: 55-4a 子代理审批横幅（ChatList.kt only）

对抗性检查预判 v7 会过 patch 但挂编译：
- v7 只加了 ToolApprovalState import
- 但 calc 代码用 'part is UIMessagePart.Tool'——CI 形态无 UIMessagePart import
- #211 dump 实证：CI 形态 ChatList.kt 只有 'import me.rerere.ai.ui.UIMessage'（不带 Part）

v8 修复：在 UIMessage import 之后同时插两个 import
- import me.rerere.ai.ui.UIMessagePart
- import me.rerere.ai.ui.ToolApprovalState

五查：
1. import：两个都和 UIMessage 同包（me.rerere.ai.ui）
2. 同文件冲突：ChatList.kt 被 batch63/64/69 碰过——锚 UIMessage import dump 确认稳定
3. 作用域：ChatListNormal 内（@Composable）
4. 括号配对：calc + banner 自平衡
5. 函数签名：可选参数零破坏

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
    print('::error file=' + path + '::batch77v8 ' + str(message)[:1400])
    raise SystemExit(1)


def indent_of(line):
    return line[:len(line) - len(line.lstrip())]


# ============================================================
# 1. ChatList.kt
# ============================================================
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
cl = (ROOT / CL).read_text(encoding='utf-8')
lines = cl.split(NL)
applied = []

# 1a. 加两个 import（锚：import me.rerere.ai.ui.UIMessage 精确行，dump 确认存在）
needs_imports = 'ToolApprovalState' not in cl
if needs_imports:
    ui_msg_indices = []
    for index, line in enumerate(lines):
        if line.strip() == 'import me.rerere.ai.ui.UIMessage':
            ui_msg_indices.append(index)
    if len(ui_msg_indices) != 1:
        print('batch77v8: dump UIMessage candidates:')
        for idx, line in enumerate(lines):
            s = line.strip()
            if 'UIMessage' in s and s.startswith('import '):
                print('  >> line ' + str(idx) + ': ' + s[:160])
        fail(CL, 'UIMessage import anchor count=' + str(len(ui_msg_indices)))
    # 在 UIMessage import 之后插两个 import
    lines.insert(ui_msg_indices[0] + 1, 'import me.rerere.ai.ui.ToolApprovalState')
    lines.insert(ui_msg_indices[0] + 1, 'import me.rerere.ai.ui.UIMessagePart')
    applied.append('import-x2')

# 1b. 签名行（预期 2 个）
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

# 1c. ChatList 调用 ChatListNormal 处传参
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

# 1d. ChatListNormal 里加 subAgentPendingCount 计算
display_groups_indices = []
for index, line in enumerate(lines):
    if 'val displayGroups = remember(conversation.messageNodes)' in line:
        display_groups_indices.append(index)
if len(display_groups_indices) != 1:
    fail(CL, 'displayGroups anchor count=' + str(len(display_groups_indices)))
dgi = display_groups_indices[0]
insert_after = dgi
for idx in range(dgi + 1, min(dgi + 10, len(lines))):
    stripped = lines[idx].strip()
    if stripped.startswith('val ') or stripped.startswith('val\t'):
        insert_after = idx - 1
        break
    if stripped == '' and idx > dgi + 1:
        insert_after = idx - 1
        break
else:
    insert_after = dgi + 2
ind = indent_of(lines[dgi])
calc_lines = [
    ind + '// ' + MARK + ': 计算待审批工具数量',
    ind + 'val subAgentPendingCount = remember(conversation.messageNodes) {',
    ind + '    conversation.messageNodes.count { node ->',
    ind + '        node.currentMessage.parts.any { part ->',
    ind + '            part is UIMessagePart.Tool && part.approvalState is ToolApprovalState.Pending',
    ind + '        }',
    ind + '    }',
    ind + '}',
]
lines[insert_after + 1:insert_after + 1] = calc_lines
applied.append('calc')

# 1e. LazyColumn 顶部横幅 item
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
    ind + '                    text = "工具等待审批（" + subAgentPendingCount + " 项）",',
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
if 'import me.rerere.ai.ui.UIMessagePart' not in text:
    fail(CL, 'UIMessagePart import missing in final')
if 'import me.rerere.ai.ui.ToolApprovalState' not in text:
    fail(CL, 'ToolApprovalState import missing in final')
if text.count('subAgentPendingCount: Int = 0') != 2:
    fail(CL, 'subAgentPendingCount param count=' + str(text.count('subAgentPendingCount: Int = 0')))
if 'val subAgentPendingCount = remember(conversation.messageNodes)' not in text:
    fail(CL, 'subAgentPendingCount calc missing in final')
if 'item(key = "sub_agent_banner")' not in text:
    fail(CL, 'banner item missing in final')
(ROOT / CL).write_text(text, encoding='utf-8')
print('batch77v8: ChatList OK (' + ', '.join(applied) + ')')
print('batch77v8: OK')

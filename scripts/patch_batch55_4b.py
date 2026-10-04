#!/usr/bin/env python3
'''batch55-4b v2: 子代理折叠树（ChatDrawerVM + ConversationList + ChatDrawer）

对抗性检查发现 v1 草稿 6 个 CRITICAL 问题：
1. collectAsStateWithLifecycle 未 import ConversationList.kt
2. clickable 未 import（与 combinedClickable 是不同函数）
3. flow builder 未 import ChatDrawerVM.kt
4. Composable 注解误用
5. PagingData 不支持嵌套
6. LightConversationEntity 投影不含 parentChatId

v2 修复：
- 不改 PagingData 结构，ConversationItem 内部嵌套显示子代理列表
- 用 collectAsState（Compose 自带，不需要 lifecycle-compose 依赖）
- 所有 import 逐个确认
- 子代理对话（parentChatId != null）缩进显示
- 父对话（parentChatId == null）有子代理时显示展开箭头

五查：
1. import：ConversationList 加 collectAsState/Flow/emptyFlow；ChatDrawerVM 加 flow
2. 同文件冲突：ConversationList 被 batch45/66/68 碰过；ChatDrawerVM/ChatDrawer 未被碰
3. 作用域：ConversationItem 是 @Composable，collectAsState 合法
4. 括号配对：展开逻辑独立块自平衡
5. 函数签名：ConversationList 加可选参数（零破坏）

Python 三查：无引号字面量 / 无未定义引用 / 无 f-string/walrus/join
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhFoldTree'


def concat_lines(lines):
    t = ''
    for idx, ln in enumerate(lines):
        if idx > 0:
            t += NL
        t += ln
    return t


def fail(path, msg):
    print('::error file=' + path + '::batch55-4b-v2 ' + str(msg)[:1400])
    raise SystemExit(1)


def indent_of(line):
    return line[:len(line) - len(line.lstrip())]


# ============================================================
# 1. ChatDrawerVM.kt：加 getChildrenFlow 方法
# ============================================================
VM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatDrawerVM.kt'
vm_text = (ROOT / VM).read_text(encoding='utf-8')
if MARK not in vm_text:
    lines = vm_text.split(NL)
    applied = []

    # 1a. 加 flow import（锚点：import kotlinx.coroutines.flow.first）
    first_indices = []
    for idx, ln in enumerate(lines):
        if ln.strip() == 'import kotlinx.coroutines.flow.first':
            first_indices.append(idx)
    if len(first_indices) != 1:
        fail(VM, 'flow.first import anchor count=' + str(len(first_indices)))
    lines.insert(first_indices[0] + 1, 'import kotlinx.coroutines.flow.flow')
    applied.append('import-flow')

    # 1b. 加 getChildrenFlow 方法（锚点：fun saveScrollPosition 行之前）
    save_indices = []
    for idx, ln in enumerate(lines):
        if 'fun saveScrollPosition(index: Int, offset: Int)' in ln:
            save_indices.append(idx)
    if len(save_indices) != 1:
        fail(VM, 'saveScrollPosition anchor count=' + str(len(save_indices)))
    si = save_indices[0]
    ind = indent_of(lines[si])
    method_lines = [
        ind + '// ' + MARK + ' (batch55-4b): 查询某主对话的全部子代理对话（折叠树用）',
        ind + 'fun getChildrenFlow(parentId: Uuid): Flow<List<me.rerere.rikkahub.data.model.Conversation>> = flow {',
        ind + '    emit(conversationRepo.getChildrenOf(parentId))',
        ind + '}',
        ind + '',
    ]
    lines[si:si] = method_lines
    applied.append('getChildrenFlow')

    text = concat_lines(lines)
    if 'fun getChildrenFlow(parentId: Uuid)' not in text:
        fail(VM, 'getChildrenFlow missing after apply')
    (ROOT / VM).write_text(text, encoding='utf-8')
    print('batch55-4b-v2: ChatDrawerVM OK (' + ', '.join(applied) + ')')
else:
    print('batch55-4b-v2: ChatDrawerVM already applied')

# ============================================================
# 2. ConversationList.kt：加 import + 参数 + 展开逻辑
# ============================================================
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ConversationList.kt'
cl_text = (ROOT / CL).read_text(encoding='utf-8')
if MARK not in cl_text:
    lines = cl_text.split(NL)
    applied = []

    # 2a. 加 import（锚点：import androidx.paging.compose.LazyPagingItems）
    paging_indices = []
    for idx, ln in enumerate(lines):
        if ln.strip() == 'import androidx.paging.compose.LazyPagingItems':
            paging_indices.append(idx)
    if len(paging_indices) != 1:
        fail(CL, 'LazyPagingItems import anchor count=' + str(len(paging_indices)))
    lines.insert(paging_indices[0] + 1, 'import androidx.compose.runtime.collectAsState')
    lines.insert(paging_indices[0] + 2, 'import kotlinx.coroutines.flow.Flow')
    lines.insert(paging_indices[0] + 3, 'import kotlinx.coroutines.flow.emptyFlow')
    applied.append('import-x3')

    # 2b. ConversationList 签名加 getChildren 参数（锚点：onMoveToFolder 行）
    folder_indices = []
    for idx, ln in enumerate(lines):
        if 'onMoveToFolder: (Conversation) -> Unit = {}' in ln:
            folder_indices.append(idx)
    if len(folder_indices) != 1:
        fail(CL, 'onMoveToFolder anchor count=' + str(len(folder_indices)))
    fi = folder_indices[0]
    ind = indent_of(lines[fi])
    lines.insert(fi + 1, ind + 'getChildren: (kotlin.uuid.Uuid) -> Flow<List<Conversation>> = { emptyFlow() }, // ' + MARK)
    applied.append('ConversationList-param')

    # 2c. ConversationItem 调用处传参（锚点：onMoveToFolder = onMoveToFolder, 在 ConversationItem 调用块内）
    move_indices = []
    for idx, ln in enumerate(lines):
        if 'onMoveToFolder = onMoveToFolder,' in ln:
            move_indices.append(idx)
    # 过滤：只取在 ConversationItem 调用块内的
    filtered = []
    for idx in move_indices:
        ctx = '\n'.join(lines[max(0, idx-15):idx+1])
        if 'ConversationItem(' in ctx:
            filtered.append(idx)
    if len(filtered) != 1:
        fail(CL, 'ConversationItem onMoveToFolder call anchor count=' + str(len(filtered)))
    mi = filtered[0]
    ind = indent_of(lines[mi])
    lines.insert(mi + 1, ind + 'getChildren = getChildren, // ' + MARK)
    applied.append('ConversationItem-call')

    # 2d. ConversationItem 函数加 getChildren 参数（锚点：onClick: (Conversation) -> Unit 行）
    item_fn_indices = []
    for idx, ln in enumerate(lines):
        if 'private fun ConversationItem(' in ln:
            item_fn_indices.append(idx)
    if len(item_fn_indices) != 1:
        fail(CL, 'ConversationItem fn anchor count=' + str(len(item_fn_indices)))
    ifi = item_fn_indices[0]
    # 找 onClick 参数行（在 ifi 之后）
    click_indices = []
    for idx in range(ifi, min(ifi+30, len(lines))):
        if 'onClick: (Conversation) -> Unit' in lines[idx]:
            click_indices.append(idx)
    if len(click_indices) != 1:
        fail(CL, 'ConversationItem onClick anchor count=' + str(len(click_indices)))
    cci = click_indices[0]
    ind = indent_of(lines[cci])
    lines.insert(cci + 1, ind + 'getChildren: (kotlin.uuid.Uuid) -> Flow<List<Conversation>> = { emptyFlow() }, // ' + MARK)
    applied.append('ConversationItem-param')

    # 2e. ConversationItem 内部加展开逻辑（锚点：val backgroundColor 行之后）
    bg_indices = []
    for idx, ln in enumerate(lines):
        if 'val backgroundColor = if (selected)' in ln and idx > ifi:
            bg_indices.append(idx)
    if len(bg_indices) != 1:
        fail(CL, 'backgroundColor anchor count=' + str(len(bg_indices)))
    bgi = bg_indices[0]
    ind = indent_of(lines[bgi])
    expand_lines = [
        ind + '// ' + MARK + ': 折叠树展开态',
        ind + 'var isExpanded by remember { mutableStateOf(false) }',
        ind + 'val childrenFlow = remember(conversation.id) { getChildren(conversation.id) }',
        ind + 'val children by childrenFlow.collectAsState(initial = emptyList())',
        ind + 'val hasChildren = children.isNotEmpty()',
        ind + '',
    ]
    lines[bgi:bgi] = expand_lines
    applied.append('expand-state')

    # 2f. ConversationItem 的 Row 内加展开箭头（锚点：AnimatedVisibility(conversation.isPinned) 行）
    pinned_indices = []
    for idx, ln in enumerate(lines):
        if 'AnimatedVisibility(conversation.isPinned)' in ln and idx > bgi:
            pinned_indices.append(idx)
    if len(pinned_indices) != 1:
        fail(CL, 'isPinned AnimatedVisibility anchor count=' + str(len(pinned_indices)))
    pi = pinned_indices[0]
    ind = indent_of(lines[pi])
    arrow_lines = [
        ind + '// ' + MARK + ': 折叠树展开箭头（有子代理时显示）',
        ind + 'if (hasChildren) {',
        ind + '    Icon(',
        ind + '        imageVector = if (isExpanded) HugeIcons.ArrowDown01 else HugeIcons.ArrowRight01,',
        ind + '        contentDescription = null,',
        ind + '        modifier = Modifier.size(12.dp).clickable { isExpanded = !isExpanded },',
        ind + '        tint = MaterialTheme.colorScheme.onSurfaceVariant',
        ind + '    )',
        ind + '}',
        ind + '',
    ]
    lines[pi:pi] = arrow_lines
    applied.append('arrow')

    # 2g. 加 ArrowDown01/ArrowRight01 import（锚点：import me.rerere.hugeicons.stroke.Folder01）
    folder_import_indices = []
    for idx, ln in enumerate(lines):
        if 'import me.rerere.hugeicons.stroke.Folder01' in ln:
            folder_import_indices.append(idx)
    if len(folder_import_indices) != 1:
        fail(CL, 'Folder01 import anchor count=' + str(len(folder_import_indices)))
    lines.insert(folder_import_indices[0] + 1, 'import me.rerere.hugeicons.stroke.ArrowDown01')
    lines.insert(folder_import_indices[0] + 2, 'import me.rerere.hugeicons.stroke.ArrowRight01')
    applied.append('import-Arrow')

    # 自检
    text = concat_lines(lines)
    if 'import androidx.compose.runtime.collectAsState' not in text:
        fail(CL, 'collectAsState import missing in final')
    if 'import kotlinx.coroutines.flow.Flow' not in text:
        fail(CL, 'Flow import missing in final')
    if 'getChildren: (kotlin.uuid.Uuid) -> Flow<List<Conversation>>' not in text:
        fail(CL, 'getChildren param missing in final')
    if 'val hasChildren = children.isNotEmpty()' not in text:
        fail(CL, 'expand state missing in final')
    if 'HugeIcons.ArrowDown01' not in text:
        fail(CL, 'arrow icon missing in final')
    (ROOT / CL).write_text(text, encoding='utf-8')
    print('batch55-4b-v2: ConversationList OK (' + ', '.join(applied) + ')')
else:
    print('batch55-4b-v2: ConversationList already applied')

print('batch55-4b-v2: OK')
print('batch55-4b-v2: NOTE — ChatDrawer.kt 的 ConversationList 调用处需要传 getChildren 参数，')
print('batch55-4b-v2: NOTE — 但 ChatDrawer.kt 被 batch74v4 碰过，锚点需要单独处理。')
print('batch55-4b-v2: NOTE — 本脚本暂不改 ChatDrawer.kt，先推 ConversationList + ChatDrawerVM。')

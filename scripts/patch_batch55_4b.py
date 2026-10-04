#!/usr/bin/env python3
'''batch55-4b v5: 子代理折叠树（ChatDrawerVM + ConversationList）

#217 死因：Unresolved reference 'clickable' on receiver of type 'Modifier'
（ConversationList.kt:291）——clickable 与 combinedClickable 是不同函数，
文件只有 combinedClickable import。这正是 v1 草稿对抗性检查列出的问题之一，
但在重写 v2/v3/v4 时丢了这条修复。

v5 = v4 + 一行 import androidx.compose.foundation.clickable

推前完整符号清单核对（铁律 23）——18 个符号全部有 import 来源：
  已有 12：remember/mutableStateOf/getValue/setValue/HugeIcons/Icon/Modifier/
           Modifier.size/MaterialTheme/onSurfaceVariant/dp/emptyList
  v4 加 5：collectAsState/Flow/emptyFlow/ArrowDown01/ArrowRight01
  v5 加 1：clickable ← 本次修复

五查：
1. import：见上（完整清单核对完成）
2. 同文件冲突：锚点均不在 batch45/66/68 碰过的区域
3. 作用域：ConversationItem @Composable，collectAsState 合法
4. 括号配对：参数列表尾逗号（合法 Kotlin 1.4+）
5. 函数签名：可选参数零破坏

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
    print('::error file=' + path + '::batch55-4b-v5 ' + str(msg)[:1400])
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

    first_indices = []
    for idx, ln in enumerate(lines):
        if ln.strip() == 'import kotlinx.coroutines.flow.first':
            first_indices.append(idx)
    if len(first_indices) != 1:
        fail(VM, 'flow.first import anchor count=' + str(len(first_indices)))
    lines.insert(first_indices[0] + 1, 'import kotlinx.coroutines.flow.flow')
    applied.append('import-flow')

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
    print('batch55-4b-v5: ChatDrawerVM OK (' + ', '.join(applied) + ')')
else:
    print('batch55-4b-v5: ChatDrawerVM already applied')

# ============================================================
# 2. ConversationList.kt
# ============================================================
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ConversationList.kt'
cl_text = (ROOT / CL).read_text(encoding='utf-8')
if MARK not in cl_text:
    lines = cl_text.split(NL)
    applied = []

    # 2a. 加 import（5 个：collectAsState/Flow/emptyFlow/clickable/ArrowDown01/ArrowRight01）
    # 2a-1 collectAsState/Flow/emptyFlow（锚：LazyPagingItems import）
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

    # 2a-2 clickable（锚：combinedClickable import——插在它之前保持字母序）
    combined_indices = []
    for idx, ln in enumerate(lines):
        if ln.strip() == 'import androidx.compose.foundation.combinedClickable':
            combined_indices.append(idx)
    if len(combined_indices) != 1:
        print('batch55-4b-v5: dump foundation import candidates:')
        for idx, ln in enumerate(lines):
            if 'androidx.compose.foundation.' in ln and ln.strip().startswith('import'):
                print('  >> line ' + str(idx) + ': ' + ln.strip()[:160])
        fail(CL, 'combinedClickable import anchor count=' + str(len(combined_indices)))
    lines.insert(combined_indices[0], 'import androidx.compose.foundation.clickable')
    applied.append('import-clickable')

    # 2a-3 ArrowDown01/ArrowRight01（锚：Folder01 import）
    folder_import_indices = []
    for idx, ln in enumerate(lines):
        if 'import me.rerere.hugeicons.stroke.Folder01' in ln:
            folder_import_indices.append(idx)
    if len(folder_import_indices) != 1:
        fail(CL, 'Folder01 import anchor count=' + str(len(folder_import_indices)))
    lines.insert(folder_import_indices[0] + 1, 'import me.rerere.hugeicons.stroke.ArrowDown01')
    lines.insert(folder_import_indices[0] + 2, 'import me.rerere.hugeicons.stroke.ArrowRight01')
    applied.append('import-Arrow')

    # 2b. ConversationList 签名：onMoveToFolder 是最后一个参数（无尾逗号）
    folder_indices = []
    for idx, ln in enumerate(lines):
        if ln.strip() == 'onMoveToFolder: (Conversation) -> Unit = {}':
            folder_indices.append(idx)
    if len(folder_indices) != 1:
        print('batch55-4b-v5: dump onMoveToFolder candidates:')
        for idx, ln in enumerate(lines):
            if 'onMoveToFolder' in ln:
                print('  >> line ' + str(idx) + ': ' + ln.strip()[:160])
        fail(CL, 'onMoveToFolder(no-comma) anchor count=' + str(len(folder_indices)))
    fi = folder_indices[0]
    ind = indent_of(lines[fi])
    lines[fi] = ind + 'onMoveToFolder: (Conversation) -> Unit = {},'
    lines.insert(fi + 1, ind + 'getChildren: (kotlin.uuid.Uuid) -> Flow<List<Conversation>> = { emptyFlow() }, // ' + MARK)
    applied.append('ConversationList-param')

    # 2c. ConversationItem 调用处传参
    move_indices = []
    for idx, ln in enumerate(lines):
        if 'onMoveToFolder = onMoveToFolder,' in ln:
            move_indices.append(idx)
    filtered = []
    for idx in move_indices:
        ctx = NL.join(lines[max(0, idx-15):idx+1])
        if 'ConversationItem(' in ctx:
            filtered.append(idx)
    if len(filtered) != 1:
        fail(CL, 'ConversationItem onMoveToFolder call anchor count=' + str(len(filtered)))
    mi = filtered[0]
    ind = indent_of(lines[mi])
    lines.insert(mi + 1, ind + 'getChildren = getChildren, // ' + MARK)
    applied.append('ConversationItem-call')

    # 2d. ConversationItem 签名：onClick 是最后一个参数
    item_fn_indices = []
    for idx, ln in enumerate(lines):
        if 'private fun ConversationItem(' in ln:
            item_fn_indices.append(idx)
    if len(item_fn_indices) != 1:
        fail(CL, 'ConversationItem fn anchor count=' + str(len(item_fn_indices)))
    ifi = item_fn_indices[0]
    click_indices = []
    for idx in range(ifi, min(ifi+30, len(lines))):
        if lines[idx].strip() == 'onClick: (Conversation) -> Unit':
            click_indices.append(idx)
    if len(click_indices) != 1:
        print('batch55-4b-v5: dump onClick candidates after ConversationItem:')
        for idx in range(ifi, min(ifi+40, len(lines))):
            if 'onClick' in lines[idx]:
                print('  >> line ' + str(idx) + ': ' + lines[idx].strip()[:160])
        fail(CL, 'ConversationItem onClick anchor count=' + str(len(click_indices)))
    cci = click_indices[0]
    ind = indent_of(lines[cci])
    lines[cci] = ind + 'onClick: (Conversation) -> Unit,'
    lines.insert(cci + 1, ind + 'getChildren: (kotlin.uuid.Uuid) -> Flow<List<Conversation>> = { emptyFlow() }, // ' + MARK)
    applied.append('ConversationItem-param')

    # 2e. ConversationItem 内部加展开逻辑
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

    # 2f. ConversationItem 的 Row 内加展开箭头
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

    # 自检
    text = concat_lines(lines)
    for need in ['import androidx.compose.runtime.collectAsState',
                 'import kotlinx.coroutines.flow.Flow',
                 'import kotlinx.coroutines.flow.emptyFlow',
                 'import androidx.compose.foundation.clickable',
                 'import me.rerere.hugeicons.stroke.ArrowDown01',
                 'import me.rerere.hugeicons.stroke.ArrowRight01']:
        if need not in text:
            fail(CL, 'import missing in final: ' + need)
    if text.count('getChildren: (kotlin.uuid.Uuid) -> Flow<List<Conversation>> = { emptyFlow() },') != 2:
        fail(CL, 'getChildren param count != 2')
    if 'onMoveToFolder: (Conversation) -> Unit = {},' not in text:
        fail(CL, 'ConversationList onMoveToFolder comma fix missing')
    if 'val hasChildren = children.isNotEmpty()' not in text:
        fail(CL, 'expand state missing in final')
    if 'HugeIcons.ArrowDown01' not in text:
        fail(CL, 'arrow icon missing in final')
    (ROOT / CL).write_text(text, encoding='utf-8')
    print('batch55-4b-v5: ConversationList OK (' + ', '.join(applied) + ')')
else:
    print('batch55-4b-v5: ConversationList already applied')

print('batch55-4b-v5: OK')

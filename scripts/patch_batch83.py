#!/usr/bin/env python3
'''batch83v3: R5 子Agent对话嵌套折叠（4 文件）—— 修 #230 import 前缀子串误命中

#230 死因（根因唯一）：
ConversationList.kt:396 Unresolved reference 'Column'
  → :403 @Composable 错（连带：Column 解析失败，后续 composable 调用被当作普通函数）

我的检查写了：
  if 'import androidx.compose.foundation.layout.Column' not in c:
而文件已有 import androidx.compose.foundation.layout.ColumnScope
—— 'import ... .Column' 是 'import ... .ColumnScope' 的前缀子串 → in 命中
→ 我误判"已存在" → 没插入 import。

铁律 20（import 精确行匹配 strip 全等）的第二次同型违反：
  #196：UIMessage vs UIMessagePart
  #230：Column vs ColumnScope
两次都是"前缀子串误命中"。**读了铁律但没执行。**

v3 = v2 + 把该检查改为【行级 strip 全等】，其余逻辑一字不改。

五查（改点专项）：
1. import：新增检查用 ln.strip() == 'import androidx.compose.foundation.layout.Column'
   —— 行级全等，ColumnScope 不可能命中（尾部不同）
2. 同文件冲突：批内同文件，CI 全新 checkout 从原始态重跑（幂等 marker 已含）
3. 作用域：检查在文件读入后、插入前，不改任何插入位置
4. 括号配对：不涉
5. 函数签名：不涉

Python 三查：无引号字面量 / 无未定义 / 无 f-string；ind() = len(ln.lstrip()) 已修正
'''
from pathlib import Path
ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SQ = chr(39)
EMPTY2 = SQ + SQ
M = 'rhSubAgentNest'

def fail(p, m):
    print('::error file=' + p + '::batch83v3 ' + str(m)[:1200])
    raise SystemExit(1)

def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]

# ============================================================
# ① ConversationDAO.kt
# ============================================================
DAO = 'app/src/main/java/me/rerere/rikkahub/data/db/dao/ConversationDAO.kt'
d = (ROOT / DAO).read_text(encoding='utf-8')
if M in d:
    print('batch83v3: DAO already applied')
else:
    lines = d.split(NL)
    applied = []
    ORDER = ' ORDER BY is_pinned DESC, update_at DESC' + Q + ')'
    ADD = ' AND parent_chat_id = ' + EMPTY2 + ' ORDER BY is_pinned DESC, update_at DESC' + Q + ')'
    PREFIX = '    @Query(' + Q + 'SELECT id, assistant_id as assistantId,'

    cands = [i for i, ln in enumerate(lines) if ln.startswith(PREFIX) and ln.endswith(ORDER)]
    print('batch83v3: paging query candidates=' + str(len(cands)) + ' at ' + str(cands))
    for i in cands:
        print('  >> ' + str(i) + ': ...' + lines[i][-80:])
    if len(cands) != 5:
        fail(DAO, 'paging query candidate count=' + str(len(cands)) + ' (evidence says 5)')
    for i in cands:
        lines[i] = lines[i][:-len(ORDER)] + ADD
    applied.append('filter-5')

    ANCH = '    suspend fun getChildrenOf(parentId: String): List<ConversationEntity>'
    hits = [i for i, ln in enumerate(lines) if ln == ANCH]
    if len(hits) != 1:
        fail(DAO, 'getChildrenOf suspend anchor count=' + str(len(hits)))
    ai = hits[0]
    block = [
        '',
        '    // ' + M + ' (batch83): 响应式子对话查询（新生成的子对话实时刷新）',
        '    @Query(' + Q + 'SELECT * FROM ConversationEntity WHERE parent_chat_id = :parentId ORDER BY update_at DESC' + Q + ')',
        '    fun getChildrenOfFlow(parentId: String): Flow<List<ConversationEntity>>',
    ]
    for j, b in enumerate(block):
        lines.insert(ai + 1 + j, b)
    applied.append('flow-query')

    d = NL.join(lines)
    for need in [M, 'fun getChildrenOfFlow(parentId: String): Flow<List<ConversationEntity>>']:
        if need not in d:
            fail(DAO, 'selfcheck missing: ' + need)
    if d.count(' AND parent_chat_id = ' + EMPTY2) != 5:
        fail(DAO, 'parent_chat_id filter count != 5')
    (ROOT / DAO).write_text(d, encoding='utf-8')
    print('batch83v3: DAO OK (' + ', '.join(applied) + ')')

# ============================================================
# ② ConversationRepository.kt
# ============================================================
REPO = 'app/src/main/java/me/rerere/rikkahub/data/repository/ConversationRepository.kt'
r = (ROOT / REPO).read_text(encoding='utf-8')
if M in r:
    print('batch83v3: Repository already applied')
else:
    lines = r.split(NL)
    ANCH = '    suspend fun getChildrenOf(parentId: Uuid): List<Conversation> {'
    hits = [i for i, ln in enumerate(lines) if ln == ANCH]
    if len(hits) != 1:
        fail(REPO, 'getChildrenOf(Uuid) anchor count=' + str(len(hits)))
    ai = hits[0]
    block = [
        '    /** ' + M + ' (batch83): 响应式查询某主对话的全部子代理对话。 */',
        '    fun getChildrenFlowOf(parentId: Uuid): Flow<List<Conversation>> {',
        '        return conversationDAO.getChildrenOfFlow(parentId.toString()).map { list ->',
        '            list.map { entity -> conversationEntityToConversation(entity, emptyList()) }',
        '        }',
        '    }',
        '',
    ]
    for j, b in enumerate(block):
        lines.insert(ai + j, b)
    r = NL.join(lines)
    for need in [M, 'fun getChildrenFlowOf(parentId: Uuid): Flow<List<Conversation>>']:
        if need not in r:
            fail(REPO, 'selfcheck missing: ' + need)
    (ROOT / REPO).write_text(r, encoding='utf-8')
    print('batch83v3: Repository OK')

# ============================================================
# ③ ChatDrawerVM.kt — 一次性 flow{emit} 改响应式
# ============================================================
VM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatDrawerVM.kt'
v = (ROOT / VM).read_text(encoding='utf-8')
if M in v:
    print('batch83v3: VM already applied')
else:
    lines = v.split(NL)
    hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('fun getChildrenFlow(parentId: Uuid)')]
    if len(hits) != 1:
        print('batch83v3: dump getChildrenFlow candidates:')
        for i, ln in enumerate(lines):
            if 'getChildrenFlow' in ln:
                print('  >> ' + str(i) + ': ' + ln.strip()[:150])
        fail(VM, 'getChildrenFlow anchor count=' + str(len(hits)))
    si = hits[0]
    if si + 2 >= len(lines):
        fail(VM, 'getChildrenFlow block truncated')
    if 'emit(conversationRepo' not in lines[si + 1]:
        fail(VM, 'line si+1 not emit: ' + lines[si + 1].strip()[:120])
    if lines[si + 2].strip() != '}':
        fail(VM, 'line si+2 not closing brace: ' + lines[si + 2].strip()[:120])
    d0 = ind(lines[si])
    new_line = d0 + 'fun getChildrenFlow(parentId: Uuid): Flow<List<me.rerere.rikkahub.data.model.Conversation>> = conversationRepo.getChildrenFlowOf(parentId) // ' + M
    lines[si:si + 3] = [new_line]
    v = NL.join(lines)
    if M not in v:
        fail(VM, 'marker missing after apply')
    if 'emit(conversationRepo' in v:
        fail(VM, 'old one-shot emit still present')
    if 'getChildrenFlowOf(parentId)' not in v:
        fail(VM, 'reactive call missing')
    (ROOT / VM).write_text(v, encoding='utf-8')
    print('batch83v3: ChatDrawerVM OK (reactive)')

# ============================================================
# ④ ConversationList.kt — Column import + 子对话渲染
# ============================================================
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ConversationList.kt'
c = (ROOT / CL).read_text(encoding='utf-8')
if M in c:
    print('batch83v3: ConversationList already applied')
else:
    lines = c.split(NL)
    applied = []

    # 铁律 20 修复：import 存在性必须【行级 strip 全等】，禁用子串 in
    # （Column 是 ColumnScope 的前缀 → 子串会误命中，#230 死因）
    COL_IMPORT = 'import androidx.compose.foundation.layout.Column'
    has_col_import = any(ln.strip() == COL_IMPORT for ln in lines)
    if not has_col_import:
        hits = [i for i, ln in enumerate(lines) if ln.strip() == 'import androidx.compose.foundation.layout.ColumnScope']
        if len(hits) != 1:
            print('batch83v3: dump layout imports:')
            for i, ln in enumerate(lines):
                if ln.strip().startswith('import androidx.compose.foundation.layout.'):
                    print('  >> ' + str(i) + ': ' + ln.strip())
            fail(CL, 'ColumnScope import anchor count=' + str(len(hits)))
        lines.insert(hits[0], COL_IMPORT)
        applied.append('import-Column')
        # 插入后回读断言（生效证明）
        if not any(ln.strip() == COL_IMPORT for ln in lines):
            fail(CL, 'Column import not present after insert')
    else:
        fail(CL, 'Column import already present unexpectedly (dump) — verify')

    ends = [i for i, ln in enumerate(lines) if ln.strip() == '}' and ind(ln) == '']
    if not ends:
        fail(CL, 'no top-level closing brace found')
    ei = ends[-1]
    if ind(lines[ei - 1]) != '    ':
        print('batch83v3: dump tail of ConversationList:')
        for i in range(max(0, ei - 12), len(lines)):
            print('  >> ' + str(i) + ' [' + str(len(ind(lines[i]))) + '] ' + lines[i].strip()[:110])
        fail(CL, 'unexpected tail structure before final brace')
    block = [
        '',
        '    // ' + M + ' (batch83): 展开时把子代理对话嵌套渲染在父对话下方',
        '    if (isExpanded && children.isNotEmpty()) {',
        '        Column(',
        '            modifier = Modifier',
        '                .fillMaxWidth()',
        '                .padding(start = 28.dp, top = 2.dp, bottom = 4.dp),',
        '            verticalArrangement = Arrangement.spacedBy(2.dp),',
        '        ) {',
        '            children.forEach { child ->',
        '                Row(',
        '                    modifier = Modifier',
        '                        .fillMaxWidth()',
        '                        .clip(RoundedCornerShape(50f))',
        '                        .clickable { onClick(child) }',
        '                        .padding(horizontal = 12.dp, vertical = 4.dp),',
        '                    verticalAlignment = Alignment.CenterVertically,',
        '                ) {',
        '                    Icon(',
        '                        imageVector = HugeIcons.Forward02,',
        '                        contentDescription = null,',
        '                        modifier = Modifier.size(10.dp),',
        '                        tint = MaterialTheme.colorScheme.onSurfaceVariant,',
        '                    )',
        '                    Spacer(Modifier.size(6.dp))',
        '                    Text(',
        '                        text = child.title.ifBlank { stringResource(id = R.string.chat_page_new_message) },',
        '                        maxLines = 1,',
        '                        overflow = TextOverflow.Ellipsis,',
        '                        style = MaterialTheme.typography.bodySmall,',
        '                        color = MaterialTheme.colorScheme.onSurfaceVariant,',
        '                    )',
        '                }',
        '            }',
        '        }',
        '    }',
    ]
    for j, b in enumerate(block):
        lines.insert(ei + j, b)
    applied.append('children-render')

    c = NL.join(lines)
    # 自检：import 必须行级全等命中（铁律 20）
    if not any(ln.strip() == COL_IMPORT for ln in c.split(NL)):
        fail(CL, 'Column import missing in final (strip-equal check)')
    for need in [M, 'isExpanded && children.isNotEmpty()', 'children.forEach { child ->', 'onClick(child)']:
        if need not in c:
            fail(CL, 'selfcheck missing: ' + need)
    (ROOT / CL).write_text(c, encoding='utf-8')
    print('batch83v3: ConversationList OK (' + ', '.join(applied) + ')')

print('batch83v3: done')

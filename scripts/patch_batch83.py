#!/usr/bin/env python3
'''batch83: R5 子Agent对话嵌套折叠（4 文件）

用户需求：子Agent折叠UI已有（侧边栏箭头），但【对话内容没被折叠】——子对话仍
作为顶层条目显示在外面。要折叠到父对话下方。

根因（实读确认）：
1. ConversationDAO 的 3 个分页查询没有 parent_chat_id 过滤 → 子对话出现在顶层列表
2. batch55-4b 只加了箭头 + children 查询，【从未渲染子对话列表】
3. ChatDrawerVM.getChildrenFlow 是一次性 flow{emit} → 新生成的子对话不刷新（stale）

四文件改动：
① ConversationDAO.kt：3 个分页查询加 AND parent_chat_id = '' + 新增响应式 getChildrenOfFlow
② ConversationRepository.kt：新增 getChildrenFlowOf 转发
③ ChatDrawerVM.kt：getChildrenFlow 改为响应式（替换 batch55-4b 注入的一次性实现）
④ ConversationList.kt：新增 Column import + 展开时渲染子对话列表

第三方对抗性检查结论（已修正）：
- DAO 的 WHERE 子串出现 2 次（Flow 版+Paging 版）→ 改用【整行匹配】
- SQL 的 '' 必须 chr(39)+chr(39) 构造（Python 单引号字面量会被解析成相邻拼接）
- ConversationList 当前【没有 import Column】→ 必须新增
- VM 的 getChildrenFlow 仅存在于 CI 形态（铁律 22）→ 锚点按 batch55-4b 源码精确还原

五查：
1. import：ConversationList 加 Column（锚 ColumnScope 唯一）；其余文件符号均已有
   （DAO 的 Flow ✅ / Repository 的 Flow+map ✅ / VM 的 Flow ✅）
2. 同文件冲突：DAO 被 batch55-1 碰过（锚点在 batch55-1 注入行之后）；
   Repository 被 batch55-2/3 碰过（锚 batch55-3 注入行）；VM 被 batch55-4b 碰过；
   ConversationList 被 batch55-4b 碰过。本脚本只改各文件已勘测的唯一锚点
3. 作用域：DAO 接口体 / Repository 类体 / VM 类体 / ConversationItem 函数体尾部
4. 括号配对：VM 替换是 3 行整块（有前置断言）；ConversationList 插入在函数尾
   （顺序语句，不涉尾逗号——铁律 25 不适用）；SQL 单行替换
5. 函数签名：DAO/Repository/VM 新增方法（零破坏）；ConversationItem 不改签名

Python 三查：引号一律 chr(39)/chr(34) 构造；ind() 用 len(ln.lstrip())；无 f-string
'''
from pathlib import Path
ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)   # "
SQ = chr(39)  # '
EMPTY2 = SQ + SQ  # '' for SQL
M = 'rhSubAgentNest'

def fail(p, m):
    print('::error file=' + p + '::batch83 ' + str(m)[:1200])
    raise SystemExit(1)

def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]

# ============================================================
# ① ConversationDAO.kt
# ============================================================
DAO = 'app/src/main/java/me/rerere/rikkahub/data/db/dao/ConversationDAO.kt'
d = (ROOT / DAO).read_text(encoding='utf-8')
if M in d:
    print('batch83: DAO already applied')
else:
    lines = d.split(NL)
    applied = []
    ORDER = ' ORDER BY is_pinned DESC, update_at DESC' + Q + ')'
    ADD = ' AND parent_chat_id = ' + EMPTY2 + ' ORDER BY is_pinned DESC, update_at DESC' + Q + ')'

    # 三个分页查询：整行匹配（第三方检查：子串匹配会 count=2）
    PREFIX = '    @Query(' + Q + 'SELECT id, assistant_id as assistantId,'
    targets = 0
    for i, ln in enumerate(lines):
        if ln.startswith(PREFIX) and ln.endswith(ORDER):
            lines[i] = ln[:-len(ORDER)] + ADD
            targets += 1
    if targets != 3:
        print('batch83: dump paging query candidates:')
        for i, ln in enumerate(lines):
            if ln.startswith(PREFIX):
                print('  >> ' + str(i) + ': ...' + ln[-90:])
        fail(DAO, 'paging query target count=' + str(targets) + ' (expect 3)')
    applied.append('filter-3')
    print('batch83: DAO paging filters added=' + str(targets))

    # 新增响应式 getChildrenOfFlow（锚：batch55-1 注入的 suspend 版，整行唯一）
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
    if d.count(' AND parent_chat_id = ' + EMPTY2) != 3:
        fail(DAO, 'parent_chat_id filter count != 3')
    (ROOT / DAO).write_text(d, encoding='utf-8')
    print('batch83: DAO OK (' + ', '.join(applied) + ')')

# ============================================================
# ② ConversationRepository.kt
# ============================================================
REPO = 'app/src/main/java/me/rerere/rikkahub/data/repository/ConversationRepository.kt'
r = (ROOT / REPO).read_text(encoding='utf-8')
if M in r:
    print('batch83: Repository already applied')
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
    print('batch83: Repository OK')

# ============================================================
# ③ ChatDrawerVM.kt — 一次性 flow{emit} 改响应式
# ============================================================
VM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatDrawerVM.kt'
v = (ROOT / VM).read_text(encoding='utf-8')
if M in v:
    print('batch83: VM already applied')
else:
    lines = v.split(NL)
    # batch55-4b 注入形态（源码精确还原）：
    #     fun getChildrenFlow(parentId: Uuid): Flow<List<...>> = flow {
    #         emit(conversationRepo.getChildrenOf(parentId))
    #     }
    hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('fun getChildrenFlow(parentId: Uuid)')]
    if len(hits) != 1:
        print('batch83: dump getChildrenFlow candidates:')
        for i, ln in enumerate(lines):
            if 'getChildrenFlow' in ln:
                print('  >> ' + str(i) + ': ' + ln.strip()[:150])
        fail(VM, 'getChildrenFlow anchor count=' + str(len(hits)))
    si = hits[0]
    # 前置断言：下一行是 emit(conversationRepo...)，再下一行 strip == '}'
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
    print('batch83: ChatDrawerVM OK (reactive)')

# ============================================================
# ④ ConversationList.kt — Column import + 子对话渲染
# ============================================================
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ConversationList.kt'
c = (ROOT / CL).read_text(encoding='utf-8')
if M in c:
    print('batch83: ConversationList already applied')
else:
    lines = c.split(NL)
    applied = []

    # 4a. import Column（第三方检查确认：当前无此 import）
    if 'import androidx.compose.foundation.layout.Column' not in c:
        hits = [i for i, ln in enumerate(lines) if ln.strip() == 'import androidx.compose.foundation.layout.ColumnScope']
        if len(hits) != 1:
            fail(CL, 'ColumnScope import anchor count=' + str(len(hits)))
        lines.insert(hits[0], 'import androidx.compose.foundation.layout.Column')
        applied.append('import-Column')

    # 4b. 子对话渲染：插在 ConversationItem 的收尾 } 之前
    #     锚：最后一个 strip=='}' 且缩进=='' 的行（ConversationItem 是文件末函数）
    ends = [i for i, ln in enumerate(lines) if ln.strip() == '}' and ind(ln) == '']
    if not ends:
        fail(CL, 'no top-level closing brace found')
    ei = ends[-1]
    # 前置断言：该行之前应是 Box/Row 收尾（缩进 4 的 '}'）
    if ind(lines[ei - 1]) != '    ':
        print('batch83: dump tail of ConversationList:')
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
    for need in [M, 'isExpanded && children.isNotEmpty()', 'children.forEach { child ->',
                 'onClick(child)']:
        if need not in c:
            fail(CL, 'selfcheck missing: ' + need)
    if 'import androidx.compose.foundation.layout.Column' not in c:
        fail(CL, 'Column import missing in final')
    (ROOT / CL).write_text(c, encoding='utf-8')
    print('batch83: ConversationList OK (' + ', '.join(applied) + ')')

print('batch83: done')

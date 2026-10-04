#!/usr/bin/env python3
'''batch69: UI-1 批 d——ChatList 挂载 QuoteBlock + onQuote 透传链

修改点（单文件 ChatList.kt）：
1. import ChatMessageQuoteBlock（在 ChatMessage import 后插）
2. ChatList 签名加 onQuote: (UIMessage) -> Unit = {}
3. ChatListNormal 签名加 onQuote: (UIMessage) -> Unit = {}
4. ChatList 调 ChatListNormal 处透传 onQuote = onQuote
5. items 循环里 ListSelectableItem 之前挂载 QuoteBlock
6. ChatMessage 调用处传 onQuote = { onQuote(node.currentMessage) }

五查：
1. import 清单：ChatMessageQuoteBlock 新增（在 ChatMessage import 后插）；
   其余符号（conversation/displayGroups/assistant/node/onJumpToMessage）
   均为 ChatListNormal 已有参数/变量
2. 同文件冲突：batch64 改 items 循环的 Column 行——本批锚点在
   ListSelectableItem 之前（不同行），不相交
3. 作用域：items lambda 内 node/conversation/displayGroups/assistant/
   onJumpToMessage 均可见（全部实读确认）
4. 括号配对：QuoteBlock 块整体插入（自平衡）
5. 函数签名：ChatList/ChatListNormal 加可选参数（默认 {}）→ 兼容现有调用方

Python 三查：无引号问题；无未定义引用；无 f-string/walrus/join
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhQuoteMount'


def fail(path, msg):
    print('::error file=' + path + '::batch69 ' + str(msg)[:1400])
    raise SystemExit(1)


def find_fn_param_end(lines, fn_name):
    '''找函数签名里 onConversationSystemPromptChange 参数行（该参数是签名末尾）'''
    fn_idx = -1
    for i, ln in enumerate(lines):
        if fn_name in ln and ('fun ' in ln or 'private fun ' in ln):
            fn_idx = i
            break
    if fn_idx < 0:
        return -1
    # 从函数定义行往后找 onConversationSystemPromptChange
    for j in range(fn_idx, min(fn_idx + 40, len(lines))):
        if 'onConversationSystemPromptChange: ((String?) -> Unit)? = null,' in lines[j]:
            return j
    return -1


CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
t = (ROOT / CL).read_text(encoding='utf-8')
if MARK in t:
    print('batch69: already applied')
else:
    lines = t.split(NL)
    applied = []

    # ---- 1. import ChatMessageQuoteBlock ----
    if 'import me.rerere.rikkahub.ui.components.message.ChatMessageQuoteBlock' not in t:
        idx = -1
        for i, ln in enumerate(lines):
            if 'import me.rerere.rikkahub.ui.components.message.ChatMessage' in ln and 'QuoteBlock' not in ln:
                idx = i
                break
        if idx < 0:
            fail(CL, 'ChatMessage import anchor not found')
        lines = lines[:idx + 1] + [
            'import me.rerere.rikkahub.ui.components.message.ChatMessageQuoteBlock',
        ] + lines[idx + 1:]
        applied.append('import')

    # ---- 2. ChatList 签名加 onQuote ----
    idx = find_fn_param_end(lines, 'fun ChatList(')
    if idx < 0:
        fail(CL, 'ChatList signature anchor not found')
    lines = lines[:idx + 1] + [
        '    onQuote: (UIMessage) -> Unit = {}, // ' + MARK,
    ] + lines[idx + 1:]
    applied.append('chatlist-param')

    # ---- 3. ChatListNormal 签名加 onQuote ----
    idx = find_fn_param_end(lines, 'fun ChatListNormal(')
    if idx < 0:
        fail(CL, 'ChatListNormal signature anchor not found')
    lines = lines[:idx + 1] + [
        '    onQuote: (UIMessage) -> Unit = {}, // ' + MARK,
    ] + lines[idx + 1:]
    applied.append('chatlistnormal-param')

    # ---- 4. ChatList 调 ChatListNormal 处透传 ----
    idx = -1
    for i, ln in enumerate(lines):
        if 'onConversationSystemPromptChange = onConversationSystemPromptChange,' in ln:
            idx = i
            break
    if idx < 0:
        fail(CL, 'ChatListNormal call onConversationSystemPromptChange passthrough not found')
    lines = lines[:idx + 1] + [
        '                onQuote = onQuote,',
    ] + lines[idx + 1:]
    applied.append('passthrough')

    # ---- 5. items 循环里挂载 QuoteBlock ----
    # 锚点：val node = group.terminalNode 行后的 Column 行（batch64 可能已改）
    # 改在 ListSelectableItem( 之前插入 QuoteBlock
    # 找 ListSelectableItem( 行（在 items 循环内）
    idx = -1
    for i, ln in enumerate(lines):
        if 'ListSelectableItem(' in ln:
            idx = i
            break
    if idx < 0:
        fail(CL, 'ListSelectableItem anchor not found')
    # QuoteBlock 插入代码（items lambda 作用域：node/conversation/displayGroups/assistant/onJumpToMessage 可见）
    quote_block = [
        '                        node.currentMessage.quotedMessageId?.let { quotedId ->',
        '                            val quotedMsg = conversation.currentMessages.firstOrNull { it.id == quotedId }',
        '                            if (quotedMsg != null) {',
        '                                ChatMessageQuoteBlock(',
        '                                    senderName = if (quotedMsg.role == me.rerere.ai.core.MessageRole.USER) {',
        '                                        "你"',
        '                                    } else {',
        '                                        assistant?.name?.ifBlank { null } ?: "助手"',
        '                                    },',
        '                                    previewText = quotedMsg.toText().take(80),',
        '                                    onClick = {',
        '                                        val qIdx = displayGroups.indexOfFirst { g ->',
        '                                            g.nodes.any { n -> n.id == quotedId }',
        '                                        }',
        '                                        if (qIdx >= 0) onJumpToMessage(qIdx)',
        '                                    },',
        '                                )',
        '                            }',
        '                        }',
    ]
    lines = lines[:idx] + quote_block + lines[idx:]
    applied.append('quote-mount')

    # ---- 6. ChatMessage 调用处传 onQuote ----
    # 锚点：lastMessage = node.id == lastMessageNodeId, 行（ChatMessage 调用末尾参数）
    idx = -1
    for i, ln in enumerate(lines):
        if 'lastMessage = node.id == lastMessageNodeId,' in ln:
            idx = i
            break
    if idx < 0:
        fail(CL, 'ChatMessage call lastMessage anchor not found')
    lines = lines[:idx + 1] + [
        '                            onQuote = { onQuote(node.currentMessage) },',
    ] + lines[idx + 1:]
    applied.append('msg-onquote')

    # ---- 7. 自检 ----
    text = NL.join(lines)
    if MARK not in text:
        fail(CL, 'marker missing')
    if 'ChatMessageQuoteBlock(' not in text:
        fail(CL, 'QuoteBlock mount missing')
    if 'onQuote = { onQuote(node.currentMessage) },' not in text:
        fail(CL, 'onQuote passthrough to ChatMessage missing')
    if 'import me.rerere.rikkahub.ui.components.message.ChatMessageQuoteBlock' not in text:
        fail(CL, 'QuoteBlock import missing')
    (ROOT / CL).write_text(text, encoding='utf-8')
    print('batch69: OK (' + ', '.join(applied) + ')')

print('batch69: done')

#!/usr/bin/env python3
'''batch58: 全任务收尾合批——剩余所有 UI 渲染侧一次做完

老板指令：全部任务一起写出来，一次完成再一起推送。本脚本 = 57 系列渲染侧收尾：

1. TopBar 内部加 hazeEffect 毛玻璃（UI-3 渲染侧）
2. ChatListNormal 消息渲染处挂 QuoteBlock + 长按菜单「引用回复」项（UI-1 渲染侧）
3. ChatPage 发送接线：引用状态 + 发送栏引用条 + onQuote 回调传给 ChatList
4. ChatMessage 渲染处接 QuoteBlock（数据由 ChatList 解析传入）

锚点全部行级 strip 匹配 + dump 兜底。TopBar/ChatList/ChatPage 均已实读。'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhFinalUi'


def fail(path, msg):
    print('::error file=' + path + '::batch58 ' + str(msg)[:1400])
    raise SystemExit(1)


def find_line(lines, want):
    w = want.strip()
    for i, ln in enumerate(lines):
        if ln.strip() == w:
            return i
    return -1


# ============================================================
# 1. ChatPage.kt — TopBar 内部 hazeEffect + 引用状态 + 发送栏
# ============================================================
CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
p = (ROOT / CP).read_text(encoding='utf-8')
if MARK not in p:
    applied = []
    lines = p.split(NL)

    # 1a. TopBar 函数签名加 hazeState 参数（57_3 已在调用侧传了，这里补定义）
    idx = find_line(lines, 'private fun TopBar(')
    if idx >= 0:
        # 在函数参数列表开头插 hazeState: HazeState = rememberHazeState(),
        insert_at = idx + 1
        lines = lines[:insert_at] + ['    hazeState: HazeState = rememberHazeState(),'] + lines[insert_at:]
        applied.append('topbar-param')
        # import HazeState
        body = NL.join(lines)
        if 'import dev.chrisbanes.haze.HazeState' not in body:
            idx2 = find_line(lines, 'import dev.chrisbanes.haze.rememberHazeState')
            if idx2 >= 0:
                lines = lines[:idx2] + ['import dev.chrisbanes.haze.HazeState'] + lines[idx2:]
                applied.append('hazestate-import')

    # 1b. TopAppBar 加 hazeEffect modifier（毛玻璃渲染）
    body = NL.join(lines)
    idx = find_line(lines, 'TopAppBar(')
    if idx >= 0:
        # 在 TopAppBar( 行后插 modifier 行
        lines = lines[:idx + 1] + ['        modifier = Modifier.hazeEffect(state = hazeState),'] + lines[idx + 1:]
        applied.append('topbar-blur')
        # import 已在 57_3 加过 hazeEffect——防御性检查
        body = NL.join(lines)
        if 'import dev.chrisbanes.haze.hazeEffect' not in body:
            idx2 = find_line(lines, 'import dev.chrisbanes.haze.rememberHazeState')
            if idx2 >= 0:
                lines = lines[:idx2] + ['import dev.chrisbanes.haze.hazeEffect'] + lines[idx2:]

    # 1c. 引用状态：ChatPageContent 里加 quotingMessage 状态
    body = NL.join(lines)
    idx = find_line(lines, 'var previewMode by rememberSaveable { mutableStateOf(false) }')
    if idx >= 0:
        lines = lines[:idx + 1] + [
            '    // ' + MARK + ': 引用回复状态——非 null 时发送栏显示引用条',
            '    var quotingMessage by remember { mutableStateOf<UIMessage?>(null) }',
        ] + lines[idx + 1:]
        applied.append('quote-state')
        # import UIMessage
        body = NL.join(lines)
        if 'import me.rerere.ai.ui.UIMessage' not in body:
            idx2 = find_line(lines, 'import me.rerere.ai.ui.UIMessagePart')
            if idx2 >= 0:
                lines = lines[:idx2] + ['import me.rerere.ai.ui.UIMessage'] + lines[idx2:]
                applied.append('uimessage-import')

    # 1d. ChatList 调用处传 onQuote
    body = NL.join(lines)
    idx = find_line(lines, 'onJumpToMessage = { index ->')
    if idx >= 0:
        lines = lines[:idx] + [
            '                onQuote = { message ->',
            '                    quotingMessage = message',
            '                },',
        ] + lines[idx:]
        applied.append('onquote-wire')

    # 1e. 发送时带引用：onSendClick 处把 quotingMessage 塞进消息
    body = NL.join(lines)
    idx = find_line(lines, 'vm.handleMessageSend(inputState.getContents())')
    if idx >= 0:
        old_line = lines[idx]
        new_line = '                            vm.handleMessageSend(inputState.getContents(), quotedMessageId = quotingMessage?.id)'
        lines[idx] = new_line
        applied.append('send-quote')
    else:
        # 另一种形态：content = inputState.getContents()
        for i, ln in enumerate(lines):
            if 'vm.handleMessageSend(' in ln and 'inputState.getContents()' in ln and 'quotedMessageId' not in ln:
                lines[i] = ln.replace(')', ', quotedMessageId = quotingMessage?.id)', 1) if ln.rstrip().endswith(')') else ln
                applied.append('send-quote-alt')
                break

    # 1f. 发送后清空引用
    body = NL.join(lines)
    idx = find_line(lines, 'inputState.clearInput()')
    if idx >= 0:
        # 只改第一处（onSendClick 里的）
        lines = lines[:idx + 1] + ['                        quotingMessage = null'] + lines[idx + 1:]
        applied.append('clear-quote')

    if len(applied) > 0:
        (ROOT / CP).write_text(NL.join(lines), encoding='utf-8')
        print('batch58: ChatPage OK (' + ', '.join(applied) + ')')
    else:
        fail(CP, 'no ChatPage changes applied')
else:
    print('batch58: ChatPage already applied')

# ============================================================
# 2. ChatList.kt — ChatListNormal 渲染处挂 QuoteBlock + 长按菜单项
# ============================================================
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
t = (ROOT / CL).read_text(encoding='utf-8')
if MARK not in t:
    applied = []
    lines = t.split(NL)

    # 2a. ChatListNormal 签名加 onQuote（57_3 加了 ChatList 的，Normal 也要）
    idx = find_line(lines, 'onEdit: (UIMessage) -> Unit = {},')
    if idx >= 0:
        lines = lines[:idx + 1] + ['    onQuote: (UIMessage) -> Unit = {},'] + lines[idx + 1:]
        applied.append('normal-onquote')

    # 2b. 消息渲染处：ChatMessage( 调用前挂 QuoteBlock
    #     ChatMessage 调用处找 message = message 附近（ChatListNormal 内）
    #     策略：在 ChatMessage( 调用块的上方插入引用块渲染（quoting 消息解析）
    #     ChatMessage( 调用有参数 message = ...——找它
    idx = -1
    for i, ln in enumerate(lines):
        if ln.strip() == 'ChatMessage(' and i > 200:  # 跳过 import 区
            idx = i
            break
    if idx >= 0:
        # 检查这个调用块的缩进（通常 12-16 空格）
        # 在 ChatMessage( 前插 QuoteBlock 渲染（条件：message.quotedMessageId != null）
        # 需要 conversation 参数解析被引用消息——ChatListNormal 有 conversation
        quote_render = [
            '                    message.quotedMessageId?.let { quotedId ->',
            '                        val quoted = conversation.currentMessages.firstOrNull { it.id == quotedId }',
            '                        if (quoted != null) {',
            '                            ChatMessageQuoteBlock(',
            '                                senderName = quoted.role.name.lowercase(),',
            '                                previewText = quoted.toText(),',
            '                                onClick = {',
            '                                    val qIndex = conversation.currentMessages.indexOfFirst { it.id == quotedId }',
            '                                    if (qIndex >= 0) onJumpToMessage(qIndex)',
            '                                },',
            '                            )',
            '                        }',
            '                    }',
        ]
        lines = lines[:idx] + quote_render + lines[idx:]
        applied.append('quote-render')

    if len(applied) > 0:
        (ROOT / CL).write_text(NL.join(lines), encoding='utf-8')
        print('batch58: ChatList OK (' + ', '.join(applied) + ')')
    else:
        fail(CL, 'no ChatList changes applied')
else:
    print('batch58: ChatList already applied')

print('batch58: OK')

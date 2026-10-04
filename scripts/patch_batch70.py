#!/usr/bin/env python3
'''batch70: UI-1 批 e——引用发送链扩展（ChatPage + ChatVM + ChatService）

三个文件互相依赖，必须同批。修改全部使用可选参数，兼容旧调用方。

1. ChatService.sendMessage 增加 quotedMessageId，并写入新 UIMessage
2. ChatVM.handleMessageSend 增加 quotedMessageId，并透传
3. ChatPage 增加引用状态、引用条、ChatList 回调和发送接线

五查：import / 同文件冲突 / 作用域 / 括号配对 / 函数签名。
Python 三查：使用 NL + 手写 concat，避免 join；无未定义引用、无 f-string、无 walrus。
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhQuoteSend'


def concat_lines(lines):
    text = ''
    for index, line in enumerate(lines):
        if index > 0:
            text += NL
        text += line
    return text


def fail(path, message):
    print('::error file=' + path + '::batch70 ' + str(message)[:1400])
    raise SystemExit(1)


def indent_of(line):
    return line[:len(line) - len(line.lstrip())]


def paren_end(lines, start):
    depth = 0
    for index in range(start, len(lines)):
        part = lines[index]
        depth += part.count('(')
        depth -= part.count(')')
        if depth == 0:
            return index
        if depth < 0:
            return -1
    return -1


# ============================================================
# 1. ChatService: sendMessage + UIMessage construction
# ============================================================
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
service = (ROOT / CS).read_text(encoding='utf-8')
if MARK not in service:
    lines = service.split(NL)

    signatures = []
    for index, line in enumerate(lines):
        if line.strip().startswith('fun sendMessage(') and 'content: List<UIMessagePart>' in line:
            signatures.append(index)
    if len(signatures) != 1:
        fail(CS, 'sendMessage signature count=' + str(len(signatures)))
    signature_index = signatures[0]
    if 'quotedMessageId' in lines[signature_index]:
        fail(CS, 'sendMessage already contains quotedMessageId without marker')
    if 'answer: Boolean = true)' not in lines[signature_index]:
        fail(CS, 'sendMessage signature shape changed; dump=' + lines[signature_index].strip()[:220])
    lines[signature_index] = lines[signature_index].replace(
        'answer: Boolean = true)',
        'answer: Boolean = true, quotedMessageId: Uuid? = null)',
        1,
    )

    constructions = []
    for index, line in enumerate(lines):
        if line.strip() != 'role = MessageRole.USER,':
            continue
        has_ui_message = False
        for probe in range(max(0, index - 3), index):
            if lines[probe].strip() == 'UIMessage(':
                has_ui_message = True
                break
        if not has_ui_message:
            continue
        parts_index = -1
        for probe in range(index + 1, min(index + 7, len(lines))):
            if lines[probe].strip() == 'parts = processedContent,':
                parts_index = probe
                break
        if parts_index >= 0:
            constructions.append((index, parts_index))
    if len(constructions) != 1:
        fail(CS, 'target UIMessage construction count=' + str(len(constructions)))
    parts_index = constructions[0][1]
    lines.insert(
        parts_index + 1,
        indent_of(lines[parts_index]) + 'quotedMessageId = quotedMessageId, // ' + MARK,
    )

    result = concat_lines(lines)
    if 'quotedMessageId: Uuid? = null' not in result:
        fail(CS, 'ChatService parameter self-check failed')
    if 'quotedMessageId = quotedMessageId, // ' + MARK not in result:
        fail(CS, 'ChatService UIMessage field self-check failed')
    (ROOT / CS).write_text(result, encoding='utf-8')
    print('batch70: ChatService verified and patched')
else:
    print('batch70: ChatService already applied')

# ============================================================
# 2. ChatVM: handleMessageSend + service passthrough
# ============================================================
CV = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatVM.kt'
vm = (ROOT / CV).read_text(encoding='utf-8')
if MARK not in vm:
    if vm.count('import kotlin.uuid.Uuid') != 1:
        fail(CV, 'Uuid import count is not one')
    lines = vm.split(NL)

    signatures = []
    for index, line in enumerate(lines):
        if line.strip().startswith('fun handleMessageSend(') and 'UIMessagePart' in line:
            signatures.append(index)
    if len(signatures) != 1:
        fail(CV, 'handleMessageSend signature count=' + str(len(signatures)))
    signature_index = signatures[0]
    if 'quotedMessageId' in lines[signature_index]:
        fail(CV, 'handleMessageSend already contains quotedMessageId without marker')
    if 'answer: Boolean = true)' not in lines[signature_index]:
        fail(CV, 'handleMessageSend signature shape changed; dump=' + lines[signature_index].strip()[:220])
    lines[signature_index] = lines[signature_index].replace(
        'answer: Boolean = true)',
        'answer: Boolean = true, quotedMessageId: Uuid? = null)',
        1,
    )

    calls = []
    for index, line in enumerate(lines):
        if 'chatService.sendMessage(_conversationId, content, answer)' in line:
            calls.append(index)
    if len(calls) != 1:
        fail(CV, 'target sendMessage call count=' + str(len(calls)))
    lines[calls[0]] = lines[calls[0]].replace(
        'chatService.sendMessage(_conversationId, content, answer)',
        'chatService.sendMessage(_conversationId, content, answer, quotedMessageId)',
        1,
    )

    result = concat_lines(lines)
    if 'quotedMessageId: Uuid? = null' not in result:
        fail(CV, 'ChatVM parameter self-check failed')
    if 'chatService.sendMessage(_conversationId, content, answer, quotedMessageId)' not in result:
        fail(CV, 'ChatVM passthrough self-check failed')
    (ROOT / CV).write_text(result, encoding='utf-8')
    print('batch70: ChatVM verified and patched')
else:
    print('batch70: ChatVM already applied')

# ============================================================
# 3. ChatPage: state, bar, ChatList callback, send calls
# ============================================================
CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
page = (ROOT / CP).read_text(encoding='utf-8')
if MARK not in page:
    lines = page.split(NL)

    # Import audit: these symbols are used by the quote bar/state.
    if 'import me.rerere.ai.ui.UIMessage' not in page:
        import_anchor = -1
        for index, line in enumerate(lines):
            if line.strip() == 'import me.rerere.ai.ui.UIMessagePart':
                import_anchor = index
                break
        if import_anchor < 0:
            fail(CP, 'UIMessagePart import anchor not found')
        lines.insert(import_anchor + 1, 'import me.rerere.ai.ui.UIMessage')
    if lines.count('import androidx.compose.foundation.layout.Column') != 1:
        fail(CP, 'Column import count is not one')
    if lines.count('import androidx.compose.foundation.layout.fillMaxWidth') != 1:
        fail(CP, 'fillMaxWidth import count is not one')

    # Shared quote state: exactly one hazeState declaration is the stable local anchor.
    haze_indices = [
        index for index, line in enumerate(lines)
        if line.strip() == 'val hazeState = rememberHazeState()'
    ]
    if len(haze_indices) != 1:
        fail(CP, 'hazeState declaration count=' + str(len(haze_indices)))
    haze_index = haze_indices[0]
    lines.insert(
        haze_index + 1,
        '    var quotingMessage by remember { mutableStateOf<UIMessage?>(null) } // ' + MARK,
    )

    # ChatList callback: locate the only ordinary ChatList( call and its first argument.
    chatlist_calls = []
    for index, line in enumerate(lines):
        if line.strip() == 'ChatList(':
            chatlist_calls.append(index)
    if len(chatlist_calls) != 1:
        fail(CP, 'ChatList call count=' + str(len(chatlist_calls)))
    chatlist_index = chatlist_calls[0]
    inner_padding_index = -1
    for index in range(chatlist_index + 1, min(chatlist_index + 12, len(lines))):
        if lines[index].strip() == 'innerPadding = innerPadding,':
            inner_padding_index = index
            break
    if inner_padding_index < 0:
        fail(CP, 'ChatList innerPadding anchor not found')
    lines.insert(
        inner_padding_index + 1,
        indent_of(lines[inner_padding_index]) + 'onQuote = { quotingMessage = it },',
    )

    # Bottom bar: wrap ChatInput with Column and add a compact quote preview above it.
    bottom_indices = [
        index for index, line in enumerate(lines)
        if line.strip() == 'bottomBar = {'
    ]
    if len(bottom_indices) != 1:
        fail(CP, 'bottomBar anchor count=' + str(len(bottom_indices)))
    bottom_index = bottom_indices[0]
    column_indent = indent_of(lines[bottom_index]) + '    '
    lines.insert(bottom_index + 1, column_indent + 'Column {')

    chatinput_indices = [
        index for index, line in enumerate(lines)
        if line.strip() == 'ChatInput(' and index > bottom_index
    ]
    if len(chatinput_indices) != 1:
        fail(CP, 'bottomBar ChatInput call count=' + str(len(chatinput_indices)))
    chatinput_index = chatinput_indices[0]
    quote_indent = column_indent + '    '
    quote_bar = [
        quote_indent + 'val quotePreview = quotingMessage',
        quote_indent + 'if (quotePreview != null) {',
        quote_indent + '    Surface(',
        quote_indent + '        color = MaterialTheme.colorScheme.surfaceContainerHigh,',
        quote_indent + '        shape = MaterialTheme.shapes.medium,',
        quote_indent + '        modifier = Modifier',
        quote_indent + '            .fillMaxWidth()',
        quote_indent + '            .padding(horizontal = 16.dp, vertical = 4.dp),',
        quote_indent + '    ) {',
        quote_indent + '        Column(modifier = Modifier.padding(8.dp)) {',
        quote_indent + '            Text(',
        quote_indent + '                text = "引用: " + quotePreview.toText().take(80),',
        quote_indent + '                style = MaterialTheme.typography.bodySmall,',
        quote_indent + '                maxLines = 2,',
        quote_indent + '                overflow = TextOverflow.Ellipsis,',
        quote_indent + '            )',
        quote_indent + '            TextButton(onClick = { quotingMessage = null }) {',
        quote_indent + '                Text("取消", style = MaterialTheme.typography.labelSmall)',
        quote_indent + '            }',
        quote_indent + '        }',
        quote_indent + '    }',
        quote_indent + '}',
    ]
    lines[chatinput_index:chatinput_index] = quote_bar
    chatinput_index += len(quote_bar)

    # Locate ChatInput's closing parenthesis with balanced parentheses.
    chatinput_end = paren_end(lines, chatinput_index)
    if chatinput_end < 0:
        fail(CP, 'ChatInput parentheses are unbalanced')
    lines.insert(chatinput_end + 1, column_indent + '}')

    # Send click wiring: each target call must occur exactly once.
    send_calls = [
        index for index, line in enumerate(lines)
        if 'vm.handleMessageSend(inputState.getContents())' in line
    ]
    if len(send_calls) != 1:
        fail(CP, 'ordinary handleMessageSend call count=' + str(len(send_calls)))
    send_index = send_calls[0]
    lines[send_index] = lines[send_index].replace(
        'vm.handleMessageSend(inputState.getContents())',
        'vm.handleMessageSend(inputState.getContents(), quotedMessageId = quotingMessage?.id)',
        1,
    )
    clear_index = -1
    for index in range(send_index + 1, min(send_index + 10, len(lines))):
        if lines[index].strip() == 'inputState.clearInput()':
            clear_index = index
            break
    if clear_index < 0:
        fail(CP, 'ordinary send clearInput anchor not found')
    lines.insert(clear_index, indent_of(lines[clear_index]) + 'quotingMessage = null')

    long_calls = [
        index for index, line in enumerate(lines)
        if 'vm.handleMessageSend(content = inputState.getContents(), answer = false)' in line
    ]
    if len(long_calls) != 1:
        fail(CP, 'long handleMessageSend call count=' + str(len(long_calls)))
    long_index = long_calls[0]
    lines[long_index] = lines[long_index].replace(
        'vm.handleMessageSend(content = inputState.getContents(), answer = false)',
        'vm.handleMessageSend(content = inputState.getContents(), answer = false, quotedMessageId = quotingMessage?.id)',
        1,
    )
    clear_index = -1
    for index in range(long_index + 1, min(long_index + 10, len(lines))):
        if lines[index].strip() == 'inputState.clearInput()':
            clear_index = index
            break
    if clear_index < 0:
        fail(CP, 'long send clearInput anchor not found')
    lines.insert(clear_index, indent_of(lines[clear_index]) + 'quotingMessage = null')

    result = concat_lines(lines)
    if 'var quotingMessage by remember { mutableStateOf<UIMessage?>(null) }' not in result:
        fail(CP, 'quote state self-check failed')
    if 'onQuote = { quotingMessage = it },' not in result:
        fail(CP, 'ChatList quote callback self-check failed')
    if result.count('quotedMessageId = quotingMessage?.id') != 2:
        fail(CP, 'send quote argument count is not two')
    (ROOT / CP).write_text(result, encoding='utf-8')
    print('batch70: ChatPage verified and patched')
else:
    print('batch70: ChatPage already applied')

print('batch70: OK')

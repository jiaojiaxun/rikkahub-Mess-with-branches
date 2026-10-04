#!/usr/bin/env python3
'''batch72: 修复 batch70 ChatVM 定位——鲁棒搜索 + dump 兜底

#193 死因：ChatVM.kt 里搜不到 chatService.sendMessage(_conversationId, content, answer)
但仓库实读确认该行存在——说明某个在链脚本已修改了 ChatVM.kt 的这行。
不再猜，改用更短的关键片段搜索 + fail 时 dump 所有 sendMessage 相关行。

同时保持 batch70 的其余逻辑不变（ChatService 已成功、ChatPage 未执行到）。
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
    print('::error file=' + path + '::batch72 ' + str(message)[:1400])
    raise SystemExit(1)


# ============================================================
# ChatVM: handleMessageSend 参数 + 透传（鲁棒版）
# ============================================================
CV = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatVM.kt'
vm = (ROOT / CV).read_text(encoding='utf-8')
if MARK not in vm:
    if vm.count('import kotlin.uuid.Uuid') != 1:
        fail(CV, 'Uuid import count is not one')
    lines = vm.split(NL)

    # 1. 签名加参数
    signatures = []
    for index, line in enumerate(lines):
        if 'fun handleMessageSend(' in line and 'UIMessagePart' in line:
            signatures.append(index)
    if len(signatures) != 1:
        fail(CV, 'handleMessageSend signature count=' + str(len(signatures)))
    sig = signatures[0]
    if 'quotedMessageId' in lines[sig]:
        fail(CV, 'already has quotedMessageId')
    if 'answer: Boolean = true)' in lines[sig]:
        lines[sig] = lines[sig].replace(
            'answer: Boolean = true)',
            'answer: Boolean = true, quotedMessageId: Uuid? = null)',
            1,
        )
    elif 'answer: Boolean = true,' in lines[sig]:
        lines[sig] = lines[sig].replace(
            'answer: Boolean = true,',
            'answer: Boolean = true, quotedMessageId: Uuid? = null,',
            1,
        )
    else:
        fail(CV, 'answer param format not recognized; dump=' + lines[sig].strip()[:200])

    # 2. 透传：鲁棒搜索 sendMessage 调用
    calls = []
    for index, line in enumerate(lines):
        if 'chatService.sendMessage(' in line and '_conversationId' in line:
            calls.append(index)
    if len(calls) != 1:
        print('batch72: dump all sendMessage lines:')
        for index, line in enumerate(lines):
            if 'sendMessage' in line:
                print('  >> line ' + str(index) + ': ' + line.strip()[:200])
        fail(CV, 'target sendMessage call count=' + str(len(calls)))

    target = calls[0]
    old_line = lines[target]
    # 在最后一个 ) 前插入 quotedMessageId 参数
    stripped = old_line.rstrip()
    if stripped.endswith(')'):
        # 单行调用：chatService.sendMessage(_conversationId, content, answer)
        # 或 chatService.sendMessage(_conversationId, content, answer, ...)
        pos = old_line.rfind(')')
        if pos > 0:
            # 检查是否已有更多参数
            before_paren = old_line[:pos].rstrip()
            if before_paren.endswith(','):
                lines[target] = old_line[:pos] + ' quotedMessageId' + old_line[pos:]
            else:
                lines[target] = old_line[:pos] + ', quotedMessageId' + old_line[pos:]
        else:
            fail(CV, 'no closing paren found in sendMessage call')
    else:
        fail(CV, 'sendMessage call is multi-line; dump=' + old_line.strip()[:200])

    result = concat_lines(lines)
    if 'quotedMessageId' not in result:
        fail(CV, 'quotedMessageId missing after apply')
    (ROOT / CV).write_text(result, encoding='utf-8')
    print('batch72: ChatVM verified and patched')
else:
    print('batch72: ChatVM already applied')

print('batch72: OK')

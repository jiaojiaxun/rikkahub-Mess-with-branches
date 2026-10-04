#!/usr/bin/env python3
'''batch72: ChatVM handleMessageSend 加 quotedMessageId + 透传

#195 dump 实证：CI 形态 ChatVM 有两个 sendMessage 调用：
  line 101: sendMessage(_conversationId, next, true)   — 队列处理
  line 231: sendMessage(_conversationId, content, false) — handleMessageSend
全局搜索命中 2 个 → count != 1 → fail。

修复：从 handleMessageSend 签名行往下找第一个 sendMessage 调用（限定作用域）。
签名参数插入兼容带/不带尾逗号两种格式。

五查：Uuid import 已确认 / ChatVM 无在链脚本碰（batch70 跳过此文件）/
作用域从签名行起限定 / rfind(')') 插入零括号改动 / 可选参数兼容。
Python 三查：NL + 手写 concat / 无 f-string/walrus / 符号全定义。
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

    # 2. 透传：从 handleMessageSend 签名行往下找第一个 sendMessage 调用
    target = -1
    for index in range(sig, min(sig + 20, len(lines))):
        if 'chatService.sendMessage(' in lines[index]:
            target = index
            break
    if target < 0:
        print('batch72: dump handleMessageSend area (sig=' + str(sig) + '):')
        for index in range(max(0, sig - 2), min(sig + 25, len(lines))):
            print('  >> line ' + str(index) + ': ' + lines[index].strip()[:160])
        fail(CV, 'sendMessage call not found within handleMessageSend')

    old_line = lines[target]
    stripped = old_line.rstrip()
    if stripped.endswith(')'):
        pos = old_line.rfind(')')
        if pos > 0:
            before = old_line[:pos].rstrip()
            if before.endswith(','):
                lines[target] = old_line[:pos] + ' quotedMessageId' + old_line[pos:]
            else:
                lines[target] = old_line[:pos] + ', quotedMessageId' + old_line[pos:]
        else:
            fail(CV, 'no closing paren in sendMessage call')
    else:
        fail(CV, 'sendMessage call is multi-line; dump=' + old_line.strip()[:200])

    result = concat_lines(lines)
    if 'quotedMessageId' not in result:
        fail(CV, 'quotedMessageId missing after apply')
    (ROOT / CV).write_text(result, encoding='utf-8')
    print('batch72: ChatVM verified and patched (target line=' + str(target) + ')')
else:
    print('batch72: ChatVM already applied')

print('batch72: OK')

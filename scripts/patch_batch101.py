#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch101: ChatService emit ChatGenerationUpdate + ChatGenerationEnded

通知管理器(ChatNotificationManager)已移植(batch99),但 ChatService 没有发事件。
本 patch 在两个关键位置加 emit:
  A. 流式 chunk 处理处(.collect { chunk -> is GenerationChunk.Messages -> ... }):
     在 persistStreamingStateIfDue(conversationId) 之后 emit ChatGenerationUpdate
  B. 生成完成处(onCompletion { completionCause -> ... }):
     在 persistStreamingStateNow(conversationId, updateSearchIndex = true) 之后 emit ChatGenerationEnded

senderName 在作用域内(ChatService 生成函数里定义)。
chunk.messages.lastOrNull() = 流式最新消息。
updatedConversation 在 onCompletion 块内 = 生成完成后的对话。

五查:
1. import:零新增(AppEvent/AppEventBus/MessageRole/UIMessagePart 均已在 ChatService import)
2. 同文件冲突:ChatService.kt 被 batch59/70/95 碰过——但锚点在生成处理函数里,
   batch59 在 handleToolApproval、batch70/95 在 sendMessage,不重叠
3. 作用域:collect lambda 内(chunk/conversationId/senderName 可见);
   onCompletion lambda 内(updatedConversation/conversationId/senderName 可见)
4. 括号配对:插入块自平衡;插入前后全文配平不变
5. 函数签名:不改
Python 三查:引号 Q=chr(34)/NL 手写/helper 先定义/失败 exit(1)
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhNotifEmit'
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch101 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + CS + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


t = (ROOT / CS).read_text(encoding='utf-8')
if MARK in t:
    print('batch101: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    applied = []

    # ============================================================
    # A. 流式: persistStreamingStateIfDue(conversationId) 后 emit ChatGenerationUpdate
    # ============================================================
    STREAM_ANCHOR = 'persistStreamingStateIfDue(conversationId)'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == STREAM_ANCHOR]
    if len(hits) != 1:
        fail('persistStreamingStateIfDue anchor count=' + str(len(hits)), lines,
             hits[0] if hits else 0)
    si = hits[0]
    d = ind(lines[si])
    stream_block = [
        d + '',
        d + '// ' + MARK + ' (batch101): 通知管理器消费流式更新',
        d + 'chunk.messages.lastOrNull()?.let { lastMessage ->',
        d + '    appEventBus.tryEmit(',
        d + '        AppEvent.ChatGenerationUpdate(conversationId, lastMessage, senderName)',
        d + '    )',
        d + '}',
    ]
    lines[si + 1:si + 1] = stream_block
    applied.append('stream-emit')

    # ============================================================
    # B. 完成: persistStreamingStateNow(conversationId, updateSearchIndex = true) 后 emit ChatGenerationEnded
    # ============================================================
    DONE_ANCHOR = 'persistStreamingStateNow(conversationId, updateSearchIndex = true)'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == DONE_ANCHOR]
    if len(hits) != 1:
        fail('persistStreamingStateNow anchor count=' + str(len(hits)), lines,
             hits[0] if hits else 0)
    di = hits[0]
    d = ind(lines[di])
    done_block = [
        d + '',
        d + '// ' + MARK + ' (batch101): 通知管理器消费生成完成',
        d + 'runCatching {',
        d + '    val lastAssistantMsg = updatedConversation.messageNodes',
        d + '        .lastOrNull()?.messages?.lastOrNull { it.role == MessageRole.ASSISTANT }',
        d + '    val preview = lastAssistantMsg?.parts',
        d + '        ?.filterIsInstance<UIMessagePart.Text>()',
        d + '        ?.joinToString(' + Q + Q + ') { it.text }',
        d + '        ?.takeLast(200)',
        d + '    appEventBus.emit(',
        d + '        AppEvent.ChatGenerationEnded(',
        d + '            conversationId = conversationId,',
        d + '            senderName = senderName,',
        d + '            contentPreview = preview,',
        d + '        )',
        d + '    )',
        d + '}',
    ]
    lines[di + 1:di + 1] = done_block
    applied.append('done-emit')

    out = NL.join(lines)
    for need in [MARK, 'AppEvent.ChatGenerationUpdate(', 'AppEvent.ChatGenerationEnded(']:
        if need not in out:
            fail('selfcheck missing: ' + need)
    if balance(out) != bal0:
        fail('bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

    (ROOT / CS).write_text(out, encoding='utf-8')
    print('batch101: OK (' + ', '.join(applied) + ')')

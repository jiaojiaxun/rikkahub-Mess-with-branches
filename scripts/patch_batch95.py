#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch95: 修复引用功能两处独立缺陷

【缺陷1】AI 看不到引用(设计缺失,确凿)
  batch65→73 只把 quotedMessageId 作为 UIMessage 旁路字段存储,
  全链路无任何代码把被引文本注入 parts → 模型收不到引用内容。
  修法:sendMessage 内,按 quotedMessageId 查出被引消息文本,前置为 Text part 注入。

【缺陷2】UI 引用块不显示(渲染查找过窄)
  batch69 用 conversation.currentMessages.firstOrNull { it.id == quotedId } 找被引消息,
  而 currentMessages = messageNodes.map { it.messages[it.selectIndex] } 只含每节点
  【当前选中】的版本。被引消息若是重新生成过的助手消息(node 多版本),当 selectIndex
  未指向它时找不到 → 不渲染引用块。
  修法:改为在全量 messages(messageNodes.flatMap { it.messages })中查找。
  这是纯增强:查找范围从"每节点当前版本"扩为"全部版本",是原范围的超集。

五查:
1. import:UIMessagePart 已在 ChatService import;buildList/filterIsInstance 为 stdlib/内建
   → 零新增 import
2. 同文件冲突:ChatService.kt 被 batch70 碰过(仅 sendMessage 的 UIMessage 构造点插入
   quotedMessageId 行);本批锚点 = processedContent 行,在构造点【之前】,不重叠。
   ChatList.kt 被 batch69 碰过;本批锚点 = batch69 注入行本身,定向替换。
3. 作用域:注入块位于 appScope.launch 的 try 内,currentConversation/quotedMessageId 可见
4. 括号配对:buildList { } 自平衡;单行替换不改配平
5. 函数签名:不改任何签名

Python 三查:引号走 Q=chr(34) / NL 手写 concat / helper 先定义后用 / 失败显式 exit(1)
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhQuoteFix'
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'


def fail(path, msg, lines=None, around=-1):
    body = 'batch95 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + path + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


# ============================================================
# A. ChatService.sendMessage —— 注入被引文本
# ============================================================
cs = (ROOT / CS).read_text(encoding='utf-8')
if MARK in cs:
    print('batch95: ChatService already applied')
else:
    # 前置断言:batch70 必须已应用(否则 quotedMessageId 参数不存在,插入会编译错)
    if 'quotedMessageId' not in cs:
        fail(CS, 'quotedMessageId not present (batch70 not applied?)')
    lines = cs.split(NL)

    # 锚点:processedContent 赋值行(仓库态,未被 batch70 触碰)
    ANCHOR = 'val processedContent = preprocessUserInputParts(content, assistant)'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == ANCHOR]
    if len(hits) != 1:
        fail(CS, 'processedContent anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    i = hits[0]
    d = ind(lines[i])

    block = [
        d + '// ' + MARK + ' (batch95): 把被引消息文本注入,让模型能看到引用内容',
        d + 'val quotedContext = quotedMessageId?.let { qid ->',
        d + '    currentConversation.messageNodes',
        d + '        .flatMap { node -> node.messages }',
        d + '        .firstOrNull { msg -> msg.id == qid }',
        d + '        ?.parts',
        d + '        ?.filterIsInstance<UIMessagePart.Text>()',
        d + '        ?.joinToString(' + Q + NL + Q + ') { it.text }',
        d + '        ?.takeIf { it.isNotBlank() }',
        d + '}',
        d + 'val processedContent = buildList {',
        d + '    if (quotedContext != null) {',
        d + '        add(UIMessagePart.Text(' + Q + '以下是被引用的消息内容:' + Q + ' + ' + Q + NL + Q + ' + quotedContext + ' + Q + NL + Q + '))',
        d + '    }',
        d + '    addAll(preprocessUserInputParts(content, assistant))',
        d + '}',
    ]
    lines[i:i + 1] = block
    out = NL.join(lines)

    for need in [
        'val quotedContext = quotedMessageId?.let { qid ->',
        '.flatMap { node -> node.messages }',
        'val processedContent = buildList {',
        'addAll(preprocessUserInputParts(content, assistant))',
        MARK,
    ]:
        if need not in out:
            fail(CS, 'selfcheck missing: ' + need, lines, i)

    (ROOT / CS).write_text(out, encoding='utf-8')
    print('batch95: ChatService OK (quote text injected)')


# ============================================================
# B. ChatList —— 渲染查找改为全量 messages
# ============================================================
cl = (ROOT / CL).read_text(encoding='utf-8')
if 'rhQuoteFixWide' in cl:
    print('batch95: ChatList already applied')
else:
    OLD = 'val quotedMsg = conversation.currentMessages.firstOrNull { it.id == quotedId }'
    if OLD not in cl:
        fail(CL, 'batch69 quotedMsg anchor not found (batch69 not applied?)')
    NEW = 'val quotedMsg = conversation.messageNodes.flatMap { it.messages }.firstOrNull { it.id == quotedId } // rhQuoteFixWide'
    cl2 = cl.replace(OLD, NEW, 1)
    if NEW not in cl2:
        fail(CL, 'selfcheck: wide lookup missing')
    if cl2.count('rhQuoteFixWide') != 1:
        fail(CL, 'selfcheck: marker count != 1')
    (ROOT / CL).write_text(cl2, encoding='utf-8')
    print('batch95: ChatList OK (wide message lookup)')

print('batch95: OK (quote text injection + robust render lookup)')

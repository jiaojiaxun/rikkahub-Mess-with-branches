#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch95 v2: 修复引用功能两处缺陷(修 v1 的 Kotlin 换行转义 bug)

v1(#build ba4aeb4)死因:ChatService.kt:631-639 Syntax error: Expecting '"'。
根因:我在 Kotlin 字符串内容里用了【真实换行符】(Q + NL + Q 拼成 " <换行> "),
     Kotlin 字符串字面量不接受字面换行,必须写转义序列 \n(反斜杠+n)。
     我把 Python 的 NL(chr(10))同时当成了「拼行」和「Kotlin 源码里的 \n」两种角色。
v2 修法:引入 KNL = chr(92) + 'n'(反斜杠+n),专用于 Kotlin 源码字符串内容;
    真实 NL 只用于 Python 拼行。全脚本所有 Kotlin 内的换行一律用 KNL。

【缺陷1】AI 看不到引用(设计缺失)
  修法:sendMessage 内按 quotedMessageId 查出被引消息文本,前置注入为 Text part。
【缺陷2】UI 引用块不显示(渲染查找过窄)
  batch69 用 conversation.currentMessages(仅每节点当前版本)查找;
  改为 messageNodes.flatMap { it.messages }(全部版本,原范围的超集)。

五查:
1. import:UIMessagePart 已在 ChatService import;buildList/filterIsInstance 内建 → 零新增
2. 同文件冲突:ChatService 被 batch70 碰过(仅 UIMessage 构造点);锚点 processedContent 行在其前。
   ChatList 定向替换 batch69 注入行本身。
3. 作用域:注入块在 appScope.launch try 内,currentConversation/quotedMessageId 可见
4. 括号配对:buildList { } 自平衡;单行替换不改配平
5. 函数签名:不改
Python 三查:引号 Q/普通 / KNL=反斜杠+n 专用于 Kotlin 串内换行 / NL 仅拼行 / 无 f-string / 失败 exit(1)
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)          # Python 拼行用(真实换行)
Q = chr(34)           # 双引号
KNL = chr(92) + 'n'   # Kotlin 源码字符串里的换行转义 \n(反斜杠+n)——不是真实换行!
MARK = 'rhQuoteFix'
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'


def fail(path, msg, lines=None, around=-1):
    body = 'batch95v2 ' + str(msg)
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
    print('batch95v2: ChatService already applied')
else:
    if 'quotedMessageId' not in cs:
        fail(CS, 'quotedMessageId not present (batch70 not applied?)')
    lines = cs.split(NL)

    ANCHOR = 'val processedContent = preprocessUserInputParts(content, assistant)'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == ANCHOR]
    if len(hits) != 1:
        fail(CS, 'processedContent anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    i = hits[0]
    d = ind(lines[i])

    # KNL 用于 Kotlin 串内换行;NL 仅拼行
    block = [
        d + '// ' + MARK + ' (batch95): 把被引消息文本注入,让模型能看到引用内容',
        d + 'val quotedContext = quotedMessageId?.let { qid ->',
        d + '    currentConversation.messageNodes',
        d + '        .flatMap { node -> node.messages }',
        d + '        .firstOrNull { msg -> msg.id == qid }',
        d + '        ?.parts',
        d + '        ?.filterIsInstance<UIMessagePart.Text>()',
        d + '        ?.joinToString(' + Q + KNL + Q + ') { it.text }',
        d + '        ?.takeIf { it.isNotBlank() }',
        d + '}',
        d + 'val processedContent = buildList {',
        d + '    if (quotedContext != null) {',
        d + '        add(UIMessagePart.Text(' + Q + '以下是被引用的消息内容:' + Q + ' + ' + Q + KNL + Q + ' + quotedContext + ' + Q + KNL + Q + '))',
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

    # 反斜杠+n 必须是【两字符】序列,不得是真实换行
    if (Q + KNL + Q) not in out:
        fail(CS, 'KNL escape not emitted as backslash-n', lines, i)

    (ROOT / CS).write_text(out, encoding='utf-8')
    print('batch95v2: ChatService OK (quote text injected, \\n escaped)')


# ============================================================
# B. ChatList —— 渲染查找改为全量 messages
# ============================================================
cl = (ROOT / CL).read_text(encoding='utf-8')
if 'rhQuoteFixWide' in cl:
    print('batch95v2: ChatList already applied')
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
    print('batch95v2: ChatList OK (wide message lookup)')

print('batch95v2: OK')

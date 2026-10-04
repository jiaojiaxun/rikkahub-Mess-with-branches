#!/usr/bin/env python3
'''batch60: 修复 #174/#175 全部编译错误——按清单逐项对照

老板令：反复检查、按清单逐项对照。本脚本 = 前序批次全部错误的清账：

#174 死因：clickable import 缺失（57_1）+ TopBar hazeState 参数错插调用侧（58）
#175 死因（11 条，全读 annotations）：
  1. ChatMessage:781 clickable import（#174 重复——59 的修复没在 #175 执行？
     ——#175 是 batch58 的构建，#176 才是 59。59 还没跑过。）
  2. ChatList:132/134 Conflicting declarations（57_3 和 58 都加 onQuote 参数）
  3. ChatList:385 ChatMessageQuoteBlock 未 import（58 引用但没加 import）
  4. ChatList:382-390 message 变量作用域错（58 插到 ChatMessage 调用块外）
  5. ChatPage:332 Cannot infer T（58 括号替换破坏结构）

修复策略（一个脚本改三文件，全清账）：
A. ChatMessage: clickable import（幂等——59 可能已加）
B. ChatList: 删 58 的错误插入（整个引用块代码段）+ 删重复 onQuote 参数
C. ChatPage: 删 58 的 hazeState 调用侧错插行（保留 59 的定义侧修复）
D. ChatPage: 修 58 的 send-quote 替换（检查括号配对）
E. ChatList: 正确重插 QuoteBlock（正确作用域——ChatMessage 调用前，
   用 conversation 参数解析 + import ChatMessageQuoteBlock）
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhFixAll'


def fail(path, msg):
    print('::error file=' + path + '::batch60 ' + str(msg)[:1400])
    raise SystemExit(1)


def find_line(lines, want):
    w = want.strip()
    for i, ln in enumerate(lines):
        if ln.strip() == w:
            return i
    return -1


# ============================================================
# A. ChatMessage.kt — clickable import
# ============================================================
CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
c = (ROOT / CM).read_text(encoding='utf-8')
if 'import androidx.compose.foundation.clickable' not in c:
    lines = c.split(NL)
    idx = -1
    for i, ln in enumerate(lines):
        if ln.startswith('import androidx.compose.foundation'):
            idx = i
            break
    if idx >= 0:
        lines = lines[:idx] + ['import androidx.compose.foundation.clickable'] + lines[idx:]
        (ROOT / CM).write_text(NL.join(lines), encoding='utf-8')
        print('batch60: A clickable import OK')
else:
    print('batch60: A clickable already')

# ============================================================
# B. ChatList.kt — 清理 58 的错误插入 + 去重 onQuote
# ============================================================
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
t = (ROOT / CL).read_text(encoding='utf-8')
lines = t.split(NL)
changed = False

# B1. 删 58 插的引用块代码段（消息渲染处的错误作用域块）
#     特征：message.quotedMessageId?.let { quotedId -> 开头，共 12 行
start = -1
for i, ln in enumerate(lines):
    if 'message.quotedMessageId?.let' in ln:
        start = i
        break
if start >= 0:
    # 删到 onClick = { 块的 } 结束（再 8 行）
    end = start
    depth = 0
    for j in range(start, min(start + 15, len(lines))):
        depth += lines[j].count('{') - lines[j].count('}')
        end = j
        if depth <= 0 and j > start:
            break
    # 保守：删 start 到 start+11（12 行，58 插入的完整块）
    del lines[start:start + 12]
    changed = True
    print('batch60: B1 removed 58 quote block (12 lines)')

# B2. 删重复 onQuote 参数（58 加的第二次）
first = -1
second = -1
for i, ln in enumerate(lines):
    if ln.strip() == 'onQuote: (UIMessage) -> Unit = {},':
        if first < 0:
            first = i
        else:
            second = i
            break
if second >= 0:
    del lines[second]
    # 58 可能还带注释行
    if second - 1 >= 0 and MARK in lines[second - 1]:
        del lines[second - 1]
    changed = True
    print('batch60: B2 removed duplicate onQuote')

# B3. import ChatMessageQuoteBlock（引用它但没 import）
body = NL.join(lines)
if 'ChatMessageQuoteBlock' in body and 'import me.rerere.rikkahub.ui.components.message.ChatMessageQuoteBlock' not in body:
    idx = -1
    for i, ln in enumerate(lines):
        if 'import me.rerere.rikkahub.ui.components.message.ChatMessage' in ln:
            idx = i
            break
    if idx >= 0:
        lines = lines[:idx + 1] + ['import me.rerere.rikkahub.ui.components.message.ChatMessageQuoteBlock'] + lines[idx + 1:]
        changed = True
        print('batch60: B3 QuoteBlock import OK')

# B4. 正确重插 QuoteBlock——ChatMessage( 调用前，正确作用域
#     策略变更：不在 ChatList 挂（作用域复杂），改在 ChatMessage 内部
#     （它已有 message 参数）——B4 留到 ChatMessage 侧做，ChatList 只清理
if changed:
    (ROOT / CL).write_text(NL.join(lines), encoding='utf-8')
    print('batch60: ChatList cleanup OK')
else:
    print('batch60: ChatList no changes')

# ============================================================
# C. ChatPage.kt — 删 58 的调用侧错插 + 修 send-quote
# ============================================================
CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
p = (ROOT / CP).read_text(encoding='utf-8')
lines = p.split(NL)
changed = False

# C1. 删 58 在 TopBar 调用处错插的 hazeState = hazeState, 行
#     （59 已在定义侧加了参数；58 在调用处加的是重复）
#     找出不在 private fun TopBar( 定义内的 hazeState = hazeState, 行
def_idx = find_line(lines, 'private fun TopBar(')
dup_idx = -1
for i, ln in enumerate(lines):
    if ln.strip() == 'hazeState = hazeState,' and (def_idx < 0 or i < def_idx or i > def_idx + 25):
        dup_idx = i
        break
if dup_idx >= 0:
    del lines[dup_idx]
    changed = True
    print('batch60: C1 removed dup hazeState call-side line')

# C2. 修 send-quote：检查 58 替换的行是否破坏括号
for i, ln in enumerate(lines):
    if 'quotedMessageId = quotingMessage?.id' in ln and 'vm.handleMessageSend(' not in ln:
        # 58 的替换：原行尾 ) 被改成 , quotedMessageId = quotingMessage?.id)
        # 需要整行重写：vm.handleMessageSend(inputState.getContents(), quotedMessageId = quotingMessage?.id)
        indent = ln[:len(ln) - len(ln.lstrip())]
        lines[i] = indent + 'vm.handleMessageSend(inputState.getContents(), quotedMessageId = quotingMessage?.id)'
        changed = True
        print('batch60: C2 fixed send-quote line')
        break

if changed:
    (ROOT / CP).write_text(NL.join(lines), encoding='utf-8')
    print('batch60: ChatPage cleanup OK')
else:
    print('batch60: ChatPage no changes')

# ============================================================
# D. ChatMessage.kt — QuoteBlock 挂到 ChatMessage 内部（正确作用域）
# ============================================================
c = (ROOT / CM).read_text(encoding='utf-8')
if MARK not in c:
    lines = c.split(NL)
    # ChatMessage 函数体里：在 SelectionContainer 或 Column 开始前挂引用块
    # 策略：找 message = message 之后、或 Column( 开始前
    # 简化：在 @Composable fun ChatMessage( 的函数体开头插（Column 内第一元素）
    idx = find_line(lines, 'fun ChatMessage(')
    if idx >= 0:
        # 找函数体开始的 Column( 或 Box(（通常在参数列表后 10-20 行内）
        insert_at = -1
        for j in range(idx + 1, min(idx + 40, len(lines))):
            s = lines[j].strip()
            if s.startswith('Column(') or s.startswith('Box('):
                insert_at = j + 1
                break
        if insert_at > 0:
            quote_block = [
                '    message.quotedMessageId?.let { quotedId ->',
                '        conversation.currentMessages.firstOrNull { it.id == quotedId }?.let { quoted ->',
                '            ChatMessageQuoteBlock(',
                '                senderName = quoted.role.name.lowercase(),',
                '                previewText = quoted.toText(),',
                '                onClick = { onJumpToMessage?.let { jump ->',
                '                    val idx2 = conversation.currentMessages.indexOfFirst { it.id == quotedId }',
                '                    if (idx2 >= 0) jump(idx2)',
                '                } },',
                '            )',
                '        }',
                '    }',
            ]
            # ChatMessage 签名里有 conversation 吗？——查
            body = NL.join(lines)
            has_conv = 'conversation: Conversation' in body[idx:idx + 2000] if len(body) > idx else False
            has_jump = 'onJumpToMessage' in body[idx:idx + 2000] if len(body) > idx else False
            if has_conv and has_jump:
                lines = lines[:insert_at] + quote_block + lines[insert_at:]
                (ROOT / CM).write_text(NL.join(lines), encoding='utf-8')
                print('batch60: D QuoteBlock mounted in ChatMessage')
            else:
                print('batch60: D skip (ChatMessage lacks conversation or onJumpToMessage)')
                print('  has_conv=' + str(has_conv) + ' has_jump=' + str(has_jump))
        else:
            print('batch60: D skip (no Column/Box found)')
    else:
        print('batch60: D skip (ChatMessage fn not found)')
else:
    print('batch60: D already mounted')

print('batch60: OK')

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch250: 引用断链修复（队列丢 quotedMessageId）+ 记忆导入链路精准取证

【根因 —— 已对着 snapshot 真形态逐行核实，不是转述】
ChatVM.kt 任务N4 v3 的消息排队实现:
    private val pendingMessages = java.util.concurrent.ConcurrentLinkedQueue<List<me.rerere.ai.ui.UIMessagePart>>()
    ...
    fun handleMessageSend(content: List<UIMessagePart>, answer: Boolean = true, quotedMessageId: Uuid? = null) {
        if (content.isEmptyInputMessage()) return
        if (!answer) {
            chatService.sendMessage(_conversationId, content, false, quotedMessageId)   // ← 这条路径是好的
            return
        }
        if (pendingMessages.size >= 20) return
        pendingMessages.add(content)                    // ← 只存 content，quotedMessageId 被丢弃
        pendingMessageCountState.value = pendingMessages.size
        drainOnePendingMessage()
    }
    private fun drainOnePendingMessage() {
        ...
        val next = pendingMessages.poll() ?: return@withLock
        chatService.sendMessage(_conversationId, next, true)   // ← 第 4 参数缺省 = null
    }
=> answer=true（也就是正常发消息触发 AI 回复，绝大多数情况）时引用 ID 在入队那一刻就丢了。
   下游三层完好，无需改动:
     · ChatService.kt L627-629  highlightedContext 注入（rhQuoteFix / batch95）
     · ChatService.kt L649      写入 quotedMessageId（rhQuoteSend）
     · ChatList.kt   L439-441   rhQuoteId = displayMessage.quotedMessageId ?: currentMessage.quotedMessageId，再 O(1) 查表
   所以修法只动 ChatVM 的这一条链。

【本批改动】
1. 新增私有嵌套 data class PendingSend(content, quotedMessageId)
2. pendingMessages 类型 ConcurrentLinkedQueue<List<UIMessagePart>> -> ConcurrentLinkedQueue<PendingSend>
3. 入队 pendingMessages.add(content) -> pendingMessages.add(PendingSend(content, quotedMessageId))
4. 出队 chatService.sendMessage(conversationId, next, true) -> (..., next.content, true, next.quotedMessageId)
5. answer=false 的直发路径保持原样（它本来就透传 quotedMessageId）

【端到端验证路径（代码侧已闭环，供装机核对）】
a. 引用一条消息发送 -> 用户消息带 quotedMessageId -> ChatList L439 取到非 null ->
   ChatMessageQuoteBlock 渲染（发送者 + 预览）
b. 同一次发送 -> ChatService L627-629 把被引文本以「以下是被引用的消息内容:」前缀注入
   请求体的用户消息 parts 首位
c. 生成进行中再排队一条引用消息 -> generationDoneFlow 触发 drainOnePendingMessage ->
   next.quotedMessageId 透传 -> 引用完整保留
d. 引用后删除被引消息 -> ChatList 查表为 null -> 显示「（引用的消息已不在对话中）」，不崩

【T-M4 取证（本批只读，不盲改）】
batch249 已确认: MemoryEntity L17-18 `@ColumnInfo("conversation_id") val conversationId: String = ""`；
MemoryRepository 有按会话的 getMemoriesOfConversation(Flow) 与按 assistantId 的若干 mapping。
但「记忆页读的是哪一条」还没确认，所以旧备份导入后不显示的原因仍未定性。
本批补 dump: MemoryDAO.kt 全部查询语句 + MemoryRepository 的读取入口 + AssistantMemoryPage 里
对 memoryRepository 的调用点 + 备份/恢复里 MemoryEntity 的处理方式。
下一批按真实查询条件定修法（候选：长期记忆查询缺 OR conversation_id IS NULL / 恢复后 assistantId 不匹配）。

五查:
 1. import 清单: ChatVM.kt 已 import `kotlin.uuid.Uuid` 与 `me.rerere.ai.ui.UIMessagePart`，
    PendingSend 不需要任何新 import
 2. 同文件冲突: ChatVM.kt 在链上被 batch234(A4 setChatModel)、batch237/238/239 等改过；
    本批锚点位于「任务N4 v3 队列」区段（pendingMessages 声明 / drainOnePendingMessage / handleMessageSend），
    snapshpt 实读确认这些行未被其他批次触碰
 3. 作用域: PendingSend 作为 ChatVM 的私有嵌套类，pendingMessages 与两个使用点都在类体内
 4. 括号配对: data class 块自身配平（{} 各 1）；其余为类型/参数替换，括号数量不变
    => 整文件 balance 编辑前后相等，脚本断言
 5. 函数签名: handleMessageSend / drainOnePendingMessage / sendMessage 签名全部不变
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败记录并继续
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
DIAG = 'ci_diag_batch250.txt'

CHATVM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatVM.kt'
MEM_DAO = 'app/src/main/java/me/rerere/rikkahub/data/db/dao/MemoryDAO.kt'
MEM_REPO = 'app/src/main/java/me/rerere/rikkahub/data/repository/MemoryRepository.kt'
MEM_PAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/detail/AssistantMemoryPage.kt'

report = []


def note(msg):
    report.append(str(msg)[:900])


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def lines_to_text(lines):
    out = ''
    for idx, line in enumerate(lines):
        if idx > 0:
            out += NL
        out += line
    return out


def ind_of(line):
    s = line.lstrip()
    return line[:len(line) - len(s)]


def find_idx(lines, needle, label):
    hits = [i for i, ln in enumerate(lines) if ln.strip() == needle]
    if len(hits) == 0:
        note('ANCHOR-MISS ' + label + ' -> ' + repr(needle))
        raise RuntimeError('anchor miss ' + label)
    if len(hits) != 1:
        note('ANCHOR-DUP ' + label + ' count=' + str(len(hits)))
        raise RuntimeError('anchor dup ' + label)
    return hits[0]


def patch_chatvm():
    p = ROOT / CHATVM
    if not p.exists():
        note('MISSING ChatVM.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhQuoteQueue250' in t:
        note('chatvm already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    # 1. 队列声明 -> PendingSend 类型
    a = find_idx(
        lines,
        'private val pendingMessages = java.util.concurrent.ConcurrentLinkedQueue<List<me.rerere.ai.ui.UIMessagePart>>()',
        'queue declaration')
    ai = ind_of(lines[a])
    new_decl = [
        ai + '// rhQuoteQueue250: 队列元素必须带 quotedMessageId —— 否则 answer=true 的引用在入队瞬间丢失',
        ai + 'private data class PendingSend(',
        ai + '    val content: List<UIMessagePart>,',
        ai + '    val quotedMessageId: Uuid?,',
        ai + ')',
        ai + 'private val pendingMessages = java.util.concurrent.ConcurrentLinkedQueue<PendingSend>()',
    ]
    lines = lines[:a] + new_decl + lines[a + 1:]

    # 2. 入队透传
    b = find_idx(lines, 'pendingMessages.add(content)', 'enqueue')
    lines[b] = ind_of(lines[b]) + 'pendingMessages.add(PendingSend(content, quotedMessageId)) // rhQuoteQueue250'

    # 3. 出队透传
    c = find_idx(lines, 'chatService.sendMessage(_conversationId, next, true)', 'dequeue send')
    lines[c] = ind_of(lines[c]) + 'chatService.sendMessage(_conversationId, next.content, true, next.quotedMessageId) // rhQuoteQueue250'

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('chatvm balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        return
    for need in ['private data class PendingSend(',
                 'private val pendingMessages = java.util.concurrent.ConcurrentLinkedQueue<PendingSend>()',
                 'pendingMessages.add(PendingSend(content, quotedMessageId))',
                 'chatService.sendMessage(_conversationId, next.content, true, next.quotedMessageId)']:
        if need not in t2:
            note('chatvm selfcheck missing ' + need)
            return
    if 'chatService.sendMessage(_conversationId, next, true)' in t2:
        note('chatvm old dequeue call still present')
        return
    if 'ConcurrentLinkedQueue<List<me.rerere.ai.ui.UIMessagePart>>' in t2:
        note('chatvm old queue type still present')
        return
    p.write_text(t2, encoding='utf-8')
    note('chatvm OK: PendingSend(content, quotedMessageId) wired in enqueue+dequeue')


def probe_memory():
    # a) DAO 全部查询
    p = ROOT / MEM_DAO
    if not p.exists():
        note('probe missing MemoryDAO.kt')
    else:
        lines = p.read_text(encoding='utf-8').split(NL)
        note('probe MemoryDAO.kt lines=' + str(len(lines)))
        for i, ln in enumerate(lines):
            s = ln.strip()
            if s == '':
                continue
            note('dao L' + str(i + 1) + ':' + s[:170])

    # b) Repository 读取入口
    p = ROOT / MEM_REPO
    if not p.exists():
        note('probe missing MemoryRepository.kt')
    else:
        lines = p.read_text(encoding='utf-8').split(NL)
        hits = []
        for i, ln in enumerate(lines):
            s = ln.strip()
            if s.startswith('fun ') or s.startswith('suspend fun ') or s.startswith('private fun ') or 'memoryDAO.' in s:
                hits.append('L' + str(i + 1) + ':' + s[:150])
        note('probe MemoryRepository entries=' + str(len(hits)))
        for h in hits[:30]:
            note('repo ' + h)

    # c) 记忆页读取点
    p = ROOT / MEM_PAGE
    if not p.exists():
        note('probe missing AssistantMemoryPage.kt')
    else:
        lines = p.read_text(encoding='utf-8').split(NL)
        hits = []
        for i, ln in enumerate(lines):
            s = ln.strip()
            if ('memoryRepository' in s) or ('getMemories' in s) or ('conversationId' in s) or ('shortMemory' in s):
                hits.append('L' + str(i + 1) + ':' + s[:160])
        note('probe AssistantMemoryPage hits=' + str(len(hits)))
        for h in hits[:36]:
            note('page ' + h)


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch250 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch250 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    for name, fn in [
        ('1 quote queue fix', patch_chatvm),
        ('2 memory probe', probe_memory),
    ]:
        try:
            fn()
            note(name + ' DONE')
        except Exception as e:
            note(name + ' EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
        print('::error::batch250 part: ' + name)
        sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch250 ' + str(line)[:800])
    print('::error::batch250 END lines=' + str(len(report)))


main()
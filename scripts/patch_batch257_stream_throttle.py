#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch257: 流式状态推送节流（T-P2）—— 对 GenerationChunk 快照流做 80ms 采样

【为什么这一层可以丢中间帧（与之前"conflate 会丢字"的判断分层）】
· providerHandler.streamText() 产出的是**增量** chunk（每块只带新增文本）—— 绝对不能丢，丢了就是永久缺字。
· GenerationHandler.generateText() 产出的是 `Flow<GenerationChunk>`，其
  `emit(GenerationChunk.Messages(messages))` 里的 messages 是**完整消息快照**（实读确认，见
  GenerationHandler 内 onUpdateMessages = { messages = it.transforms(...); emit(...) }）。
  ⇒ 丢中间快照只丢"中间画面"，不丢内容：最后一次到达即可。
本批只在**下游 collect 这一层**做采样，绝不碰 provider 的增量流。

【现状（ChatService 实读）】
    ).onCompletion { completionCause -> ... }        // 结束兜底：finishReasoning + updateConversation + 落库
     .collect { chunk -> when (chunk) { is GenerationChunk.Messages -> {
            val currentConversation = getConversationFlow(conversationId).value
            val updatedConversation = currentConversation.updateCurrentMessages(chunk.messages)
            updateConversation(conversationId, updatedConversation)   // 每帧重建 + 写 StateFlow
            markStreamingPersistence(...); persistStreamingStateIfDue(...)
            appEventBus.tryEmit(ChatGenerationUpdate(...))            // 每帧发通知事件
            ...
     }}}
=> 长上下文时每个 chunk 都做 O(全文) 的 updateCurrentMessages + 一次 StateFlow 写入 + 一次事件；
   即使 batch251 已经把整条管线挪到 IO（不再卡主线程），这层仍是无效重复工作，
   并且 StateFlow 高频变更会放大 UI 侧重组压力。

【修法（一处，最小）】
在 generateText(...) 之后、onCompletion 之前插入 `.sample(80.milliseconds)`：
    ).sample(80.milliseconds) // rhUiThrottle257
     .onCompletion { ... }
· sample 每 80ms 只放行最新一帧（丢弃中间帧，不丢内容）
· 流结束时 sample 会放行最后一个挂起值；即使极端情况下没放行，
  onCompletion 本来就会做一次 `updateConversation` + `persistStreamingStateNow`
  （实读确认，含 finishReasoning 与 NonCancellable 落库），最终状态不会丢
· 工具"开始执行但无输出"的立即落库标记最多延后 80ms，仍会在 onCompletion 补写

五查:
 1. import 清单: 需要 kotlinx.coroutines.flow.sample 与 kotlin.time.Duration.Companion.milliseconds；
    脚本检查存在才补（已存在则跳过），锚点用 import kotlinx.coroutines.flow.first
 2. 同文件冲突: ChatService.kt 被 batch95/232/233/234/235/238/251 改过；
    本批锚点是 generateText 调用结束的 `},` + `).onCompletion { completionCause ->` 两行窗口，
    与上述落点不重叠（251 改的是 sendMessage 的 launch，不在这条链）
 3. 作用域: 纯 Flow 操作符插入，不引入任何新符号到函数体
 4. 括号配对: 新增 `.sample(80.milliseconds)` 含 1 对括号 => balance 不变（断言）
 5. 函数签名: 零改动
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败记录并继续

【可回退】
把 `.sample(80.milliseconds)` 那行删掉即恢复原行为，不涉及任何状态迁移。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch257.txt'

CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'

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


def patch():
    p = ROOT / CS
    if not p.exists():
        note('MISSING ChatService.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhUiThrottle257' in t:
        note('chatService already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    # 1. 定位 generateText 调用结束 + onCompletion
    anchor = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == ').onCompletion { completionCause ->':
            prev = lines[i - 1].strip()
            if prev in ('},', ')'):
                anchor = i
                break
    if anchor < 0:
        note('ANCHOR-MISS generateText -> onCompletion window')
        return

    ind = ind_of(lines[anchor])
    lines = lines[:anchor] + [
        ind + '// rhUiThrottle257: 状态推送节流 —— GenerationChunk 是完整快照，可安全丢弃中间帧；'
        + 'onCompletion 仍会补一次最终 updateConversation + 落库',
        ind + '.sample(80.milliseconds)',
    ] + lines[anchor:]

    # 2. import sample
    t2 = lines_to_text(lines)
    if 'import kotlinx.coroutines.flow.sample' not in t2:
        a = find_idx(lines, 'import kotlinx.coroutines.flow.first', 'flow.first import anchor')
        lines = lines[:a] + ['import kotlinx.coroutines.flow.sample // rhUiThrottle257'] + lines[a:]

    # 3. import milliseconds
    t2 = lines_to_text(lines)
    if 'import kotlin.time.Duration.Companion.milliseconds' not in t2:
        b = -1
        for i, ln in enumerate(lines):
            if ln.strip() == 'import kotlin.time.Instant':
                b = i
                break
        if b >= 0:
            lines = lines[:b + 1] + ['import kotlin.time.Duration.Companion.milliseconds // rhUiThrottle257'] + lines[b + 1:]
        else:
            note('milliseconds import anchor(kotlin.time.Instant) not found; skip import')

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('chatService balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        return
    for need in ['import kotlinx.coroutines.flow.sample',
                 '.sample(80.milliseconds)']:
        if need not in t2:
            note('chatService selfcheck missing ' + need)
            return
    if 'import kotlin.time.Duration.Companion.milliseconds' not in t2:
        note('chatService WARNING: milliseconds import missing, .sample() may not compile')
    p.write_text(t2, encoding='utf-8')
    note('chatService OK: GenerationChunk flow sampled at 80ms')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch257 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch257 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    try:
        patch()
        note('1 ui throttle DONE')
    except Exception as e:
        note('1 ui throttle EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::batch257 part: ui throttle')
    sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch257 ' + str(line)[:800])
    print('::error::batch257 END lines=' + str(len(report)))


main()
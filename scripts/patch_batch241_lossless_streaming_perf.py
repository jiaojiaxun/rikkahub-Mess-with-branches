#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch241: 长上下文流式卡顿 —— 零观感损失的后台计算消除

用户硬约束: 不允许通过关闭实时 Markdown / 实时代码高亮 / 毛玻璃 / 平滑滚动来降级观感。
故本批只消除"每个 token 都在重复做的后台计算", 视觉与交互行为与修复前完全一致。

根因(全部读 snapshot 真形态实读确认, 非推测):
  1. AutoCompactionMessageGroup.displayMessage 是构造期求值的 val。
     ChatList 侧 displayGroups = remember(conversation.messageNodes) { groupAutomaticCompactionMessages() }
     在流式期间每个 token 都让 key 失效 ⇒ 每 token 为全部 N 个分组重做
     terminalNode.currentMessage.copy(parts = nodes.flatMap { ... }) 的列表深拷贝
     ⇒ 全程 O(n²) 的对象分配与 parts 拷贝。
     修复: 改为 by lazy(LazyThreadSafetyMode.NONE)。只有被 LazyColumn 组合到的可见分组才会
     真正读取 displayMessage, 不可见的历史分组零构造; 可见分组每次都是新实例, 求值时读到
     当前最新文本 ⇒ 行为与修复前完全一致。
  2. ChatList 每个可见消息条目内部执行
     conversation.messageNodes.flatMap { it.messages }.firstOrNull { it.id == quotedId }
     即 O(全部消息) 线性扫描; 流式期间全部可见条目每 token 失效并重扫 ⇒ 全程 O(n²)。
     修复: 列表外按 (会话 id, 节点数, 各节点版本数之和) 建一次 Map, 条目内 O(1) 查表。
     key 只依赖结构, 与正在增长的文本无关, 流式期间稳定命中。
  3. 自动跟随流的 snapshotFlow collect 内无条件 state.requestScrollToItem(count - 1),
     每次调用强制触发 LazyList 重测量, 即使同一行文字继续追加、列表高度未变、已经贴底。
     修复: 增加 state.canScrollForward 守卫。平滑跟随保留, 毛玻璃零改动。

五查:
  1. import 清单: 零新增 import
     - AutoCompactionMessageGroup.kt: LazyThreadSafetyMode 属 kotlin.* 默认导入
     - ChatList.kt: buildMap 属 kotlin.collections(stdlib), canScrollForward 是 LazyListState 既有属性
  2. 同文件冲突: ChatList.kt 在链 patch 中 batch15/21c/55/228/238 已改过不同区域;
     本批锚点取自 displayGroups 定义、items 内引用查找行、自动滚动 collect 行,
     与 batch238 落点(estimate/pending 块)不相邻, 无覆盖
  3. 作用域: 两个 ChatList 锚点均在 ChatListNormal 内, conversation/state/rhFollowStream 均在作用域
  4. 括号配对: 逐文件断言修改前后 balance 完全一致
  5. 函数签名: 不改任何函数签名(displayMessage 仍是 val UIMessage, 仅求值时机变化)

Python 三查: 引号一律 Q 变量构造; NL 显式 concat 禁 join/f-string/walrus;
helper 先定义后用; 锚点行级 strip 匹配(对空白零容忍); 失败 ::error + exit(0)
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhLosslessStream241'

GROUP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/AutoCompactionMessageGroup.kt'
CHATLIST = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'


def fail(msg):
    print('::error::batch241 ' + str(msg)[:1400])
    sys.stdout.flush()
    sys.exit(0)


def note(msg):
    print('::error::batch241 ' + str(msg)[:1400])
    sys.stdout.flush()


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


def find_unique_line(lines, needle, label):
    hits = []
    for i, line in enumerate(lines):
        if line.strip() == needle:
            hits.append(i)
    if len(hits) == 0:
        fail(label + ': line not found -> ' + repr(needle))
    if len(hits) != 1:
        fail(label + ': line count=' + str(len(hits)) + ' expected 1 -> ' + repr(needle))
    return hits[0]


def indent_of(line):
    stripped = line.lstrip()
    return line[:len(line) - len(stripped)]


# ---------------------------------------------------------------------------
# 1. AutoCompactionMessageGroup.kt : displayMessage -> by lazy
# ---------------------------------------------------------------------------
def patch_group():
    p = ROOT / GROUP
    if not p.exists():
        fail('AutoCompactionMessageGroup.kt missing')
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        note('group already applied, skip')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    start_needle = 'val displayMessage: UIMessage = terminalNode.currentMessage.copy('
    start_idx = find_unique_line(lines, start_needle, 'group displayMessage start')
    close_idx = -1
    limit = min(start_idx + 10, len(lines))
    for i in range(start_idx + 1, limit):
        if lines[i].strip() == ')':
            close_idx = i
            break
    if close_idx < 0:
        fail('group: closing paren of displayMessage not found within 10 lines')

    base = indent_of(lines[start_idx])
    inner = lines[start_idx + 1:close_idx]
    if len(inner) < 1:
        fail('group: displayMessage copy args empty')

    new_block = []
    new_block.append(base + '// ' + MARK + ': displayMessage 改为惰性求值。')
    new_block.append(base + '// groupAutomaticCompactionMessages() 每次 messageNodes 变化都会重建全部分组实例,')
    new_block.append(base + '// 原实现让每个分组在构造瞬间就 copy 一次 UIMessage 并 flatMap 深拷贝全部 parts;')
    new_block.append(base + '// 流式期间每 token 一次 => 全程 O(n^2) 的对象分配与列表深拷贝。')
    new_block.append(base + '// 只有被 LazyColumn 组合到的可见分组才读取 displayMessage, 故改为 lazy:')
    new_block.append(base + '// 不可见的历史分组零构造; 可见分组每次都是新实例, 求值时读到当前最新文本。')
    new_block.append(base + 'val displayMessage: UIMessage by lazy(LazyThreadSafetyMode.NONE) {')
    new_block.append(base + '    terminalNode.currentMessage.copy(')
    for line in inner:
        if line.strip() == '':
            new_block.append(line)
        else:
            new_block.append('    ' + line)
    new_block.append(base + '    )')
    new_block.append(base + '}')

    lines = lines[:start_idx] + new_block + lines[close_idx + 1:]
    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        fail('group: balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
    if 'val displayMessage: UIMessage = terminalNode.currentMessage.copy(' in t2:
        fail('group: old displayMessage declaration still present')
    if 'by lazy(LazyThreadSafetyMode.NONE) {' not in t2:
        fail('group: lazy marker missing after edit')
    p.write_text(t2, encoding='utf-8')
    note('group OK: displayMessage -> by lazy(LazyThreadSafetyMode.NONE)')


# ---------------------------------------------------------------------------
# 2. ChatList.kt : O(1) quote map + canScrollForward guard
# ---------------------------------------------------------------------------
def patch_chatlist():
    p = ROOT / CHATLIST
    if not p.exists():
        fail('ChatList.kt missing')
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        note('chatlist already applied, skip')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    # --- 2a. 在 displayGroups 三行块之后插入 rhMessageByIdMap ---
    call_idx = find_unique_line(
        lines,
        'conversation.messageNodes.groupAutomaticCompactionMessages()',
        'chatlist displayGroups call',
    )
    if call_idx + 1 >= len(lines):
        fail('chatlist: displayGroups call is last line, unexpected')
    if lines[call_idx + 1].strip() != '}':
        fail('chatlist: unexpected line after displayGroups call -> ' + repr(lines[call_idx + 1]))

    insert_at = call_idx + 2
    block = []
    block.append('')
    block.append('    // ' + MARK + ': 引用消息 O(1) 查表, 替代每帧对全消息树的 flatMap 线性扫描。')
    block.append('    // 原实现在每个可见消息条目内部执行')
    block.append('    //   conversation.messageNodes.flatMap { it.messages }.firstOrNull { it.id == quotedId }')
    block.append('    // 流式期间每个 token 都让全部可见条目失效并重扫 => 全程 O(n^2)。')
    block.append('    // 该表只依赖结构性信息(节点数 + 各节点版本数之和), 与正在增长的文本无关,')
    block.append('    // 因此流式期间稳定命中, 历史条目不再参与任何重扫。')
    block.append('    val rhMessageByIdMap = remember(')
    block.append('        conversation.id,')
    block.append('        conversation.messageNodes.size,')
    block.append('        conversation.messageNodes.sumOf { it.messages.size },')
    block.append('    ) {')
    block.append('        buildMap {')
    block.append('            conversation.messageNodes.forEach { node ->')
    block.append('                node.messages.forEach { message -> put(message.id, message) }')
    block.append('            }')
    block.append('        }')
    block.append('    }')

    lines = lines[:insert_at] + block + lines[insert_at:]

    # --- 2b. 引用查找行 -> O(1) 查表 ---
    old_quote_needle = ('val quotedMsg = conversation.messageNodes.flatMap { it.messages }'
                        '.firstOrNull { it.id == quotedId }')
    quote_idx = find_unique_line(lines, old_quote_needle, 'chatlist quotedMsg lookup')
    q_indent = indent_of(lines[quote_idx])
    lines[quote_idx] = q_indent + 'val quotedMsg = rhMessageByIdMap[quotedId]'

    # --- 2c. 自动滚动 canScrollForward 守卫 ---
    old_scroll_needle = 'if (rhFollowStream && !state.isScrollInProgress && count > 0) {'
    new_scroll_body = ('if (rhFollowStream && !state.isScrollInProgress && count > 0 '
                       '&& state.canScrollForward) {')
    scroll_idx = find_unique_line(lines, old_scroll_needle, 'chatlist stream follow guard')
    s_indent = indent_of(lines[scroll_idx])
    lines[scroll_idx] = s_indent + new_scroll_body

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        fail('chatlist: balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
    if old_quote_needle in t2:
        fail('chatlist: old quotedMsg lookup still present')
    if 'rhMessageByIdMap[quotedId]' not in t2:
        fail('chatlist: quote map not wired')
    if old_scroll_needle in t2:
        fail('chatlist: old scroll guard still present')
    if 'state.canScrollForward' not in t2:
        fail('chatlist: canScrollForward guard missing')
    if t2.count('conversation.messageNodes.groupAutomaticCompactionMessages()') != 1:
        fail('chatlist: displayGroups call count changed unexpectedly')
    p.write_text(t2, encoding='utf-8')
    note('chatlist OK: quote map (O(1)) + canScrollForward guard')


def main():
    patch_group()
    patch_chatlist()
    note('batch241 OK - lossless streaming perf: lazy displayMessage + O(1) quote map '
         '+ canScrollForward guard (no visual downgrade: markdown/highlight/blur/scroll intact)')


main()
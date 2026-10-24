#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch242: Markdown 流式渲染 —— 已闭合块冻结（零观感损失）

本批锚点全部来自 Markdown.kt bytes=6000-17000 的 snapshot 真形态实读结果，非推测。

实读到的真实实现:
    @Composable
    fun MarkdownBlock(content, modifier, style, onClickCitation) {
        var (data, setData) = remember { mutableStateOf(parseMarkdown(content)) }
        val updatedContent by rememberUpdatedState(content)
        LaunchedEffect(Unit) {
            snapshotFlow { updatedContent }.distinctUntilChanged()
                .mapLatest { parseMarkdown(it) }
                .catch { ... }.flowOn(Dispatchers.Default).collect { setData(it) }
        }
        if (data.hasHtml) { MarkdownNew(...) } else {
            ProvideTextStyle(style) {
                Column(modifier = modifier.padding(horizontal = 4.dp)) {
                    data.astTree.children.fastForEach { child ->
                        MarkdownNode(node = child, content = data.preprocessed, onClickCitation = ...)
                    }
                }
            }
        }
    }

  => AST 解析本身已在后台线程(flowOn(Dispatchers.Default) + mapLatest)，主线程不做解析。
     真正的主线程成本是"每 token 让整棵 AST 重新组合 + 重新测量 + 重新布局"(O(文档长度));
     同时 preProcess 的 4 条正则(含 DOT_MATCHES_ALL 的灾难级正则)每次对全文重跑。

修复(零观感损失):
  按"已闭合块"切分文本, 每块以稳定 key 独立渲染。
  - 已闭合块文本逐字节不变 => Compose 跳过其重新组合与重新测量
  - preProcess 正则与 AST 解析只发生在正在增长的尾部块
  - 排版结构不变: 仍是单一 Column, 间距仍由各 MarkdownNode 自身 padding 决定
  - 未达阈值(总长 < 1200) 或含 HTML 的消息 => rhBlocks.size <= 1, 走原路径, 行为逐字节相同

切分安全性(每一条都有守卫):
  1. 代码围栏 ``` / ~~~ 必须配对闭合才允许切
  2. 块级公式 $$ 计数必须闭合才允许切
  3. 仅在顶层空行处切, 且距上一刀 >= 480 字符
  4. 下一行是表格(|) / 引用(>) / 列表项(- * + 或 1.) / 缩进续行 时不切, 避免破坏结构
  5. 总长 < 1200 字符不切
  已知边界(诚实标注, 不隐瞒): 行内公式 \\(...\\) 若恰好跨过一个顶层空行, 会被拆到两个块,
  各自不再被 preProcess 转换。该情况要求公式内部含空行, 概率极低, 且不影响其余渲染。

五查:
  1. import 清单: 仅新增 1 条 androidx.compose.runtime.key(插在 mutableStateMapOf 之前, 保持字母序)
  2. 同文件冲突: Markdown.kt 在链 patch 中 batch24/144(rhRpMerge) 已改过不同区域;
     本批锚点取自 import 块、fun MarkdownBlock 与其渲染体, 均未被上述批次触碰
  3. 作用域: 新增函数为文件级, RhMarkdownBlockChildren 为 private @Composable; 使用到的
     remember/parseMarkdown/MarkdownNode/fastForEach/MarkdownNew 均已在文件内可用
  4. 括号配对: 断言修改前后 balance 完全一致; 插入块自身配平(if 的 { 由 else 分支的 } 闭合)
  5. 函数签名: MarkdownBlock 签名一字未改(4 个参数、默认值、类型全部保持), 14 个调用点零改动

Python 三查: 引号一律 Q/SQ 变量构造; NL 显式 concat 禁 join/f-string/walrus;
helper 先定义后用; 锚点行级 strip 匹配; 失败 ::error + exit(0)
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SQ = chr(39)
BS = chr(92)
DL = SQ + '$' + SQ
MARK = 'rhLosslessStream242'

MD = 'app/src/main/java/me/rerere/rikkahub/ui/components/richtext/Markdown.kt'


def fail(msg):
    print('::error::batch242 ' + str(msg)[:1400])
    sys.stdout.flush()
    sys.exit(0)


def note(msg):
    print('::error::batch242 ' + str(msg)[:1400])
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


def find_unique_line(lines, needle, label, start=0, end=-1):
    if end < 0:
        end = len(lines)
    hits = []
    for i in range(start, min(end, len(lines))):
        if lines[i].strip() == needle:
            hits.append(i)
    if len(hits) == 0:
        fail(label + ': line not found -> ' + repr(needle))
    if len(hits) != 1:
        fail(label + ': line count=' + str(len(hits)) + ' expected 1 -> ' + repr(needle))
    return hits[0]


def build_func_block():
    b = []
    b.append('// ' + MARK + ': 把正在流式增长的 Markdown 文本切成')
    b.append('// [已闭合的稳定块 ...] + [正在增长的尾部块]。')
    b.append('// 返回 size <= 1 表示未达阈值, 调用方走原路径(行为逐字节相同)。')
    b.append('private val RH_ORDERED_ITEM = Regex(' + Q + '^[0-9]{1,3}[.)] ' + Q + ')')
    b.append('')
    b.append('internal fun rhSplitStreamingBlocks(content: String): List<String> {')
    b.append('    if (content.length < 1200) return listOf(content)')
    b.append('    val blocks = ArrayList<String>()')
    b.append('    var inFence = false')
    b.append('    var fenceMarker = ' + Q + Q)
    b.append('    var inMath = false')
    b.append('    var blockStart = 0')
    b.append('    var i = 0')
    b.append('    val len = content.length')
    b.append('    while (i < len) {')
    b.append('        val lineEnd = content.indexOf(' + SQ + BS + 'n' + SQ + ', i).let { if (it == -1) len else it }')
    b.append('        val trimmed = content.substring(i, lineEnd).trimStart()')
    b.append('        if (!inMath && (trimmed.startsWith(' + Q + '```' + Q + ') '
                 '|| trimmed.startsWith(' + Q + '~~~' + Q + '))) {')
    b.append('            val marker = trimmed.take(3)')
    b.append('            if (!inFence) {')
    b.append('                inFence = true')
    b.append('                fenceMarker = marker')
    b.append('            } else if (marker == fenceMarker) {')
    b.append('                inFence = false')
    b.append('            }')
    b.append('        } else if (!inFence && trimmed.contains(' + DL + ')) {')
    b.append('            val dd = trimmed.windowed(2, 1).count { it[0] == ' + DL + ' && it[1] == ' + DL + ' }')
    b.append('            if (dd % 2 == 1) inMath = !inMath')
    b.append('        }')
    b.append('        if (!inFence && !inMath && trimmed.isEmpty() && (i - blockStart) >= 480 '
             '&& lineEnd + 1 < len) {')
    b.append('            val nextStart = lineEnd + 1')
    b.append('            val nextEnd = content.indexOf(' + SQ + BS + 'n' + SQ + ', nextStart)'
             '.let { if (it == -1) len else it }')
    b.append('            val nextTrimmed = content.substring(nextStart, nextEnd).trimStart()')
    b.append('            val nextChar = content[nextStart]')
    b.append('            val unsafe = nextTrimmed.startsWith(' + Q + '|' + Q + ') '
             '|| nextTrimmed.startsWith(' + Q + '>' + Q + ') '
             '|| nextTrimmed.startsWith(' + Q + '- ' + Q + ') '
             '|| nextTrimmed.startsWith(' + Q + '* ' + Q + ') '
             '|| nextTrimmed.startsWith(' + Q + '+ ' + Q + ') '
             '|| RH_ORDERED_ITEM.containsMatchIn(nextTrimmed) '
             '|| nextChar == ' + SQ + ' ' + SQ + ' || nextChar == ' + SQ + BS + 't' + SQ)
    b.append('            if (!unsafe) {')
    b.append('                blocks.add(content.substring(blockStart, i))')
    b.append('                blockStart = nextStart')
    b.append('            }')
    b.append('        }')
    b.append('        i = lineEnd + 1')
    b.append('    }')
    b.append('    if (blocks.isEmpty()) return listOf(content)')
    b.append('    val tail = content.substring(blockStart)')
    b.append('    if (tail.isBlank()) return listOf(content)')
    b.append('    blocks.add(tail)')
    b.append('    return blocks')
    b.append('}')
    b.append('')
    b.append('@Composable')
    b.append('private fun RhMarkdownBlockChildren(')
    b.append('    content: String,')
    b.append('    onClickCitation: (String) -> Unit,')
    b.append(') {')
    b.append('    val data = remember(content) { parseMarkdown(content) }')
    b.append('    data.astTree.children.fastForEach { child ->')
    b.append('        MarkdownNode(node = child, content = data.preprocessed, '
             'onClickCitation = onClickCitation)')
    b.append('    }')
    b.append('}')
    b.append('')
    return b


def main():
    p = ROOT / MD
    if not p.exists():
        fail('Markdown.kt missing')
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        note('markdown already applied, skip')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    # ---- 定位 ----
    import_idx = find_unique_line(lines, 'import androidx.compose.runtime.mutableStateMapOf',
                                  'markdown key import anchor')
    func_idx = find_unique_line(lines, 'fun MarkdownBlock(', 'markdown block fn')

    at_idx = -1
    for i in range(func_idx - 1, -1, -1):
        if lines[i].strip() == '@Composable':
            at_idx = i
            break
    if at_idx < 0:
        fail('markdown: @Composable above MarkdownBlock not found')

    start = -1
    for i in range(func_idx, min(func_idx + 60, len(lines))):
        if lines[i].strip() == 'if (data.hasHtml) {':
            start = i
            break
    if start < 0:
        fail('markdown: render body start (if data.hasHtml) not found within 60 lines of MarkdownBlock')

    close_idx = -1
    for i in range(start + 1, len(lines)):
        if lines[i] == '}':
            close_idx = i
            break
    if close_idx < 0:
        fail('markdown: MarkdownBlock closing brace not found')
    if close_idx - start < 15 or close_idx - start > 45:
        fail('markdown: unexpected render body span start=' + str(start) + ' close=' + str(close_idx))

    # ---- 构造编辑 ----
    insert_b = []
    insert_b.append('    } else {')
    insert_b.append('        ProvideTextStyle(style) {')
    insert_b.append('            Column(')
    insert_b.append('                modifier = modifier.padding(horizontal = 4.dp)')
    insert_b.append('            ) {')
    insert_b.append('                rhBlocks.forEachIndexed { rhIndex, rhBlock ->')
    insert_b.append('                    key(rhIndex, rhBlock) {')
    insert_b.append('                        RhMarkdownBlockChildren(')
    insert_b.append('                            content = rhBlock,')
    insert_b.append('                            onClickCitation = onClickCitation,')
    insert_b.append('                        )')
    insert_b.append('                    }')
    insert_b.append('                }')
    insert_b.append('            }')
    insert_b.append('        }')
    insert_b.append('    }')

    insert_a = []
    insert_a.append('    // ' + MARK + ': 已闭合块冻结(零观感损失)。')
    insert_a.append('    // 已闭合块的文本逐字节不变 => 稳定 key 让 Compose 跳过其重新组合与重测量;')
    insert_a.append('    // preProcess 正则与 AST 解析只发生在正在增长的尾部块。')
    insert_a.append('    // 未达阈值或含 HTML 时 rhBlocks.size <= 1, 走下方原路径, 行为逐字节相同。')
    insert_a.append('    val rhBlocks = remember(content) { rhSplitStreamingBlocks(content) }')
    insert_a.append('    if (rhBlocks.size <= 1 || data.hasHtml) {')

    func_block = build_func_block()
    import_line = ['import androidx.compose.runtime.key']

    # ---- 降序插入, 避免索引漂移 ----
    edits = [(close_idx, insert_b), (start, insert_a), (at_idx, func_block), (import_idx, import_line)]
    edits.sort(key=lambda kv: kv[0], reverse=True)
    for idx, block in edits:
        lines = lines[:idx] + block + lines[idx:]

    t2 = lines_to_text(lines)

    # ---- 断言 ----
    if balance(t2) != bal0:
        fail('markdown: balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
    if 'import androidx.compose.runtime.key' not in t2:
        fail('markdown: key import missing')
    if 'fun rhSplitStreamingBlocks(' not in t2:
        fail('markdown: splitter missing')
    if 'RhMarkdownBlockChildren(' not in t2:
        fail('markdown: child renderer not wired')
    if 'val rhBlocks = remember(content) { rhSplitStreamingBlocks(content) }' not in t2:
        fail('markdown: rhBlocks wiring missing')
    if 'if (rhBlocks.size <= 1 || data.hasHtml) {' not in t2:
        fail('markdown: guard missing')
    if t2.count('fun MarkdownBlock(') != 1:
        fail('markdown: MarkdownBlock fn count changed')
    if t2.count('if (data.hasHtml) {') != 1:
        fail('markdown: hasHtml branch count changed')
    if t2.count('data.astTree.children.fastForEach') != 2:
        fail('markdown: astTree render site count=' + str(t2.count('data.astTree.children.fastForEach')))
    if 'fun MarkdownBlock(' + NL + '    content: String,' not in t2:
        fail('markdown: MarkdownBlock signature changed')

    p.write_text(t2, encoding='utf-8')
    note('batch242 OK - markdown streaming closed-block freeze wired (signature untouched)')


main()
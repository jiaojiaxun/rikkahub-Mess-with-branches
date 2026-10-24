#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch285 v2: 流式渲染平滑三件套 —— 打字机匀速 + 块冻结 + 新块淡入

【v2 修正: 500ms 延迟门曾被 LaunchedEffect 重启杀死】
v1 把 delay(500) 放在 drive() 里, 而驱动方是 LaunchedEffect(active, len) ——
每 80ms 一次新 chunk 就取消旧协程, delay 被打断, 而 started 已在 delay 前置位,
实际延迟只剩 ~80ms。v2 拆成:
  · awaitStartDelay(active): 独立 LaunchedEffect(active) 内跑, 只受 active 键影响,
    delay 完再置 started
  · drive() 里 if (!started) return —— 延迟未结束不推进
另修: clip(latest, active) 对"从未流式过的历史消息"(started=false, revealed=0)
直接返回全文, 消除首帧空白, 且不重放动画。

【用户诉求】流式"一顿一顿的变速" -> 0.5s 延迟缓冲 + 匀速输出 + 文字淡入。
【根因】ChatService 80ms sample(batch258) 后每帧增量不可预测(一次蹦 0~N 字符),
Markdown 全文重组合且无打字整流层。

【本批三件】
1. SmoothStream.kt(新文件): RhTypewriterState(Animatable 匀速推进+积压追赶+冲线),
   LocalRhStreamFade(CompositionLocal 淡入门控), RhFadeIn(alpha 0->1 300ms,
   rememberSaveable 防滚动重放), rhSplitStreamBlocks285(已闭合块切分)。
2. Markdown.kt: MarkdownBlock AST 渲染分支改 短路径直渲染/冻结块循环
   (key(rhIndex)+RhFadeIn+RhMarkdownChunkChildren); 文件级插 RhMarkdownChunkChildren;
   +import androidx.compose.runtime.key。
   —— batch242 的冻结在当前链上零落地(snapshot 实读 MarkdownBlock 无 marker,
   其 fail 被 warn-only 吞), 本批换名重实现, 不依赖它。
3. ChatMessage.kt: ContentBlock Text 分支插打字机状态+两个 LaunchedEffect,
   两处助手 MarkdownBlock content=part.text -> content=rhShownText,
   助手分支包 CompositionLocalProvider(LocalRhStreamFade provides rhStreamActive)。

【行为边界】用户消息/历史消息(loading=false 且从未流式)逐字节不变;
hasHtml 消息打字机照常但冻结/淡入不覆盖; 表格单元格默认 LocalRhStreamFade=false;
重生成 clip 的 len>=latest.length 检查保证越界安全。

五查:
 1. import: Markdown.kt +1 key; ChatMessage.kt +3; SmoothStream.kt 新文件 15 条。
 2. 同文件冲突: Markdown.kt 在链 batch24/144(Paragraph rpStyleRules 区域)不重叠,
    batch242 未落地已核; ChatMessage.kt 在链 53/76/88/249 均不在 textContent 锚点带。
 3. 作用域: 打字机块在 ContentBlock key(block.index) 内; rhShownText 在 lambda 外定义
    lambda 内捕获; 新符号均 richtext 包文件级。
 4. 括号配对: 三文件 balance 前后一致断言; 新块自身配平已逐块数过。
 5. 函数签名: 零改动。
Python 三查: 引号 Q/SQ 变量构造; Kotlin 多行块用 raw 三引号字面量;
NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 每部分独立 try 捕获继续;
失败 ::error + ci_diag_batch285.txt 落盘。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SQ = chr(39)
MARK = 'rhSmoothStream285'

RT = 'app/src/main/java/me/rerere/rikkahub/ui/components/richtext'
MD = RT + '/Markdown.kt'
SS = RT + '/SmoothStream.kt'
CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
DIAG = 'ci_diag_batch285.txt'

report = []


def note(msg):
    report.append(str(msg)[:900])
    print('::error::batch285 ' + str(msg)[:900])
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


def find_unique(lines, needle, label, start=0, end=-1):
    if end < 0:
        end = len(lines)
    hits = []
    for i in range(start, min(end, len(lines))):
        if lines[i].strip() == needle:
            hits.append(i)
    if len(hits) != 1:
        note('ABORT ' + label + ': count=' + str(len(hits)) + ' need 1 -> ' + repr(needle))
        raise SystemExit(1)
    return hits[0]


SMOOTH_STREAM_KT = r'''package me.rerere.rikkahub.ui.components.richtext

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.graphicsLayer
import kotlinx.coroutines.delay

// rhSmoothStream285: 流式渲染平滑层(打字机+淡入)。
// ChatMessage 层用 RhTypewriterState 把"每 80ms 一帧的变速增量"整流成
// 恒定速率的字符流; Markdown 渲染层用 LocalRhStreamFade 给新增块做淡入。

// 流式淡入开关: 只有"正在生成的助手消息"所在子树 provide true,
// 历史消息/用户消息保持 false(直通零开销)。
internal val LocalRhStreamFade = compositionLocalOf { false }

// 打字机参数:
// START_DELAY  首批内容到达后先攒 0.5s, 吃到足够 buffer 再开始吐字
// BASE_RATE    基础吐字速率(字符/秒); 低于多数模型到达率, 平滑层始终工作
// CATCHUP      积压追赶窗口(秒); 积压大时 rate 提升到 backlog/CATCHUP,
//              显示最多落后约 1.5s, 速率随积压连续变化(无跳变, 观感匀速)
// FINISH_MS    生成结束后的冲线时长(剩余字符快速补完)
// INSTANT_LEN  组合销毁重建(滚动出屏再回来)时, 已有内容超过该长度直接全量,
//              避免滚动回来重放打字机
private const val RH_TW_START_DELAY_MS = 500L
private const val RH_TW_BASE_RATE = 24f
private const val RH_TW_CATCHUP_WINDOW_S = 1.5f
private const val RH_TW_FINISH_MS = 220
private const val RH_TW_INSTANT_LEN = 64

internal class RhTypewriterState {
    private val revealed = Animatable(0f)
    private var started = false
    private var driven = false

    // 读取当前应显示的文本(组合期调用, 无副作用)。
    // 从未流式过的历史消息(started=false, revealed=0)直通全文, 零帧空白。
    fun clip(latest: String, active: Boolean): String {
        if (!active && !started && revealed.value == 0f) return latest
        val len = revealed.value.toInt()
        return if (len >= latest.length) latest else latest.substring(0, len)
    }

    // 初始缓冲门: 必须在只依赖 active 的独立 LaunchedEffect 里调用,
    // 否则会随每个 chunk 重启而被取消(v1 的 bug, v2 修正)。
    suspend fun awaitStartDelay(active: Boolean) {
        if (!active || started) return
        delay(RH_TW_START_DELAY_MS)
        started = true
    }

    // 驱动动画: target 变化时由 LaunchedEffect 重启, 从当前 revealed 匀速推进。
    suspend fun drive(targetLen: Int, active: Boolean) {
        if (!active) {
            if (revealed.value < targetLen) {
                if (!started && revealed.value == 0f) {
                    // 历史消息首次组合: 直接全量, 不播放任何动画
                    revealed.snapTo(targetLen.toFloat())
                } else {
                    revealed.animateTo(targetLen.toFloat(), tween(RH_TW_FINISH_MS))
                }
            }
            return
        }
        if (targetLen <= 0) return
        if (!driven) {
            driven = true
            if (targetLen >= RH_TW_INSTANT_LEN) {
                // 滚动销毁重建: 已有内容直接全量, 不重放
                revealed.snapTo(targetLen.toFloat())
                return
            }
        }
        if (!started) return
        val backlog = targetLen - revealed.value
        if (backlog <= 0f) return
        val rate = maxOf(RH_TW_BASE_RATE, backlog / RH_TW_CATCHUP_WINDOW_S)
        val durMs = (backlog / rate * 1000f).toInt().coerceAtLeast(60)
        revealed.animateTo(targetLen.toFloat(), tween(durationMillis = durMs, easing = LinearEasing))
    }
}

// 新块淡入: alpha 0->1 (300ms)。played 用 rememberSaveable 记录"已播放",
// 滚动出屏销毁组合后回来不重放(靠 LazyColumn 的 item 状态保存)。
// enabled=false 时直通不引入 Box, 历史消息布局逐字节不变。
@Composable
internal fun RhFadeIn(
    enabled: Boolean,
    content: @Composable () -> Unit,
) {
    if (!enabled) {
        content()
        return
    }
    var played by rememberSaveable { mutableStateOf(false) }
    if (played) {
        content()
        return
    }
    val alpha = remember { Animatable(0f) }
    LaunchedEffect(Unit) {
        alpha.animateTo(1f, tween(durationMillis = 300))
        played = true
    }
    Box(modifier = Modifier.graphicsLayer { this.alpha = alpha.value }) {
        content()
    }
}

// 流式文本按"已闭合块"切分: 代码围栏/块级公式配对才允许切;
// 仅在顶层空行处切且距上一刀>=480字符; 下一行是表格/引用/列表项/缩进续行
// 时不切; 总长<1200不切。返回 size<=1 表示未达阈值, 调用方走原路径。
private val RH_ORDERED_ITEM_285 = Regex("^[0-9]{1,3}[.)] ")

internal fun rhSplitStreamBlocks285(content: String): List<String> {
    if (content.length < 1200) return listOf(content)
    val blocks = ArrayList<String>()
    var inFence = false
    var fenceMarker = ""
    var inMath = false
    var blockStart = 0
    var i = 0
    val len = content.length
    while (i < len) {
        val lineEnd = content.indexOf('\n', i).let { if (it == -1) len else it }
        val trimmed = content.substring(i, lineEnd).trimStart()
        if (!inMath && (trimmed.startsWith("```") || trimmed.startsWith("~~~"))) {
            val marker = trimmed.take(3)
            if (!inFence) {
                inFence = true
                fenceMarker = marker
            } else if (marker == fenceMarker) {
                inFence = false
            }
        } else if (!inFence && trimmed.contains('$')) {
            val dd = trimmed.windowed(2, 1).count { it[0] == '$' && it[1] == '$' }
            if (dd % 2 == 1) inMath = !inMath
        }
        if (!inFence && !inMath && trimmed.isEmpty() && (i - blockStart) >= 480 && lineEnd + 1 < len) {
            val nextStart = lineEnd + 1
            val nextEnd = content.indexOf('\n', nextStart).let { if (it == -1) len else it }
            val nextTrimmed = content.substring(nextStart, nextEnd).trimStart()
            val nextChar = content[nextStart]
            val unsafe = nextTrimmed.startsWith("|") || nextTrimmed.startsWith(">")
                || nextTrimmed.startsWith("- ") || nextTrimmed.startsWith("* ")
                || nextTrimmed.startsWith("+ ") || RH_ORDERED_ITEM_285.containsMatchIn(nextTrimmed)
                || nextChar == ' ' || nextChar == '\t'
            if (!unsafe) {
                blocks.add(content.substring(blockStart, i))
                blockStart = nextStart
            }
        }
        i = lineEnd + 1
    }
    if (blocks.isEmpty()) return listOf(content)
    val tail = content.substring(blockStart)
    if (tail.isBlank()) return listOf(content)
    blocks.add(tail)
    return blocks
}
'''


def part_smoothstream():
    p = ROOT / SS
    if p.exists():
        note('SmoothStream.kt already exists, skip')
        return
    p.write_text(SMOOTH_STREAM_KT, encoding='utf-8')
    for need in ['class RhTypewriterState', 'fun RhFadeIn(',
                 'fun rhSplitStreamBlocks285(', 'LocalRhStreamFade',
                 'rememberSaveable', 'RH_TW_START_DELAY_MS = 500L',
                 'suspend fun awaitStartDelay(active: Boolean)']:
        if need not in SMOOTH_STREAM_KT:
            note('ABORT selfcheck missing ' + need)
            raise SystemExit(1)
    note('smoothstream OK: new file written chars=' + str(len(SMOOTH_STREAM_KT)))


RENDER_NEW_BLOCK = r'''                val rhBlocks = remember(content) { rhSplitStreamBlocks285(content) } // rhSmoothStream285
                if (rhBlocks.size <= 1 || data.hasHtml) {
                    data.astTree.children.fastForEach { child ->
                        MarkdownNode(
                            node = child, content = data.preprocessed, onClickCitation = onClickCitation
                        )
                    }
                } else {
                    rhBlocks.forEachIndexed { rhIndex, rhBlock ->
                        key(rhIndex) {
                            RhFadeIn(enabled = LocalRhStreamFade.current) {
                                RhMarkdownChunkChildren(
                                    content = rhBlock,
                                    onClickCitation = onClickCitation,
                                )
                            }
                        }
                    }
                }'''

CHUNK_CHILDREN = r'''@Composable
private fun RhMarkdownChunkChildren(
    content: String,
    onClickCitation: (String) -> Unit,
) {
    // rhSmoothStream285: 冻结块子渲染 —— remember(content) 让已闭合块
    // 的 AST 解析只发生一次, 尾部增长块每次重解析。
    val data = remember(content) { parseMarkdown(content) }
    data.astTree.children.fastForEach { child ->
        MarkdownNode(node = child, content = data.preprocessed, onClickCitation = onClickCitation)
    }
}

'''


def part_markdown():
    p = ROOT / MD
    if not p.exists():
        note('ABORT Markdown.kt missing')
        raise SystemExit(1)
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        note('markdown already applied, skip')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    ff_idx = find_unique(lines, 'data.astTree.children.fastForEach { child ->',
                         'markdown render loop anchor')
    expect = ['MarkdownNode(',
              'node = child, content = data.preprocessed, onClickCitation = onClickCitation',
              ')',
              '}']
    for off, needle in enumerate(expect, start=1):
        if lines[ff_idx + off].strip() != needle:
            note('ABORT markdown render loop shape mismatch at +' + str(off)
                 + ' -> ' + repr(lines[ff_idx + off][:80]))
            raise SystemExit(1)

    new_lines = RENDER_NEW_BLOCK.split(NL)
    lines = lines[:ff_idx] + new_lines + lines[ff_idx + 5:]

    imp_idx = find_unique(lines, 'import androidx.compose.runtime.mutableStateMapOf',
                          'markdown import anchor')
    lines = lines[:imp_idx] + ['import androidx.compose.runtime.key'] + lines[imp_idx:]

    fn_idx = find_unique(lines, 'fun MarkdownBlock(', 'markdown block fn')
    at_idx = -1
    for i in range(fn_idx - 1, max(fn_idx - 12, 0) - 1, -1):
        if lines[i].strip() == '@Composable':
            at_idx = i
            break
    if at_idx < 0:
        note('ABORT markdown @Composable above MarkdownBlock not found')
        raise SystemExit(1)
    chunk_lines = CHUNK_CHILDREN.split(NL)
    lines = lines[:at_idx] + chunk_lines + lines[at_idx:]

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT markdown balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        raise SystemExit(1)
    checks = [
        'val rhBlocks = remember(content) { rhSplitStreamBlocks285(content) }',
        'if (rhBlocks.size <= 1 || data.hasHtml) {',
        'RhMarkdownChunkChildren(',
        'fun RhMarkdownChunkChildren(',
        'import androidx.compose.runtime.key',
        'RhFadeIn(enabled = LocalRhStreamFade.current)',
        'key(rhIndex)',
    ]
    for need in checks:
        if need not in t2:
            note('ABORT markdown selfcheck missing ' + need)
            raise SystemExit(1)
    n_ff = t2.count('data.astTree.children.fastForEach')
    if n_ff != 2:
        note('ABORT markdown fastForEach count=' + str(n_ff) + ' need 2')
        raise SystemExit(1)
    if t2.count('fun MarkdownBlock(') != 1:
        note('ABORT markdown MarkdownBlock fn count changed')
        raise SystemExit(1)
    if t2.count('if (data.hasHtml) {') != 1:
        note('ABORT markdown hasHtml branch count changed')
        raise SystemExit(1)
    p.write_text(t2, encoding='utf-8')
    note('markdown OK: freeze loop + chunk children + key import wired')


TYPEWRITER_BLOCK = r'''// rhSmoothStream285: 打字机匀速渲染。0.5s 初始缓冲后恒定速率吐字,
                        // 积压平滑提速(显示最多落后约 1.5s), 生成结束 220ms 冲线;
                        // 滚动销毁重建(len>=64)直接全量不重放。
                        val rhTw = remember { RhTypewriterState() }
                        val rhStreamActive = role != MessageRole.USER && loading
                        LaunchedEffect(rhStreamActive) {
                            rhTw.awaitStartDelay(rhStreamActive)
                        }
                        LaunchedEffect(rhStreamActive, part.text.length) {
                            rhTw.drive(part.text.length, rhStreamActive)
                        }
                        val rhShownText = rhTw.clip(part.text, rhStreamActive)
'''

PROVIDER_OPEN = '                                CompositionLocalProvider(LocalRhStreamFade provides rhStreamActive) { // rhSmoothStream285'
PROVIDER_CLOSE = '                                } // rhSmoothStream285'


def part_chatmessage():
    p = ROOT / CM
    if not p.exists():
        note('ABORT ChatMessage.kt missing')
        raise SystemExit(1)
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        note('chatmessage already applied, skip')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    tc_idx = find_unique(lines, 'val textContent = @Composable {', 'chatmessage textContent anchor')
    tw_lines = TYPEWRITER_BLOCK.rstrip(NL).split(NL)
    lines = lines[:tc_idx] + tw_lines + lines[tc_idx:]
    tc_idx += len(tw_lines)

    content_hits = []
    for i in range(tc_idx, min(tc_idx + 60, len(lines))):
        if lines[i].strip() == 'content = part.text.replaceRegexes(':
            content_hits.append(i)
    if len(content_hits) != 3:
        note('ABORT chatmessage content hits=' + str(len(content_hits)) + ' need 3')
        raise SystemExit(1)
    replaced = 0
    for hi in content_hits:
        scope_zone = NL.join(lines[hi:min(hi + 4, len(lines))])
        if 'AssistantAffectScope.ASSISTANT' in scope_zone:
            raw_line = lines[hi]
            indent = raw_line[:len(raw_line) - len(raw_line.lstrip())]
            lines[hi] = indent + 'content = rhShownText.replaceRegexes( // rhSmoothStream285'
            replaced += 1
    if replaced != 2:
        note('ABORT chatmessage assistant content replace=' + str(replaced) + ' need 2')
        raise SystemExit(1)

    open_hits = []
    for i in range(tc_idx, min(tc_idx + 60, len(lines))):
        if lines[i] == '                            } else {':
            open_hits.append(i)
    if len(open_hits) != 1:
        note('ABORT chatmessage role-else hits=' + str(len(open_hits)) + ' need 1')
        raise SystemExit(1)
    oe_idx = open_hits[0]
    lines = lines[:oe_idx + 1] + [PROVIDER_OPEN] + lines[oe_idx + 1:]

    close_idx = -1
    for i in range(oe_idx + 2, min(oe_idx + 40, len(lines))):
        if lines[i] == '                            }':
            close_idx = i
            break
    if close_idx < 0:
        note('ABORT chatmessage role-else close not found')
        raise SystemExit(1)
    lines = lines[:close_idx] + [PROVIDER_CLOSE] + lines[close_idx:]

    imp1 = find_unique(lines, 'import androidx.compose.runtime.Composable',
                       'chatmessage composable import')
    lines = lines[:imp1 + 1] + ['import androidx.compose.runtime.CompositionLocalProvider // rhSmoothStream285'] + lines[imp1 + 1:]
    imp2 = find_unique(lines, 'import me.rerere.rikkahub.ui.components.richtext.MarkdownBlock',
                       'chatmessage markdownblock import')
    lines = lines[:imp2 + 1] + [
        'import me.rerere.rikkahub.ui.components.richtext.LocalRhStreamFade // rhSmoothStream285',
        'import me.rerere.rikkahub.ui.components.richtext.RhTypewriterState // rhSmoothStream285',
    ] + lines[imp2 + 1:]

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT chatmessage balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        raise SystemExit(1)
    checks = [
        'RhTypewriterState()',
        'rhTw.awaitStartDelay(rhStreamActive)',
        'rhTw.drive(part.text.length, rhStreamActive)',
        'rhTw.clip(part.text, rhStreamActive)',
        'CompositionLocalProvider(LocalRhStreamFade provides rhStreamActive)',
        'content = rhShownText.replaceRegexes(',
        'import me.rerere.rikkahub.ui.components.richtext.RhTypewriterState',
    ]
    for need in checks:
        if need not in t2:
            note('ABORT chatmessage selfcheck missing ' + need)
            raise SystemExit(1)
    if t2.count('content = part.text.replaceRegexes(') != 1:
        note('ABORT chatmessage user content left != 1')
        raise SystemExit(1)
    p.write_text(t2, encoding='utf-8')
    note('chatmessage OK: typewriter + provider + 2 content swaps wired')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as e:
        note('diag write FAILED ' + str(e)[:200])


def main():
    for name, fn in [('smoothstream', part_smoothstream),
                     ('markdown', part_markdown),
                     ('chatmessage', part_chatmessage)]:
        try:
            fn()
            note('part ' + name + ' DONE')
        except SystemExit:
            note('part ' + name + ' ABORTED')
        except Exception as e:
            note('part ' + name + ' EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    write_diag()
    note('batch285 END report lines=' + str(len(report)))


main()

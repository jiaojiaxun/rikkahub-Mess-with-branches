#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch290 v2: 修复重进流式对话时消息整篇重放(打字机+淡入)

【v1 死因(run 40158258113, diag 实证)】
    smoothstream OK / part DONE
    chatmessage dropped rememberSaveable import
    ABORT chatmessage stale symbol rhIsRebuild   <= 断言误判
v1 用裸词 `rhIsRebuild` 检查代码残留, 但 v3 打字机块上方的说明注释里就有
"rhIsRebuild=true -> 直接全量..." 字样 => 断言命中注释 => abort => ChatMessage
零写盘; 而 SmoothStream.kt 的 clip 已改成 3 参 => 编译错
"ChatMessage.kt:482 No value passed for parameter 'resumed'"。
v2 两处修正:
  1. 注释块随代码一起替换(注释描述新语义, 不再残留旧词)
  2. 残留检查改精确语法: 'val rhEverDriven' / 'val rhIsRebuild' /
     '(part.text.length, rhStreamActive, rhIsRebuild)' —— 裸词检查永远会撞注释。

【用户报告】每次重进一个正在输出的对话, 消息都会重新显示一遍。
【根因】batch288 v3 用 rememberSaveable 的 everDriven 判定"滚动重建", 但
LazyColumn item 级 saveable 只在可见+预取范围内保留: 导航离开对话页时若
消息不在可见区/页面整体 dispose, everDriven 恢复失败 => 打字机从 0 重放全文;
RhFadeIn 的 played 同样丢 => 所有块重新淡入。

【修复: 消息年龄判定(数据层事实, 跨导航恒定)】
UIMessage.createdAt 跨导航/重建恒定:
  · 发送瞬间 age≈0   => 本次组合就是"从头开始流式" => 打字机+淡入照常
  · 打开/重进时 age>1s => 本次组合前已有内容 => drive(skipReplay) 直接全量,
    clip 同步直通(消首帧空白), 淡入关闭(LocalRhStreamFade 为 false)
remember(message.id) 让同一消息在本次组合会话内只判定一次: 发送后盯着看,
age 从 0 涨到 30s, rhStreamResumed 保持 false(remember 冻结) => 打字机不中断;
滚动出屏再回来/导航重进 => 新组合重新判定 => 直通。

【删除】rememberSaveable 的 rhEverDriven / rhIsRebuild / drive 的 isRebuild
参数(改名 skipReplay) —— 整个不可靠机制移除。

【五查】
 1. import: ChatMessage.kt +5(kotlin.time.Clock / kotlinx.datetime.TimeZone /
    kotlinx.datetime.toInstant / LocalRhStreamResumed / RH_TW_RESUME_AGE_MS),
    -1(rememberSaveable, v3 加入且仅被删代码使用); SmoothStream.kt +0 import。
 2. 同文件冲突: ChatMessage.kt 在链 53/76/88/249/286/289(ThinkingBlock 区+import)
    与 288(textContent 区)。本批锚点: onUserMessageClick 定义/调用两行(形态不同)、
    v3 打字机块注释+代码(288 自写)、v3 provider 行、colorScheme 行、import 区
    —— 与 286/289 落点不相交; sort -V 下 290 最后执行。
    SmoothStream.kt 由 288 创建, 本批 find/replace 基于 v3 已实读形态。
 3. 作用域: rhStreamResumed 在 ChatMessage 函数体(message/remember 可用);
    streamResumed 为 MessagePartsBlock 默认参数; rhResumed 在 ContentBlock 内,
    drive/clip/provider fade 均在作用域。
 4. 括号配对: 两文件 balance 前后一致断言; 旧注释+代码 9 行(3 对花括号)换成
    新注释+代码 7 行(1 对花括号), 净差 0; 新增计算块自身配平;
    clip 的 (!active || resumed) 与 provider 的 (rhStreamActive && !rhResumed))
    各增 1 对括号。
 5. 函数签名: MessagePartsBlock 加默认参数(内部 private, 唯一调用点同步);
    drive isRebuild->skipReplay 改名; clip 加 resumed 形参 —— 同批调用点同步。
【Python 三查】Kotlin 块 raw 三引号; NL 显式 concat; helper 先定义后用;
每部分独立 try 捕获继续; 失败 ::error + 独立 diag 落盘。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhStreamResumeFix290'

CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
SS = 'app/src/main/java/me/rerere/rikkahub/ui/components/richtext/SmoothStream.kt'
DIAG = 'ci_diag_batch290_stream_resume_fix.txt'

report = []


def note(msg):
    report.append(str(msg)[:900])
    print('::error::batch290 ' + str(msg)[:900])
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
        note('ABORT ' + label + ': count=' + str(len(hits)) + ' need 1 -> ' + repr(needle[:70]))
        raise SystemExit(1)
    return hits[0]


# =========================================================================
# Part 1: SmoothStream.kt —— skipReplay 语义 + clip resumed + 消息级信号
# =========================================================================
def part_smoothstream():
    p = ROOT / SS
    if not p.exists():
        note('ABORT SmoothStream.kt missing (batch288 not applied?)')
        raise SystemExit(1)
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        note('smoothstream already applied, skip')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    sig_idx = find_unique(lines, 'suspend fun drive(targetLen: Int, active: Boolean, isRebuild: Boolean) {',
                          'drive signature')
    lines[sig_idx] = '    suspend fun drive(targetLen: Int, active: Boolean, skipReplay: Boolean) { // ' + MARK
    if_idx = find_unique(lines, 'if (isRebuild) {', 'drive rebuild branch')
    lines[if_idx] = '        if (skipReplay) {'
    cmt1 = find_unique(lines,
                       '// isRebuild=true 表示"滚动出屏后重建"(everDriven 由 rememberSaveable 恢复),',
                       'drive comment 1')
    lines[cmt1] = ('    // skipReplay=true: 本次组合前已有内容(打开/重进对话, 消息年龄>1s, '
                   '或滚动重建),')
    cmt2 = find_unique(lines,
                       '// 直接 snapTo 全量, 不重放打字机; 首块大 chunk 不属于重建, 照常走打字机。',
                       'drive comment 2')
    lines[cmt2] = '    // 直接 snapTo 全量, 不重放; 发送瞬间 age≈0 不属于重放, 照常走打字机。'

    clip_idx = find_unique(lines, 'fun clip(latest: String, active: Boolean): String {', 'clip signature')
    lines[clip_idx] = '    fun clip(latest: String, active: Boolean, resumed: Boolean): String { // ' + MARK
    clip_if = find_unique(lines, 'if (!active && !started && revealed.value == 0f) return latest',
                          'clip passthrough')
    lines[clip_if] = ('        if ((!active || resumed) && !started && revealed.value == 0f) '
                      'return latest // ' + MARK + ': 历史/重进消息直通, 消除首帧空白')

    fade_idx = find_unique(lines, 'internal val LocalRhStreamFade = compositionLocalOf { false }',
                           'fade local')
    block = [
        '',
        '// ' + MARK + ': 消息级"重进/重建"信号。',
        '// ChatMessage 按 message.createdAt 年龄判定(>1s)后 provide;',
        '// true => 该消息在本次组合前已有内容: 打字机不重放、淡入不重播。',
        'internal val LocalRhStreamResumed = compositionLocalOf { false }',
        '',
        '// 消息年龄阈值(ms): 超过即视为"打开/重进对话时已有内容"。',
        '// 正常流式首块在发送后 1s 内到达, 故发送瞬间判定为 false。',
        'internal const val RH_TW_RESUME_AGE_MS = 1000L',
    ]
    lines = lines[:fade_idx + 1] + block + lines[fade_idx + 1:]

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT smoothstream balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        raise SystemExit(1)
    checks = [
        'suspend fun drive(targetLen: Int, active: Boolean, skipReplay: Boolean) {',
        'if (skipReplay) {',
        'fun clip(latest: String, active: Boolean, resumed: Boolean): String {',
        'if ((!active || resumed) && !started && revealed.value == 0f) return latest',
        'internal val LocalRhStreamResumed = compositionLocalOf { false }',
        'internal const val RH_TW_RESUME_AGE_MS = 1000L',
    ]
    for need in checks:
        if need not in t2:
            note('ABORT smoothstream selfcheck missing ' + need[:70])
            raise SystemExit(1)
    # 精确语法残留检查(裸词会撞注释, v1 的教训)
    for bad in ['isRebuild: Boolean', 'if (isRebuild) {', 'isRebuild)']:
        if bad in t2:
            note('ABORT smoothstream stale syntax ' + bad)
            raise SystemExit(1)
    p.write_text(t2, encoding='utf-8')
    note('smoothstream OK: skipReplay + clip resumed + LocalRhStreamResumed wired')


# =========================================================================
# Part 2: ChatMessage.kt —— 年龄判定 + 参数接线 + import 增删
# =========================================================================
# 旧注释+代码共 9 行(v3 形态, strip 比较); 注释必须一起换, 否则旧词残留
OLD_TW_BLOCK = [
    '// everDriven 经 rememberSaveable 跨组合保存: 滚动出屏重建时',
    '// rhIsRebuild=true -> 直接全量, 不重放; 首块大 chunk 照常打字。',
    'val rhEverDriven = rememberSaveable { mutableStateOf(false) }',
    'val rhIsRebuild = remember { rhEverDriven.value }',
    'LaunchedEffect(rhStreamActive, part.text.length) {',
    'if (rhStreamActive && !rhIsRebuild) rhEverDriven.value = true',
    'rhTw.drive(part.text.length, rhStreamActive, rhIsRebuild)',
    '}',
    'val rhShownText = rhTw.clip(part.text, rhStreamActive)',
]

NEW_TW_BLOCK = [
    '// rhStreamResumeFix290: 重进/重建判定改用消息年龄(rhStreamResumed):',
    '// 已有内容直接全量不重放; 发送瞬间照常打字, 淡入由 provider 控制。',
    'val rhResumed = streamResumed',
    'LaunchedEffect(rhStreamActive, part.text.length) {',
    'rhTw.drive(part.text.length, rhStreamActive, rhResumed)',
    '}',
    'val rhShownText = rhTw.clip(part.text, rhStreamActive, rhResumed)',
]

NEW_IMPORTS = [
    'import kotlin.time.Clock // ' + MARK,
    'import kotlinx.datetime.TimeZone // ' + MARK,
    'import kotlinx.datetime.toInstant // ' + MARK,
    'import me.rerere.rikkahub.ui.components.richtext.LocalRhStreamResumed // ' + MARK,
    'import me.rerere.rikkahub.ui.components.richtext.RH_TW_RESUME_AGE_MS // ' + MARK,
]


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

    # E1: 删 v3 的 rememberSaveable import(仅被删代码使用)
    drop_idx = -1
    for i, ln in enumerate(lines):
        if ln.strip() == 'import androidx.compose.runtime.saveable.rememberSaveable // rhSmoothStream285':
            drop_idx = i
            break
    if drop_idx >= 0:
        del lines[drop_idx]
        note('chatmessage dropped rememberSaveable import')
    else:
        note('chatmessage rememberSaveable import absent (already clean)')

    # E2: import 增补(锚点 = v3 的 CompositionLocalProvider 行)
    imp_idx = find_unique(lines,
                          'import androidx.compose.runtime.CompositionLocalProvider // rhSmoothStream285',
                          'chatmessage import anchor')
    lines = lines[:imp_idx + 1] + NEW_IMPORTS + lines[imp_idx + 1:]

    # E3: rhStreamResumed 年龄判定(插在 colorScheme 行后, 函数体作用域)
    cs_idx = find_unique(lines, 'val colorScheme = MaterialTheme.colorScheme', 'colorScheme anchor')
    resume_block = [
        '    // ' + MARK + ': 消息年龄>1s = 打开/重进对话时已有内容 => 不重放打字机/淡入。',
        '    // remember(message.id): 同一消息本次组合会话内只判一次——发送瞬间 age≈0',
        '    // => 全程打字机; 滚动/导航重进 => 新组合重判 => 直通。',
        '    val rhStreamResumed = remember(message.id) {',
        '        val createdAt = message.createdAt.toInstant(TimeZone.currentSystemDefault())',
        '        (Clock.System.now() - createdAt).inWholeMilliseconds > RH_TW_RESUME_AGE_MS',
        '    }',
    ]
    lines = lines[:cs_idx + 1] + resume_block + lines[cs_idx + 1:]

    # E4: MessagePartsBlock 定义加默认参数
    def_idx = find_unique(lines, 'onUserMessageClick: (() -> Unit)? = null,', 'MessagePartsBlock def param')
    lines = lines[:def_idx + 1] + ['    streamResumed: Boolean = false, // ' + MARK] + lines[def_idx + 1:]

    # E5: MessagePartsBlock 调用传参
    call_idx = find_unique(lines,
                           'onUserMessageClick = if (message.role == MessageRole.USER) onEdit else null,',
                           'MessagePartsBlock call arg')
    lines = lines[:call_idx + 1] + ['                    streamResumed = rhStreamResumed, // ' + MARK] + lines[call_idx + 1:]

    # E6: 注释+代码整块替换(9 行 -> 7 行), 逐行 strip 校验
    start_idx = -1
    for i, ln in enumerate(lines):
        if ln.strip() == OLD_TW_BLOCK[0]:
            start_idx = i
            break
    if start_idx < 0:
        note('ABORT chatmessage typewriter block start not found')
        raise SystemExit(1)
    for k, needle in enumerate(OLD_TW_BLOCK):
        if start_idx + k >= len(lines) or lines[start_idx + k].strip() != needle:
            note('ABORT chatmessage typewriter block shape mismatch at +' + str(k)
                 + ' -> ' + repr(lines[start_idx + k][:70] if start_idx + k < len(lines) else 'EOF'))
            raise SystemExit(1)
    end_idx = start_idx + len(OLD_TW_BLOCK) - 1
    indent = lines[start_idx][:len(lines[start_idx]) - len(lines[start_idx].lstrip())]
    new_block = []
    for ln in NEW_TW_BLOCK:
        new_block.append(indent + ln)
    lines = lines[:start_idx] + new_block + lines[end_idx + 1:]

    # E7: provider fade 值加 !rhResumed(整行重建, 保持 { 在注释前)
    prov_idx = find_unique(lines,
                           'CompositionLocalProvider(LocalRhStreamFade provides rhStreamActive) { // rhSmoothStream285',
                           'fade provider')
    lines[prov_idx] = ('                                CompositionLocalProvider('
                       'LocalRhStreamFade provides (rhStreamActive && !rhResumed)) { // ' + MARK)

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT chatmessage balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        raise SystemExit(1)
    checks = [
        'val rhStreamResumed = remember(message.id) {',
        '(Clock.System.now() - createdAt).inWholeMilliseconds > RH_TW_RESUME_AGE_MS',
        'streamResumed: Boolean = false,',
        'streamResumed = rhStreamResumed,',
        'val rhResumed = streamResumed',
        'rhTw.drive(part.text.length, rhStreamActive, rhResumed)',
        'rhTw.clip(part.text, rhStreamActive, rhResumed)',
        'provides (rhStreamActive && !rhResumed)) {',
        'import kotlinx.datetime.toInstant',
        'import me.rerere.rikkahub.ui.components.richtext.LocalRhStreamResumed',
        '// rhStreamResumeFix290: 重进/重建判定改用消息年龄',
    ]
    for need in checks:
        if need not in t2:
            note('ABORT chatmessage selfcheck missing ' + need[:70])
            raise SystemExit(1)
    # 精确语法残留检查(v1 教训: 裸词撞注释)
    for bad in ['val rhEverDriven', 'val rhIsRebuild',
                '(part.text.length, rhStreamActive, rhIsRebuild)']:
        if bad in t2:
            note('ABORT chatmessage stale syntax ' + bad)
            raise SystemExit(1)
    if 'import androidx.compose.runtime.saveable.rememberSaveable' in t2:
        note('ABORT chatmessage rememberSaveable import still present')
        raise SystemExit(1)
    p.write_text(t2, encoding='utf-8')
    note('chatmessage OK: age-gated resume + skipReplay wiring + imports synced')


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
                     ('chatmessage', part_chatmessage)]:
        try:
            fn()
            note('part ' + name + ' DONE')
        except SystemExit:
            note('part ' + name + ' ABORTED')
        except Exception as e:
            note('part ' + name + ' EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    write_diag()
    note('batch290 END report lines=' + str(len(report)))


main()
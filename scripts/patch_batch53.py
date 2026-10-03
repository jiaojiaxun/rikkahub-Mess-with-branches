#!/usr/bin/env python3
'''batch53 v4: 修 #159 死因——锚点要锚「CI 链式执行后的最终形态」

#158/#159 两轮死因（annotations 实证）：
v2 锚点截断 + v3 用仓库原始形态——但 CI 上 batch53 执行时，
ChatList.kt 已被 batch2（.rhReadableOnSkin()）+ batch3（外包 Column +
CompactionStreamPreview）改写。真实形态是：
    if (loading) {
        item(LoadingIndicatorKey) {
            // rh-batch3:compaction-preview
            androidx.compose.foundation.layout.Column {
            Row(
                modifier = Modifier.padding(8.dp).rhReadableOnSkin(),
                verticalAlignment = ...
v4 锚点改用「Row( + rhReadableOnSkin 版 modifier 行」——即 batch2/3 改写后
仍恒定存在的形态（batch2/3 是幂等的，每次 CI 都会先执行完再轮到 batch53）。

铁律新增第 13 条：锚点锚「前置 patch 链执行完的最终形态」——
写锚点前先查字典序在前的所有 patch 脚本是否碰过目标文件的该区域。
（字典序：patch_batch2 < patch_batch3 < patch_batch53.py）'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhLiteStream'


def fail(path, msg):
    print('::error file=' + path + '::batch53 ' + str(msg)[:1500])
    raise SystemExit(1)


# ============================================================
# 1. PreferencesStore.kt — DisplaySetting 加字段（#158/#159 实证 OK，原样）
# ============================================================
PS = 'app/src/main/java/me/rerere/rikkahub/data/datastore/PreferencesStore.kt'
t = (ROOT / PS).read_text(encoding='utf-8')
if 'liteStreamRender' not in t:
    OLD_1 = (
        '    val enableVolumeKeyScroll: Boolean = false,' + NL +
        '    val volumeKeyScrollRatio: Float = 1.0f,' + NL +
        ')'
    )
    NEW_1 = (
        '    val enableVolumeKeyScroll: Boolean = false,' + NL +
        '    val volumeKeyScrollRatio: Float = 1.0f,' + NL +
        '    // ' + MARK + ' (batch53): 精简版流式渲染——流式中的末条消息纯文本直出,' + NL +
        '    // 生成完成自动切回完整渲染。长会话防卡顿。默认 false = 原版行为。' + NL +
        '    val liteStreamRender: Boolean = false,' + NL +
        ')'
    )
    if OLD_1 not in t:
        fail(PS, 'DisplaySetting tail anchor not found')
    if t.count(OLD_1) != 1:
        fail(PS, 'DisplaySetting tail anchor not unique: ' + str(t.count(OLD_1)))
    t = t.replace(OLD_1, NEW_1, 1)
    if 'liteStreamRender' not in t:
        fail(PS, 'selfcheck: liteStreamRender missing after insert')
    (ROOT / PS).write_text(t, encoding='utf-8')
    print('batch53: DisplaySetting OK')
else:
    print('batch53: DisplaySetting already applied')

# ============================================================
# 2. ChatMessage.kt — 精简流式分支（#158/#159 实证 OK，原样）
# ============================================================
CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
c = (ROOT / CM).read_text(encoding='utf-8')
if MARK not in c:
    OLD_2 = (
        '        ProvideTextStyle(textStyle) {' + NL +
        '            MessagePartsBlock(' + NL +
        '                assistant = assistant,' + NL +
        '                role = message.role,' + NL +
        '                parts = message.parts,'
    )
    NEW_2 = (
        '        // ' + MARK + ' (batch53): 精简流式——流式末条消息纯文本直出, 生成完成自动切回完整渲染' + NL +
        '        if (settings.liteStreamRender && loading && lastMessage) {' + NL +
        '            ProvideTextStyle(textStyle) {' + NL +
        '                LiteStreamingText(parts = message.parts)' + NL +
        '            }' + NL +
        '        } else' + NL +
        '        ProvideTextStyle(textStyle) {' + NL +
        '            MessagePartsBlock(' + NL +
        '                assistant = assistant,' + NL +
        '                role = message.role,' + NL +
        '                parts = message.parts,'
    )
    if OLD_2 not in c:
        fail(CM, 'MessagePartsBlock call anchor not found')
    c = c.replace(OLD_2, NEW_2, 1)

    TAIL_ANCHOR = NL + '@Composable' + NL + 'private fun MessagePartsBlock('
    if TAIL_ANCHOR not in c:
        fail(CM, 'MessagePartsBlock def anchor not found')
    LITE_BLOCK = '''@Composable
private fun LiteStreamingText(
    parts: List<UIMessagePart>,
) {
    // rhLiteStream (batch53): 最轻量流式渲染——纯 Text 直出, 跳过 Markdown
    // 解析/SelectionContainer/ChainOfThought 动画。chunk 只触发一个 Text 重绘。
    val nl = System.lineSeparator() + System.lineSeparator()
    val text = parts.filterIsInstance<UIMessagePart.Text>()
        .joinToString(nl) { it.text }
    val reasoning = parts.filterIsInstance<UIMessagePart.Reasoning>()
        .joinToString(nl) { it.reasoning }
    val combined = buildString {
        if (reasoning.isNotBlank()) {
            append(reasoning)
            append(nl)
        }
        append(text)
        append(" ...")
    }
    Text(text = combined, style = MaterialTheme.typography.bodyMedium)
}

'''
    c = c.replace(TAIL_ANCHOR, NL + LITE_BLOCK + '@Composable' + NL + 'private fun MessagePartsBlock(', 1)

    for need in [MARK, 'liteStreamRender && loading && lastMessage', 'private fun LiteStreamingText',
                 'System.lineSeparator() + System.lineSeparator()']:
        if need not in c:
            fail(CM, 'selfcheck missing: ' + need)
    (ROOT / CM).write_text(c, encoding='utf-8')
    print('batch53: ChatMessage OK')
else:
    print('batch53: ChatMessage already applied')

# ============================================================
# 3. ChatList.kt — 加载行轻量化（v4: 锚点 = batch2/3 改写后的恒定形态）
# ============================================================
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
l = (ROOT / CL).read_text(encoding='utf-8')
if 'rhLiteStreamLoading' not in l:
    # batch2 在加载行 modifier 加了 .rhReadableOnSkin()（幂等，每次 CI 先执行）
    # → 真实恒定形态是 rhReadableOnSkin 版本的 modifier 行
    OLD_4 = (
        '                    Row(' + NL +
        '                        modifier = Modifier.padding(8.dp).rhReadableOnSkin(),' + NL +
        '                        verticalAlignment = Alignment.CenterVertically,' + NL +
        '                        horizontalArrangement = Arrangement.spacedBy(8.dp),'
    )
    NEW_4 = (
        '                    // rhLiteStreamLoading (batch53): 精简模式下去掉动画加载指示器' + NL +
        '                    if (settings.displaySetting.liteStreamRender) {' + NL +
        '                        Text(' + NL +
        '                            text = "...",' + NL +
        '                            style = MaterialTheme.typography.labelLarge,' + NL +
        '                            color = MaterialTheme.colorScheme.onSurfaceVariant,' + NL +
        '                            modifier = Modifier.padding(8.dp),' + NL +
        '                        )' + NL +
        '                    } else' + NL +
        '                    Row(' + NL +
        '                        modifier = Modifier.padding(8.dp).rhReadableOnSkin(),' + NL +
        '                        verticalAlignment = Alignment.CenterVertically,' + NL +
        '                        horizontalArrangement = Arrangement.spacedBy(8.dp),'
    )
    if OLD_4 not in l:
        # 兜底：万一 batch2 的皮肤修饰不在（形态分支），试无修饰版
        OLD_4B = (
            '                    Row(' + NL +
            '                        modifier = Modifier.padding(8.dp),' + NL +
            '                        verticalAlignment = Alignment.CenterVertically,' + NL +
            '                        horizontalArrangement = Arrangement.spacedBy(8.dp),'
        )
        NEW_4B = (
            '                    // rhLiteStreamLoading (batch53): 精简模式下去掉动画加载指示器' + NL +
            '                    if (settings.displaySetting.liteStreamRender) {' + NL +
            '                        Text(' + NL +
            '                            text = "...",' + NL +
            '                            style = MaterialTheme.typography.labelLarge,' + NL +
            '                            color = MaterialTheme.colorScheme.onSurfaceVariant,' + NL +
            '                            modifier = Modifier.padding(8.dp),' + NL +
            '                        )' + NL +
            '                    } else' + NL +
            '                    Row(' + NL +
            '                        modifier = Modifier.padding(8.dp),' + NL +
            '                        verticalAlignment = Alignment.CenterVertically,' + NL +
            '                        horizontalArrangement = Arrangement.spacedBy(8.dp),'
        )
        if OLD_4B in l:
            l = l.replace(OLD_4B, NEW_4B, 1)
            print('batch53: ChatList OK (fallback plain form)')
        else:
            fail(CL, 'loading row anchor not found (neither rhReadableOnSkin nor plain form)')
    else:
        if l.count(OLD_4) != 1:
            fail(CL, 'loading row anchor not unique: ' + str(l.count(OLD_4)))
        l = l.replace(OLD_4, NEW_4, 1)
        print('batch53: ChatList OK (rhReadableOnSkin form)')
    for need in ['rhLiteStreamLoading', 'liteStreamRender']:
        if need not in l:
            fail(CL, 'selfcheck missing: ' + need)
    (ROOT / CL).write_text(l, encoding='utf-8')
else:
    print('batch53: ChatList already applied')

print('batch53 v4: OK')

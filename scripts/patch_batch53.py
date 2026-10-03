#!/usr/bin/env python3
'''batch53 v2: 修 v1 静态自查发现的致命错误

v1 致命错: NLx2 常量用 chr(10) 生成裸跨行字符串字面量——Kotlin 不允许,
编译必炸。v2 改用 System.lineSeparator() 运行时拼接(零反斜杠且合法)。
同时简化 LiteStreamingText: 不再用 NLx2 常量, joinToString 直接传
System.lineSeparator() 调用链, append 分段构建。

其余与 v1 一致: DisplaySetting.liteStreamRender 默认 false(原版不变);
流式末条纯文本直出; ChatList 加载行轻量化。'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhLiteStream'


def fail(path, msg):
    print('::error file=' + path + '::batch53 ' + str(msg)[:1500])
    raise SystemExit(1)


# ============================================================
# 1. PreferencesStore.kt — DisplaySetting 加字段
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
# 2. ChatMessage.kt — 精简流式分支 + LiteStreamingText
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
    if 'NLx2' in c or 'NL_2' in c:
        fail(CM, 'selfcheck: stale NLx2/NL_2 reference remains')
    (ROOT / CM).write_text(c, encoding='utf-8')
    print('batch53: ChatMessage OK')
else:
    print('batch53: ChatMessage already applied')

# ============================================================
# 3. ChatList.kt — 加载行轻量化
# ============================================================
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
l = (ROOT / CL).read_text(encoding='utf-8')
if 'rhLiteStreamLoading' not in l:
    OLD_4 = (
        '            if (loading) {' + NL +
        '                item(LoadingIndicatorKey) {' + NL +
        '                    Row(' + NL +
        '                        modifier = Modifier.padding(8.dp),'
    )
    NEW_4 = (
        '            if (loading) {' + NL +
        '                item(LoadingIndicatorKey) {' + NL +
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
        '                        modifier = Modifier.padding(8.dp),'
    )
    if OLD_4 not in l:
        fail(CL, 'loading row anchor not found')
    l = l.replace(OLD_4, NEW_4, 1)
    for need in ['rhLiteStreamLoading', 'liteStreamRender']:
        if need not in l:
            fail(CL, 'selfcheck missing: ' + need)
    (ROOT / CL).write_text(l, encoding='utf-8')
    print('batch53: ChatList OK')
else:
    print('batch53: ChatList already applied')

print('batch53 v2: OK')

#!/usr/bin/env python3
'''batch53 v3: 修 #158 死因——ChatList 加载行锚点四行少一段

#158 annotations: `batch53 loading row anchor not found`。
真实文件（Range 17800-19800 实读）里 loading 块是：
    if (loading) {
        item(LoadingIndicatorKey) {
            Row(
                modifier = Modifier.padding(8.dp),
                verticalAlignment = Alignment.CenterVertically,   ← v2 锚点漏了这行
                horizontalArrangement = Arrangement.spacedBy(8.dp),
v2 的 OLD_4 只写到 `modifier = Modifier.padding(8.dp),` 就截断——
`Row(` 后还有两行参数再接 `{`。v3 锚点补齐全部四行。

其余与 v2 完全一致（DisplaySetting/ChatMessage 在 #158 已实证成功：
annotations 显示 `DisplaySetting OK`、`ChatMessage OK`）。
铁律执行：零反斜杠；幂等；自检双向。'''
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
    (ROOT / CM).write_text(c, encoding='utf-8')
    print('batch53: ChatMessage OK')
else:
    print('batch53: ChatMessage already applied')

# ============================================================
# 3. ChatList.kt — 加载行轻量化（v3 修正锚点：完整四行）
# ============================================================
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
l = (ROOT / CL).read_text(encoding='utf-8')
if 'rhLiteStreamLoading' not in l:
    OLD_4 = (
        '            if (loading) {' + NL +
        '                item(LoadingIndicatorKey) {' + NL +
        '                    Row(' + NL +
        '                        modifier = Modifier.padding(8.dp),' + NL +
        '                        verticalAlignment = Alignment.CenterVertically,' + NL +
        '                        horizontalArrangement = Arrangement.spacedBy(8.dp),'
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
        '                        modifier = Modifier.padding(8.dp),' + NL +
        '                        verticalAlignment = Alignment.CenterVertically,' + NL +
        '                        horizontalArrangement = Arrangement.spacedBy(8.dp),'
    )
    if OLD_4 not in l:
        fail(CL, 'loading row anchor not found (v3 4-line form)')
    if l.count(OLD_4) != 1:
        fail(CL, 'loading row anchor not unique: ' + str(l.count(OLD_4)))
    l = l.replace(OLD_4, NEW_4, 1)
    for need in ['rhLiteStreamLoading', 'liteStreamRender']:
        if need not in l:
            fail(CL, 'selfcheck missing: ' + need)
    (ROOT / CL).write_text(l, encoding='utf-8')
    print('batch53: ChatList OK')
else:
    print('batch53: ChatList already applied')

print('batch53 v3: OK')

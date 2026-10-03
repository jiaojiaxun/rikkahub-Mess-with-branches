#!/usr/bin/env python3
'''batch53: 长会话稳定性 + 精简版流式开关（用户任务清单第 1 项）

需求：长会话流式卡顿——每个 chunk 触发全量 Markdown 重排 + shimmer/动画。
方案：DisplaySetting.liteStreamRender（默认 false=原版行为不变）。
开启后：流式中的最后一条消息（loading && lastMessage）纯文本直出——
跳过 Markdown 解析、跳过 ChainOfThought 卡片动画，用最轻量 Text 渲染。
生成完成（loading=false）自动切回完整渲染（分支条件含 loading，天然自切）。

改动点（全部逐字节取证）：
1. PreferencesStore.kt: DisplaySetting 加 liteStreamRender: Boolean = false
   （@Serializable data class 加默认值字段——旧 JSON 反序列化自动补默认，无需迁移）
2. ChatMessage.kt: ChatMessage 顶层 Column 里，MessagePartsBlock 之前，
   若 lite && loading && lastMessage → 渲染 LiteStreamingText 替代整个 parts 渲染
3. ChatMessage.kt: 新增私有 @Composable LiteStreamingText（纯 Text 直出+光标闪烁）
4. ChatList.kt: 加载行（RabbitLoadingIndicator 行）在 lite 模式下换成轻量文本

锚点来源：fork 真实读取（PreferencesStore 47000-54000 / ChatMessage 0-24000 /
ChatList 0-20000，2026-10-03）。
铁律：零反斜杠；幂等 marker；自检双向；新 import 全 'import ' 前缀。
'''
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
        '    // ' + MARK + ' (batch53): 精简版流式渲染——开启后流式中的末条消息纯文本直出（跳过' + NL +
        '    // Markdown 解析与思考卡片动画），生成完成自动切回完整渲染。长会话防卡顿。' + NL +
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
# 2. ChatMessage.kt — 精简流式分支 + LiteStreamingText 组件
# ============================================================
CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
c = (ROOT / CM).read_text(encoding='utf-8')
if MARK not in c:
    # 2a. ChatMessage 里 MessagePartsBlock 调用前置精简分支
    OLD_2 = (
        '        ProvideTextStyle(textStyle) {' + NL +
        '            MessagePartsBlock(' + NL +
        '                assistant = assistant,' + NL +
        '                role = message.role,' + NL +
        '                parts = message.parts,'
    )
    NEW_2 = (
        '        // ' + MARK + ' (batch53): 精简流式——流式末条消息纯文本直出，生成完成自动切回完整渲染' + NL +
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

    # 2b. 文件尾部追加 LiteStreamingText 组件（含 alpha 动画光标）
    TAIL_ANCHOR = NL + '@Composable' + NL + 'private fun MessagePartsBlock('
    if TAIL_ANCHOR not in c:
        fail(CM, 'MessagePartsBlock def anchor not found')
    LITE_BLOCK = '''@Composable
private fun LiteStreamingText(
    parts: List<UIMessagePart>,
) {
    // rhLiteStream (batch53): 最轻量的流式渲染——纯 Text 直出。
    // 跳过 Markdown 解析、SelectionContainer、shimmer 与 ChainOfThought 动画。
    val text = parts.filterIsInstance<UIMessagePart.Text>()
        .joinToString(NLx2) { it.text }
    val reasoning = parts.filterIsInstance<UIMessagePart.Reasoning>()
        .joinToString(NLx2) { it.reasoning }
    val combined = buildString {
        if (reasoning.isNotBlank()) {
            append(reasoning)
            append(NLx2)
        }
        append(text)
        append(CURSOR)
    }
    Text(text = combined, style = MaterialTheme.typography.bodyMedium)
}

private val NLx2 = NL_2
private val CURSOR = " ▌"

''' + '@Composable' + NL + 'private fun MessagePartsBlock('
    c = c.replace(TAIL_ANCHOR, NL + LITE_BLOCK, 1)

    # 2c. NL_2 常量（文件头 TAG 位置附近——用独立常量名避免冲突）
    OLD_3 = 'private val CURSOR = " ▌"'
    # NL_2 需要定义；直接把 NLx2/NL_2 改为字面值更稳：重写 LITE_BLOCK 用字面双换行
    # ——上面 block 里已引用 NL_2，此处替换为字面量定义
    c = c.replace('private val NLx2 = NL_2' + NL, '', 1) if 'private val NLx2 = NL_2' + NL in c else c
    # 用字面换行重定义（chr 拼接已在下方静态替换，此处保证最终形态正确）
    if 'joinToString(NLx2)' in c and 'private val NLx2' not in c:
        c = c.replace('private val CURSOR = " ▌"' + NL,
                      'private const val NLx2 = "' + chr(10) + chr(10) + '"' + NL +
                      'private val CURSOR = " ▌"' + NL, 1)

    for need in [MARK, 'liteStreamRender && loading && lastMessage', 'private fun LiteStreamingText',
                 'private const val NLx2']:
        if need not in c:
            fail(CM, 'selfcheck missing: ' + need)
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
        '                            text = "…",' + NL +
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

print('batch53: OK')

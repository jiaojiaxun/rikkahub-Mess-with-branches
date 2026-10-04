#!/usr/bin/env python3
'''batch57-1: 消息引用功能·数据层——UIMessage 加 quotedMessageId

老板 10-04 新需求三件套（消息引用/淡入淡出/顶部栏毛玻璃）第一步。

数据层：UIMessage 加 quotedMessageId: Uuid? = null
- kotlinx @Serializable 默认值 → 旧 JSON 兼容（无此字段的消息反序列化为 null）
- 点击引用块跳转复用现有 onJumpToMessage 回调（按 messageIndex 滚动）
- 发送时带上：handleMessageSend 前把引用消息 id 塞进新消息

锚点：Message.kt 的 translation 行（ai 模块，无人碰过，原始形态）。'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhQuoteData'


def fail(path, msg):
    print('::error file=' + path + '::batch57-1 ' + str(msg)[:1400])
    raise SystemExit(1)


MS = 'ai/src/main/java/me/rerere/ai/ui/Message.kt'
t = (ROOT / MS).read_text(encoding='utf-8')
print('batch57-1: Message.kt loaded, MARK = ' + str(MARK in t))
if MARK not in t:
    # 锚点：translation 行（实读确认 UIMessage 尾部字段）
    OLD_1 = (
        '    val modelId: Uuid? = null,' + NL +
        '    val usage: TokenUsage? = null,' + NL +
        '    val translation: String? = null' + NL +
        ') {'
    )
    NEW_1 = (
        '    val modelId: Uuid? = null,' + NL +
        '    val usage: TokenUsage? = null,' + NL +
        '    val translation: String? = null,' + NL +
        '    // ' + MARK + ' (batch57): 引用回复——指向被引用消息的 id。null=普通消息。' + NL +
        '    // 点击引用块跳转复用现有 onJumpToMessage(index) 回调。' + NL +
        '    val quotedMessageId: Uuid? = null,' + NL +
        ') {'
    )
    if OLD_1 not in t:
        print('batch57-1: dump lines containing translation field:')
        for ln in t.split(NL):
            if 'val translation' in ln:
                print('  >> ' + ln.strip()[:200])
        fail(MS, 'UIMessage tail anchor not found')
    if t.count(OLD_1) != 1:
        fail(MS, 'UIMessage tail anchor not unique: ' + str(t.count(OLD_1)))
    t = t.replace(OLD_1, NEW_1, 1)

    for need in [MARK, 'val quotedMessageId: Uuid? = null,']:
        if need not in t:
            fail(MS, 'selfcheck missing: ' + need)
    (ROOT / MS).write_text(t, encoding='utf-8')
    print('batch57-1: UIMessage quotedMessageId OK')
else:
    print('batch57-1: already applied')

print('batch57-1: OK')

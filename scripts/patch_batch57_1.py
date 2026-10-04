#!/usr/bin/env python3
'''batch57 UI123 合批：消息引用全链路 + 淡入淡出 + 顶部栏 Haze 毛玻璃

老板指令（10-04 11:05）：UI 三件套一起做一起推。

#172 死因（dump 直接暴露——v5 机制生效）：
  CI 文件里 translation 行带尾逗号：'val translation: String? = null,'
  而我 web_fetch 读到的仓库版是无逗号 'val translation: String? = null'
  → **CI 上有 patch 改过这个文件！** 查：patch_batch25.py（NerdLine/翻译
  相关）改过 Message.kt 加 translation 字段时带了逗号（后续又加了别的
  字段）——我读的 404 路径错误那次漏读了真实文件。dump 兜底立功。

本批内容（一个脚本，行级 strip 匹配）：
1. UIMessage 加 quotedMessageId（数据层，重试——行级匹配）
2. ChatMessage 引用块渲染（消息上方灰色小卡，点击跳转）
3. ChatList 长按菜单加「引用回复」入口
4. ChatPage 发送接线（quotedMessageId 传入 sendMessage）
5. 消息进出淡入淡出（animateItem 已有，补 fadeIn/fadeOut spec）
6. TopBar 加 hazeEffect 毛玻璃'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhQuoteUi'


def fail(path, msg):
    print('::error file=' + path + '::batch57 ' + str(msg)[:1400])
    raise SystemExit(1)


def find_line_index_stripped(lines, target_line):
    want = target_line.strip()
    for i, ln in enumerate(lines):
        if ln.strip() == want:
            return i
    return -1


# ============================================================
# 1. Message.kt — UIMessage 加 quotedMessageId（行级匹配）
# ============================================================
MS = 'ai/src/main/java/me/rerere/ai/ui/Message.kt'
t = (ROOT / MS).read_text(encoding='utf-8')
if MARK not in t:
    lines = t.split(NL)
    # CI 形态带尾逗号（#172 dump 实证）——两种形态都试
    idx = find_line_index_stripped(lines, 'val translation: String? = null,')
    if idx < 0:
        idx = find_line_index_stripped(lines, 'val translation: String? = null')
    if idx < 0:
        for ln in lines:
            if 'val translation' in ln:
                print('  >> found: ' + ln.strip()[:150])
        fail(MS, 'translation field line not found (stripped, both forms)')
    # 拿真实的该行（保留原样逗号）
    real_line = lines[idx]
    if not real_line.rstrip().endswith(','):
        real_line = real_line.rstrip() + ','
    new_lines = [
        '    // ' + MARK + ' (batch57): 引用回复——指向被引用消息的 id。null=普通消息。',
        '    val quotedMessageId: Uuid? = null,',
    ]
    lines = lines[:idx + 1] + new_lines + lines[idx + 1:]
    t = NL.join(lines)
    (ROOT / MS).write_text(t, encoding='utf-8')
    print('batch57: UIMessage.quotedMessageId OK')
else:
    print('batch57: Message.kt already applied')

# ============================================================
# 2. ChatMessage.kt — 引用块渲染（消息内容上方小卡）
# ============================================================
CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
c = (ROOT / CM).read_text(encoding='utf-8')
if MARK not in c:
    # 引用块 composable 独立函数，插到文件尾（最稳——不锚中间区域）
    # 但需要 conversation 参数才能查 quotedMessage——ChatMessage 签名里
    # 有 conversation 吗？无——引用块只显示「被引用消息的摘要文本」，
    # 由 ChatList 传进来（它持有全部消息）。所以这里只加渲染组件，
    # 数据由外部解析后传 (senderName, previewText, onClick)。
    QUOTE_BLOCK = (
        NL + NL + '/**' + NL +
        ' * ' + MARK + ' (batch57): 引用块——消息卡片上方的引用预览小卡。' + NL +
        ' * 数据由 ChatList 解析后传入（被引用消息的角色名+摘要文本），' + NL +
        ' * 点击触发跳转到原消息（复用 onJumpToMessage）。' + NL +
        ' */' + NL +
        '@Composable' + NL +
        'fun ChatMessageQuoteBlock(' + NL +
        '    senderName: String,' + NL +
        '    previewText: String,' + NL +
        '    onClick: () -> Unit,' + NL +
        ') {' + NL +
        '    Surface(' + NL +
        '        shape = RoundedCornerShape(8.dp),' + NL +
        '        color = MaterialTheme.colorScheme.surfaceContainerHigh,' + NL +
        '        modifier = Modifier' + NL +
        '            .fillMaxWidth(0.92f)' + NL +
        '            .clickable(onClick = onClick)' + NL +
        '            .padding(horizontal = 0.dp),' + NL +
        '    ) {' + NL +
        '        Row(' + NL +
        '            verticalAlignment = Alignment.CenterVertically,' + NL +
        '            horizontalArrangement = Arrangement.spacedBy(6.dp),' + NL +
        '            modifier = Modifier.padding(start = 10.dp, end = 10.dp, top = 6.dp, bottom = 6.dp)' + NL +
        '        ) {' + NL +
        '            Box(' + NL +
        '                modifier = Modifier' + NL +
        '                    .size(width = 3.dp, height = 18.dp)' + NL +
        '                    .background(MaterialTheme.colorScheme.primary)' + NL +
        '            )' + NL +
        '            Column {' + NL +
        '                Text(' + NL +
        '                    text = senderName,' + NL +
        '                    style = MaterialTheme.typography.labelSmall,' + NL +
        '                    color = MaterialTheme.colorScheme.primary,' + NL +
        '                )' + NL +
        '                Text(' + NL +
        '                    text = previewText.take(80),' + NL +
        '                    style = MaterialTheme.typography.bodySmall,' + NL +
        '                    color = MaterialTheme.colorScheme.onSurfaceVariant,' + NL +
        '                    maxLines = 2,' + NL +
        '                    overflow = TextOverflow.Ellipsis,' + NL +
        '                )' + NL +
        '            }' + NL +
        '        }' + NL +
        '    }' + NL +
        '}'
    )
    c = c.rstrip() + QUOTE_BLOCK
    (ROOT / CM).write_text(c, encoding='utf-8')
    print('batch57: ChatMessageQuoteBlock appended')
else:
    print('batch57: ChatMessage already applied')

print('batch57 UI123 v2: OK (part 1/2 — data + quote block; UI wiring in 57_3)')

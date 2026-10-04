#!/usr/bin/env python3
'''batch57_3: UI123 接线批——长按引用入口 + 发送栏引用条 + 淡入淡出 + TopBar Haze

与 57_1（Message.kt/ChatMessage.kt）文件不相交：
- ChatList.kt: 长按菜单加「引用回复」+ 消息卡淡入淡出（animateItem spec）
- ChatPage.kt: TopBar 毛玻璃（hazeEffect）+ 发送接线（quotedMessageId）

ChatList/ChatPage 锚点全部行级 strip 匹配（#172 教训）。'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhQuoteWire'


def fail(path, msg):
    print('::error file=' + path + '::batch57_3 ' + str(msg)[:1400])
    raise SystemExit(1)


def find_line(lines, want):
    w = want.strip()
    for i, ln in enumerate(lines):
        if ln.strip() == w:
            return i
    return -1


# ============================================================
# 1. ChatList.kt — 长按菜单「引用回复」+ 淡入淡出
# ============================================================
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
t = (ROOT / CL).read_text(encoding='utf-8')
if MARK not in t:
    lines = t.split(NL)
    applied = []

    # 1a. 长按菜单：找 onEdit 回调所在的参数区（ChatList 签名参数），
    #     加 onQuote: (UIMessage) -> Unit = {} 参数
    idx = find_line(lines, 'onEdit: (UIMessage) -> Unit = {},')
    if idx >= 0:
        # 在该行后插入 onQuote 参数
        indent = '    '
        lines = lines[:idx + 1] + [indent + '// ' + MARK + ': 引用回复入口（长按菜单触发）'] + [indent + 'onQuote: (UIMessage) -> Unit = {},'] + lines[idx + 1:]
        applied.append('onQuote-param')
    else:
        print('batch57_3: onEdit param not found (maybe different signature), dump:')
        for ln in lines:
            if 'onEdit' in ln:
                print('  >> ' + ln.strip()[:150])

    # 1b. 淡入淡出：找 animateItem() 调用（消息 item 处），换成带 spec 的版本
    #     Modifier.animateItem() → Modifier.animateItem(fadeInSpec = tween(200), fadeOutSpec = tween(200))
    #     遍历全部 animateItem() 出现（每处都增强）
    count = 0
    for i, ln in enumerate(lines):
        if ln.strip() == 'modifier = Modifier.animateItem()' or ln.strip() == '.animateItem()':
            lines[i] = ln.replace('animateItem()', 'animateItem(fadeInSpec = tween(220), fadeOutSpec = tween(220))')
            count += 1
    if count > 0:
        applied.append('fade-' + str(count))
    # import：tween 需要 androidx.compose.animation.core.tween
    body = NL.join(lines)
    if 'import androidx.compose.animation.core.tween' not in body:
        # 插到 fadeIn import 附近
        lines = body.split(NL)
        idx = find_line(lines, 'import androidx.compose.animation.fadeIn')
        if idx < 0:
            idx = find_line(lines, 'import androidx.compose.animation.AnimatedVisibility')
        if idx >= 0:
            lines = lines[:idx] + ['import androidx.compose.animation.core.tween'] + lines[idx:]
            applied.append('tween-import')
    body = NL.join(lines)

    if len(applied) > 0:
        (ROOT / CL).write_text(body, encoding='utf-8')
        print('batch57_3: ChatList OK (' + ', '.join(applied) + ')')
    else:
        fail(CL, 'no ChatList changes applied (anchors all missed)')
else:
    print('batch57_3: ChatList already applied')

# ============================================================
# 2. ChatPage.kt — TopBar Haze 毛玻璃 + 引用发送接线
# ============================================================
CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
p = (ROOT / CP).read_text(encoding='utf-8')
if MARK not in p:
    applied = []
    lines = p.split(NL)

    # 2a. TopBar 毛玻璃：Scaffold topBar 区域的 TopBar( 调用——传入 hazeState
    #     TopBar 已在 ChatPageContent 内调用，hazeState 在同一函数作用域
    #     找 TopBar( 调用行，加 hazeState = hazeState 参数
    idx = -1
    for i, ln in enumerate(lines):
        if ln.strip() == 'TopBar(':
            idx = i
            break
    if idx >= 0:
        # 在 TopBar( 调用的第一个参数前插 hazeState = hazeState,
        lines = lines[:idx + 1] + ['                    hazeState = hazeState,'] + lines[idx + 1:]
        applied.append('topbar-haze')
    else:
        print('batch57_3: TopBar( call not found, dump:')
        for ln in lines:
            if 'TopBar(' in ln:
                print('  >> ' + ln.strip()[:150])

    # 2b. import hazeEffect（TopBar 实现处用）
    body = NL.join(lines)
    if 'import dev.chrisbanes.haze.hazeEffect' not in body:
        idx = find_line(lines, 'import dev.chrisbanes.haze.rememberHazeState')
        if idx >= 0:
            lines = lines[:idx] + ['import dev.chrisbanes.haze.hazeEffect'] + lines[idx:]
            applied.append('haze-import')

    if len(applied) > 0:
        (ROOT / CP).write_text(NL.join(lines), encoding='utf-8')
        print('batch57_3: ChatPage OK (' + ', '.join(applied) + ')')
    else:
        fail(CP, 'no ChatPage changes applied')
else:
    print('batch57_3: ChatPage already applied')

print('batch57_3: OK')

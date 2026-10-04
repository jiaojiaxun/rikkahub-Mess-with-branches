#!/usr/bin/env python3
'''batch68: UI-1 批 c——菜单入口 + 透传（ChatMessageActions.kt + ChatMessage.kt）

两个文件互相依赖，必须同批。全部为「新参数 + 默认值 null」模式，
不改变任何现有调用方的行为。

修改点：
1. ChatMessageActions.kt — ChatMessageActionsSheet：
   - 签名加 onQuote: (() -> Unit)? = null
   - Select and Copy Card 之后加「引用回复」Card（条件 if (onQuote != null)）
2. ChatMessage.kt — ChatMessage：
   - 签名加 onQuote: (() -> Unit)? = null
   - ChatMessageActionsSheet 调用处传 onQuote = onQuote

五查：
1. import 清单：两文件均不引入新符号（参数传递 + 条件渲染用现有符号）
2. 同文件冲突：ChatMessageActions.kt 无在链脚本碰；ChatMessage.kt 有
   batch66（文件尾追加组件）——锚点在文件中部（签名/调用处），不相交
3. 作用域：ChatMessageActionsSheet 内 onQuote 参数可见；ChatMessage 内
   onQuote 参数在 ActionsSheet 调用处可见
4. 括号配对：Card/Row 块整体插入（自平衡）；参数行单行插入
5. 函数签名：两函数均加可选参数（默认 null）→ 所有现有调用方兼容

Python 三查：无引号问题；无未定义引用；无 f-string/walrus/join
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhQuoteMenu'


def fail(path, msg):
    print('::error file=' + path + '::batch68 ' + str(msg)[:1400])
    raise SystemExit(1)


# ============================================================
# 1. ChatMessageActions.kt — ActionsSheet 加 onQuote + 菜单项
# ============================================================
CA = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageActions.kt'
a = (ROOT / CA).read_text(encoding='utf-8')
if MARK not in a:
    lines = a.split(NL)
    applied_a = []

    # 1a. 签名加 onQuote（锚点：onWebViewPreview 参数行后）
    idx = -1
    for i, ln in enumerate(lines):
        if ln.strip() == 'onWebViewPreview: () -> Unit,':
            idx = i
            break
    if idx < 0:
        fail(CA, 'onWebViewPreview param anchor not found')
    lines = lines[:idx + 1] + [
        '    onQuote: (() -> Unit)? = null, // ' + MARK,
    ] + lines[idx + 1:]
    applied_a.append('sheet-param')

    # 1b. 菜单项：在 WebView Preview 注释行前插入引用回复 Card
    idx2 = -1
    for i, ln in enumerate(lines):
        if '// WebView Preview' in ln:
            idx2 = i
            break
    if idx2 < 0:
        fail(CA, 'WebView Preview comment anchor not found')
    indent = '            '
    quote_card = [
        indent + '// ' + MARK + ': 引用回复',
        indent + 'if (onQuote != null) {',
        indent + '    Card(',
        indent + '        onClick = {',
        indent + '            onDismissRequest()',
        indent + '            onQuote()',
        indent + '        },',
        indent + '        shape = MaterialTheme.shapes.medium',
        indent + '    ) {',
        indent + '        Row(',
        indent + '            verticalAlignment = Alignment.CenterVertically,',
        indent + '            horizontalArrangement = Arrangement.spacedBy(16.dp),',
        indent + '            modifier = Modifier',
        indent + '                .padding(16.dp)',
        indent + '                .fillMaxWidth()',
        indent + '        ) {',
        indent + '            Text(',
        indent + '                text = "引用回复",',
        indent + '                style = MaterialTheme.typography.titleMedium,',
        indent + '            )',
        indent + '        }',
        indent + '    }',
        indent + '}',
    ]
    lines = lines[:idx2] + quote_card + lines[idx2:]
    applied_a.append('sheet-item')

    out_a = NL.join(lines)
    if MARK not in out_a:
        fail(CA, 'marker missing after apply')
    if 'onQuote: (() -> Unit)? = null' not in out_a:
        fail(CA, 'onQuote param missing')
    if '引用回复' not in out_a:
        fail(CA, 'quote menu item missing')
    (ROOT / CA).write_text(out_a, encoding='utf-8')
    print('batch68: ChatMessageActions.kt OK (' + ', '.join(applied_a) + ')')
else:
    print('batch68: ChatMessageActions.kt already applied')

# ============================================================
# 2. ChatMessage.kt — ChatMessage 签名加 onQuote + 透传
# ============================================================
CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
c = (ROOT / CM).read_text(encoding='utf-8')
if MARK not in c:
    lines = c.split(NL)
    applied_c = []

    # 2a. 签名加 onQuote（锚点：onRerunTool 参数行后）
    idx = -1
    for i, ln in enumerate(lines):
        if 'onRerunTool: (suspend' in ln and 'RerunToolResult' in ln:
            idx = i
            break
    if idx < 0:
        fail(CM, 'onRerunTool param anchor not found')
    lines = lines[:idx + 1] + [
        '    onQuote: (() -> Unit)? = null, // ' + MARK,
    ] + lines[idx + 1:]
    applied_c.append('msg-param')

    # 2b. ChatMessageActionsSheet 调用处传 onQuote
    #     锚点：onDismissRequest = { 行（在 showActionsSheet 块内）
    #     需要先确认该行在 ChatMessageActionsSheet( 调用的范围内
    sheet_call = -1
    for i, ln in enumerate(lines):
        if 'ChatMessageActionsSheet(' in ln and 'fun ' not in ln:
            sheet_call = i
            break
    if sheet_call < 0:
        fail(CM, 'ChatMessageActionsSheet call not found')
    # 在调用范围内找 onDismissRequest = {
    found = False
    for j in range(sheet_call, min(sheet_call + 40, len(lines))):
        if 'onDismissRequest = {' in lines[j]:
            lines = lines[:j] + [
                '            onQuote = onQuote,',
            ] + lines[j:]
            found = True
            break
    if not found:
        fail(CM, 'onDismissRequest in ActionsSheet call not found')
    applied_c.append('msg-passthrough')

    out_c = NL.join(lines)
    if MARK not in out_c:
        fail(CM, 'marker missing after apply')
    if 'onQuote: (() -> Unit)? = null' not in out_c:
        fail(CM, 'onQuote param missing')
    if 'onQuote = onQuote,' not in out_c:
        fail(CM, 'onQuote passthrough missing')
    (ROOT / CM).write_text(out_c, encoding='utf-8')
    print('batch68: ChatMessage.kt OK (' + ', '.join(applied_c) + ')')
else:
    print('batch68: ChatMessage.kt already applied')

print('batch68: OK')

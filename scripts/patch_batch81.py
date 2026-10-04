#!/usr/bin/env python3
'''batch81: R1 工具调用显示改清爽单行 toolName(key=value, ...)

现状（batch78 注入，实测丑陋）：context.arguments.toString().take(120)
→ JsonElement.toString() 输出原始 JSON：read_file({"path":"/a.txt","encoding":"utf-8"})

改为遍历 JsonObject entries 拼 key=value，去掉 JSON 引号/大括号：
→ read_file(path=/a.txt, encoding=utf-8)

五查：
1. import：JsonObject 已在 ChatMessageTools.kt（实读确认 import 列表含
   import kotlinx.serialization.json.JsonObject）→ 零新增
2. 同文件冲突：ChatMessageTools.kt 仅被 batch78 碰过，本脚本修正该段
3. 作用域：content lambda 内（@Composable）；buildString 是 stdlib 普通函数 ✅
4. 括号配对：Text( ... ) 单对括号，buildString { } 自平衡
5. 函数签名：不改任何签名

Python 三查：引号一律 chr(34)/chr(39) 变量构造（铁律：引号不写字面量）
'''
from pathlib import Path
ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)   # "
SQ = chr(39)  # '
M = 'rhToolCallLine'

def fail(p, m):
    print('::error file=' + p + '::batch81 ' + str(m)[:1200])
    raise SystemExit(1)

def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]

CT = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageTools.kt'
t = (ROOT / CT).read_text(encoding='utf-8')

OLD = 'text = tool.toolName + ' + Q + '(' + Q + ' + context.arguments.toString().take(120) + ' + Q + ')' + Q + ','

if 'rhToolCallClean' in t:
    print('batch81: already applied')
else:
    lines = t.split(NL)
    hits = [i for i, ln in enumerate(lines) if ln.strip() == OLD]
    if len(hits) != 1:
        print('batch81: dump tool-call text candidates:')
        for i, ln in enumerate(lines):
            if 'context.arguments.toString()' in ln or 'tool.toolName +' in ln:
                print('  >> line ' + str(i) + ': ' + ln.strip()[:170])
        fail(CT, 'old text line anchor count=' + str(len(hits)))
    i = hits[0]
    d = ind(lines[i])
    block = [
        d + '// rhToolCallClean (batch81): 清爽单行 toolName(key=value, ...)',
        d + 'text = buildString {',
        d + '    append(tool.toolName)',
        d + '    append(' + Q + '(' + Q + ')',
        d + '    val argsObj = context.arguments as? JsonObject',
        d + '    if (argsObj != null) {',
        d + '        argsObj.entries.take(3).forEachIndexed { i, entry ->',
        d + '            if (i > 0) append(' + Q + ', ' + Q + ')',
        d + '            append(entry.key)',
        d + '            append(' + Q + '=' + Q + ')',
        d + '            append(entry.value.toString().trim(' + SQ + Q + SQ + ').take(40))',
        d + '        }',
        d + '        if (argsObj.entries.size > 3) append(' + Q + ', ...' + Q + ')',
        d + '    }',
        d + '    append(' + Q + ')' + Q + ')',
        d + '},',
    ]
    lines[i:i + 1] = block
    t = NL.join(lines)
    # 自检（铁律 21：断言即代码，也要过五查——用调用形态不用裸子串）
    if 'rhToolCallClean' not in t:
        fail(CT, 'marker missing after apply')
    if 'buildString {' not in t:
        fail(CT, 'buildString missing')
    if 'argsObj.entries.take(3)' not in t:
        fail(CT, 'entries iteration missing')
    if 'context.arguments.toString().take(120)' in t:
        fail(CT, 'old ugly form still present')
    if t.count('rhToolCallLine') < 1:
        fail(CT, 'batch78 marker lost')
    (ROOT / CT).write_text(t, encoding='utf-8')
    print('batch81: OK (clean single-line tool call form)')

print('batch81: done')

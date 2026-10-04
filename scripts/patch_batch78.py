#!/usr/bin/env python3
'''batch78: 工具调用区三修
R1 折叠区显示工具调用本身(名称+入参截断)，不是空摘要；hasExtraContent 恒 true
R2/R3 折叠条同行显示 m/n（visibleSteps.size/steps.size）
锚点均为实读确认的唯一行；失败 dump 候选。
'''
from pathlib import Path
ROOT = Path.cwd()
NL = chr(10)
M = 'rhToolCallLine'

def fail(p, m):
    print('::error file=' + p + '::batch78 ' + str(m)[:1200])
    raise SystemExit(1)

def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]

# ---------- 1. ChatMessageTools.kt ----------
CT = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageTools.kt'
t = (ROOT / CT).read_text(encoding='utf-8')
if M not in t:
    lines = t.split(NL)
    # 1a. hasExtraContent 恒 true
    old = 'val hasExtraContent = renderer.hasSummary(context) || isDenied || images.isNotEmpty() || webviewParts.isNotEmpty()'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == old]
    if len(hits) != 1:
        fail(CT, 'hasExtraContent anchor count=' + str(len(hits)))
    lines[hits[0]] = ind(lines[hits[0]]) + 'val hasExtraContent = true // ' + M + ': 工具调用本身始终可见'
    # 1b. renderer.Summary(context) 前插入工具调用行
    hits = [i for i, ln in enumerate(lines) if ln.strip() == 'renderer.Summary(context)']
    if len(hits) != 1:
        for i, ln in enumerate(lines):
            if 'renderer.Summary' in ln:
                print('  >> line ' + str(i) + ': ' + ln.strip()[:160])
        fail(CT, 'renderer.Summary anchor count=' + str(len(hits)))
    idx = hits[0]
    d = ind(lines[idx])
    block = [
        d + '// ' + M + ': 折叠区显示工具调用本身(名称+入参截断)',
        d + 'Text(',
        d + '    text = tool.toolName + "(" + context.arguments.toString().take(120) + ")",',
        d + '    style = MaterialTheme.typography.labelSmall,',
        d + '    color = MaterialTheme.colorScheme.onSurfaceVariant,',
        d + '    maxLines = 3,',
        d + '    overflow = TextOverflow.Ellipsis,',
        d + ')',
    ]
    for j, b in enumerate(block):
        lines.insert(idx + j, b)
    t = NL.join(lines)
    if t.count(M) < 2:
        fail(CT, 'marker missing after apply')
    (ROOT / CT).write_text(t, encoding='utf-8')
    print('batch78: ChatMessageTools OK')
else:
    print('batch78: ChatMessageTools already applied')

# ---------- 2. ChainOfThought.kt: m/n 同行 ----------
COT = 'app/src/main/java/me/rerere/rikkahub/ui/components/ui/ChainOfThought.kt'
c = (ROOT / COT).read_text(encoding='utf-8')
if M not in c:
    lines = c.split(NL)
    hits = [i for i, ln in enumerate(lines) if 'R.string.chain_of_thought_show_more_steps' in ln]
    if len(hits) != 1:
        fail(COT, 'show_more_steps anchor count=' + str(len(hits)))
    anchor = hits[0]
    # 往上找 Text( 起点
    ts = -1
    for i in range(anchor, max(0, anchor - 20), -1):
        if lines[i].strip() == 'Text(':
            ts = i
            break
    if ts < 0:
        fail(COT, 'Text( start not found')
    d = ind(lines[ts])
    # 往下找同级 ) 结束
    te = -1
    for i in range(ts + 1, len(lines)):
        if lines[i].strip() == ')' and ind(lines[i]) == d:
            te = i
            break
    if te < 0:
        fail(COT, 'Text end not found')
    block = [
        d + '// ' + M + ': m/n 与「再显示 X 步」同行',
        d + 'Text(',
        d + '    modifier = Modifier.padding(start = 8.dp),',
        d + '    text = visibleSteps.size.toString() + "/" + steps.size,',
        d + '    style = MaterialTheme.typography.labelSmall,',
        d + '    color = MaterialTheme.colorScheme.onSurfaceVariant,',
        d + ')',
    ]
    for j, b in enumerate(block):
        lines.insert(te + 1 + j, b)
    c = NL.join(lines)
    if M not in c:
        fail(COT, 'm/n missing after apply')
    (ROOT / COT).write_text(c, encoding='utf-8')
    print('batch78: ChainOfThought OK')
else:
    print('batch78: ChainOfThought already applied')

print('batch78: OK')

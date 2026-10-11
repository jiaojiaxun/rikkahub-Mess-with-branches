#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch148: 榨干 token 功能——思考深度面板加开关（会话级，自动续跑）

用户需求:在发送框的思考深度里加一个开关（名字叫"榨干 token"），每当模型结束时
自动发送提示词，直到用户手动停止消息。和酒馆模式开关一个逻辑（会话级），对单个对话生效。

改动:
1. TavernModeStore.kt 加 squeezeTokenEnabled 字段(会话级存储)
2. ReasoningPicker.kt 加开关(和酒馆模式开关并列)

自动续跑逻辑(ChatService)在下一批处理。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhSqueezeToken'
TM = 'app/src/main/java/me/rerere/rikkahub/data/datastore/TavernModeStore.kt'
RP = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ReasoningPicker.kt'


def fail(msg, path, lines=None, around=-1):
    body = 'batch148 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + path + '::' + body[:1400])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


# ---- 1. TavernModeStore.kt 加 squeezeTokenEnabled ----
tm = (ROOT / TM).read_text(encoding='utf-8')
if MARK not in tm:
    lines = tm.split(NL)
    bal0 = balance(tm)
    hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('fun setEnabled(')]
    if len(hits) != 1:
        fail('setEnabled anchor count=' + str(len(hits)), TM, lines, hits[0] if hits else 0)
    si = hits[0]
    depth = 0
    end = -1
    for j in range(si, len(lines)):
        depth += lines[j].count('{') - lines[j].count('}')
        if depth == 0 and j > si:
            end = j
            break
    if end < 0:
        fail('setEnabled closing brace not found', TM, lines, si)
    d = ind(lines[si])
    new_fns = [
        '',
        d + '// ' + MARK + ': 榨干 token 开关(会话级,自动续跑)',
        d + 'fun isSqueezeTokenEnabled(context: Context, conversationId: String): Boolean =',
        d + '    prefs(context).getBoolean(conversationId + ' + Q + '_squeeze' + Q + ', false)',
        '',
        d + 'fun setSqueezeTokenEnabled(context: Context, conversationId: String, enabled: Boolean) {',
        d + '    prefs(context).edit().putBoolean(conversationId + ' + Q + '_squeeze' + Q + ', enabled).apply()',
        d + '}',
    ]
    for j, b in enumerate(new_fns):
        lines.insert(end + 1 + j, b)
    out = NL.join(lines)
    if MARK not in out:
        fail('marker missing', TM, lines, si)
    if balance(out) != bal0:
        fail('balance changed', TM, lines, si)
    (ROOT / TM).write_text(out, encoding='utf-8')
    print('batch148: TavernModeStore OK')
else:
    print('batch148: TavernModeStore already applied')

# ---- 2. ReasoningPicker.kt 加开关 ----
rp = (ROOT / RP).read_text(encoding='utf-8')
if MARK not in rp:
    lines = rp.split(NL)
    bal0 = balance(rp)
    hits = [i for i, ln in enumerate(lines) if 'rhTavernMove' in ln]
    if len(hits) != 1:
        fail('rhTavernMove anchor count=' + str(len(hits)), RP, lines, hits[0] if hits else 0)
    ti = hits[0]
    depth = 0
    end = -1
    for j in range(ti, len(lines)):
        depth += lines[j].count('{') - lines[j].count('}')
        if depth == 0 and j > ti:
            end = j
            break
    if end < 0:
        fail('tavern switch block closing not found', RP, lines, ti)
    d = ind(lines[ti])
    new_switch = [
        '',
        d + '// ' + MARK + ': 榨干 token 开关(会话级,自动续跑)',
        d + 'if (onUpdateSqueezeToken != null) {',
        d + '    Row(',
        d + '        modifier = Modifier.fillMaxWidth(),',
        d + '        verticalAlignment = Alignment.CenterVertically,',
        d + '        horizontalArrangement = Arrangement.SpaceBetween,',
        d + '    ) {',
        d + '        Column(modifier = Modifier.weight(1f)) {',
        d + '            Text(',
        d + '                text = ' + Q + '榨干 token' + Q + ',',
        d + '                style = MaterialTheme.typography.titleSmall,',
        d + '            )',
        d + '            Text(',
        d + '                text = ' + Q + '模型结束时自动发送提示词继续生成' + Q + ',',
        d + '                style = MaterialTheme.typography.bodySmall,',
        d + '                color = MaterialTheme.colorScheme.onSurfaceVariant,',
        d + '            )',
        d + '        }',
        d + '        Switch(',
        d + '            checked = squeezeTokenEnabled,',
        d + '            onCheckedChange = { onUpdateSqueezeToken?.invoke(it) },',
        d + '        )',
        d + '    }',
        d + '}',
    ]
    for j, b in enumerate(new_switch):
        lines.insert(end + 1 + j, b)
    out = NL.join(lines)
    if MARK not in out:
        fail('marker missing', RP, lines, ti)
    if balance(out) != bal0:
        fail('balance changed', RP, lines, ti)
    (ROOT / RP).write_text(out, encoding='utf-8')
    print('batch148: ReasoningPicker OK')
else:
    print('batch148: ReasoningPicker already applied')

print('batch148: OK')

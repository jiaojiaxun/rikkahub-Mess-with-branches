#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch162: 榨干 token 功能(warn-only)——思考深度面板加开关(会话级,自动续跑)

用户需求:在发送框的思考深度里加开关(名字叫"榨干 token"),模型结束时自动发送提示词,
直到用户手动停止。和酒馆模式开关一个逻辑(会话级),对单个对话生效。

改动:
1. TavernModeStore.kt 加 squeezeTokenEnabled 字段(会话级存储)
2. ReasoningPicker.kt 加开关(和酒馆模式开关并列)

自动续跑逻辑(ChatService)在下一批处理。
warn-only: 任何锚点失败只 ::warning + 跳过,不阻塞构建(多人协作)。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhSqueezeToken'
TM = 'app/src/main/java/me/rerere/rikkahub/data/datastore/TavernModeStore.kt'
RP = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ReasoningPicker.kt'


def warn(msg, path):
    print('::warning file=' + path + '::batch162 ' + str(msg)[:1200])


def skip(msg, path):
    warn(msg + ' — skipped (warn-only)', path)
    sys.stdout.flush()
    sys.exit(0)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


# ---- 1. TavernModeStore.kt 加 squeezeTokenEnabled ----
try:
    tm = (ROOT / TM).read_text(encoding='utf-8')
except Exception as e:
    skip('read TavernModeStore failed: ' + str(e), TM)

if MARK in tm:
    print('batch162: TavernModeStore already applied')
else:
    lines = tm.split(NL)
    bal0 = balance(tm)
    hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('fun setEnabled(')]
    if len(hits) != 1:
        skip('setEnabled anchor count=' + str(len(hits)), TM)
    si = hits[0]
    depth = 0
    end = -1
    for j in range(si, len(lines)):
        depth += lines[j].count('{') - lines[j].count('}')
        if depth == 0 and j > si:
            end = j
            break
    if end < 0:
        skip('setEnabled closing brace not found', TM)
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
    if MARK not in out or balance(out) != bal0:
        skip('selfcheck failed', TM)
    (ROOT / TM).write_text(out, encoding='utf-8')
    print('batch162: TavernModeStore OK')

# ---- 2. ReasoningPicker.kt 加开关 ----
try:
    rp = (ROOT / RP).read_text(encoding='utf-8')
except Exception as e:
    skip('read ReasoningPicker failed: ' + str(e), RP)

if MARK in rp:
    print('batch162: ReasoningPicker already applied')
else:
    lines = rp.split(NL)
    bal0 = balance(rp)
    hits = [i for i, ln in enumerate(lines) if 'rhTavernBelowDivider' in ln or 'rhTavernMove' in ln]
    if len(hits) != 1:
        skip('tavern switch anchor count=' + str(len(hits)), RP)
    ti = hits[0]
    depth = 0
    end = -1
    for j in range(ti, len(lines)):
        depth += lines[j].count('{') - lines[j].count('}')
        if depth == 0 and j > ti:
            end = j
            break
    if end < 0:
        skip('tavern switch block closing not found', RP)
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
    if MARK not in out or balance(out) != bal0:
        skip('selfcheck failed', RP)
    (ROOT / RP).write_text(out, encoding='utf-8')
    print('batch162: ReasoningPicker OK')

print('batch162: OK')

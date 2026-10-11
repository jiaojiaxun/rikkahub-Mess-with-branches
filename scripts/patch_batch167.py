#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch167: 榨干 token 接线补全(warn-only)

问题: batch162/batch164 只加了 TavernModeStore 字段 + ReasoningPicker 开关 UI + 签名参数,
但没改 ChatInputState/ChatVM/ChatInput 三个接线文件——onUpdateSqueezeToken 永远是 null,
开关不显示(死功能)。

修法(参考 batch130 酒馆模式的接线方式):
1. ChatInputState.kt: 加 squeezeTokenEnabled 状态 + 回调(在 tavernMode 声明后)
2. ChatVM.kt: init 里读取状态 + setSqueezeTokenMode 函数
3. ChatInput.kt: ReasoningButton 调用传参(在 reasoningLevel 参数前)

warn-only: 任何锚点失败只 ::warning + 跳过,不阻塞构建(多人协作)。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
D = chr(34)
MARK = 'rhSqueezeWire'
IS = 'app/src/main/java/me/rerere/rikkahub/ui/hooks/ChatInputState.kt'
VM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatVM.kt'
CI = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ChatInput.kt'


def warn(msg, path):
    print('::warning file=' + path + '::batch167 ' + str(msg)[:1200])


def skip(msg, path):
    warn(msg + ' — skipped (warn-only)', path)
    sys.stdout.flush()
    sys.exit(0)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


# ---- 1. ChatInputState.kt: 加 squeezeToken 状态 ----
try:
    ist = (ROOT / IS).read_text(encoding='utf-8')
except Exception as e:
    skip('read ChatInputState failed: ' + str(e), IS)

if MARK in ist:
    print('batch167: ChatInputState already applied')
else:
    lines = ist.split(NL)
    bal0 = balance(ist)
    hits = [i for i, ln in enumerate(lines) if 'var tavernMode by mutableStateOf(false)' in ln]
    if len(hits) != 1:
        skip('tavernMode anchor count=' + str(len(hits)), IS)
    si = hits[0]
    d = ind(lines[si])
    block = [
        d + '// ' + MARK + ': 榨干 token 状态(会话级,由 ChatVM 注入)',
        d + 'var squeezeTokenEnabled by mutableStateOf(false)',
        d + 'var onToggleSqueezeToken: ((Boolean) -> Unit)? = null',
    ]
    for j, b in enumerate(block):
        lines.insert(si + 1 + j, b)
    out = NL.join(lines)
    if MARK not in out or balance(out) != bal0:
        skip('ChatInputState selfcheck failed', IS)
    (ROOT / IS).write_text(out, encoding='utf-8')
    print('batch167: ChatInputState OK')

# ---- 2. ChatVM.kt: init 接线 + setter ----
try:
    vm = (ROOT / VM).read_text(encoding='utf-8')
except Exception as e:
    skip('read ChatVM failed: ' + str(e), VM)

if MARK in vm:
    print('batch167: ChatVM already applied')
else:
    lines = vm.split(NL)
    bal0 = balance(vm)
    changed = 0

    # 2a. init 接线(锚点: batch130 加的 onToggleTavernMode 行)
    hits = [i for i, ln in enumerate(lines) if 'inputState.onToggleTavernMode = { enabled -> setTavernMode(enabled) }' in ln]
    if len(hits) != 1:
        skip('onToggleTavernMode anchor count=' + str(len(hits)), VM)
    si = hits[0]
    d = ind(lines[si])
    block = [
        d + '// ' + MARK + ': 榨干 token 接线(会话级)',
        d + 'inputState.squeezeTokenEnabled = me.rerere.rikkahub.data.datastore.TavernModeStore.isSqueezeTokenEnabled(context, _conversationId.toString())',
        d + 'inputState.onToggleSqueezeToken = { enabled -> setSqueezeTokenMode(enabled) }',
    ]
    for j, b in enumerate(block):
        lines.insert(si + 1 + j, b)
    changed += 1

    # 2b. setSqueezeTokenMode 函数(锚点: setTavernMode 函数块后)
    hits = [i for i, ln in enumerate(lines) if 'fun setTavernMode(enabled: Boolean) {' in ln]
    if len(hits) != 1:
        skip('setTavernMode anchor count=' + str(len(hits)), VM)
    ti = hits[0]
    depth = 0
    end = -1
    for j in range(ti, len(lines)):
        depth += lines[j].count('{') - lines[j].count('}')
        if depth == 0 and j > ti:
            end = j
            break
    if end < 0:
        skip('setTavernMode closing not found', VM)
    fblock = [
        '',
        '    /** ' + MARK + ': 榨干 token 开关(会话级,自动续跑)。 */',
        '    fun setSqueezeTokenMode(enabled: Boolean) {',
        '        inputState.squeezeTokenEnabled = enabled',
        '        me.rerere.rikkahub.data.datastore.TavernModeStore.setSqueezeTokenEnabled(context, _conversationId.toString(), enabled)',
        '    }',
    ]
    for j, b in enumerate(fblock):
        lines.insert(end + 1 + j, b)
    changed += 1

    out = NL.join(lines)
    for need in [MARK, 'setSqueezeTokenMode(enabled: Boolean)', 'isSqueezeTokenEnabled']:
        if need not in out:
            skip('ChatVM selfcheck missing: ' + need, VM)
    if balance(out) != bal0:
        skip('ChatVM balance changed', VM)
    (ROOT / VM).write_text(out, encoding='utf-8')
    print('batch167: ChatVM OK (' + str(changed) + ' changes)')

# ---- 3. ChatInput.kt: ReasoningButton 传参 ----
try:
    ci = (ROOT / CI).read_text(encoding='utf-8')
except Exception as e:
    skip('read ChatInput failed: ' + str(e), CI)

if MARK in ci:
    print('batch167: ChatInput already applied')
else:
    lines = ci.split(NL)
    bal0 = balance(ci)
    hits = [i for i, ln in enumerate(lines) if ln.strip() == 'reasoningLevel = assistant.reasoningLevel,']
    if len(hits) != 1:
        skip('reasoningLevel anchor count=' + str(len(hits)), CI)
    si = hits[0]
    d = ind(lines[si])
    block = [
        d + 'squeezeTokenEnabled = state.squeezeTokenEnabled, // ' + MARK,
        d + 'onUpdateSqueezeToken = state.onToggleSqueezeToken, // ' + MARK,
    ]
    for j, b in enumerate(block):
        lines.insert(si + j, b)
    out = NL.join(lines)
    if MARK not in out or balance(out) != bal0:
        skip('ChatInput selfcheck failed', CI)
    (ROOT / CI).write_text(out, encoding='utf-8')
    print('batch167: ChatInput OK')

print('batch167: OK')

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch232: A3 —— ChatService 接线：会话级配置接管读助手/选模型（全局换旧分辨率链）

A 移植第三批(用户已定方案①合并: 会话级模型并进 ConversationConfig, 收编旧字段)。
上游接法: 读助手=settings.getAssistantOf(conversation), 选模型=settings.getChatModelOf(conversation)。
fork 旧链(多处出现): 读助手=settings.getAssistantById(X.assistantId) ?: settings.getCurrentAssistant(),
  选模型=settings.findModelById(X.chatModelId ?: assistant.chatModelId ?: settings.chatModelId)。

本批对 ChatService.kt 做全局替换(X ∈ conversation/initialConversation/currentConversation):
  1. getAssistantById 链 → getAssistantOf(X)
  2. findModelById 链 → getChatModelOf(X)
  3. import 区补 getAssistantOf + getChatModelOf(锚 import ...data.model.Conversation 之后)
报告替换处数(走 ::error, 不占 warning 配额)。幂等 marker rhA3Wiring。warn-only。

注意: 只动 ChatService.kt。ChatVM/UI 的选择器写入侧在 A4。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch232'
MARK = 'rhA3Wiring'
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'

applied = []
skipped = []


def joinlist(items):
    t = ''
    for i, s in enumerate(items):
        if i > 0:
            t += ','
        t += s
    return t


def read(path):
    p = ROOT / path
    if not p.exists():
        return None
    try:
        return p.read_text(encoding='utf-8')
    except Exception:
        return None


def write(path, text):
    p = ROOT / path
    if not p.parent.exists():
        p.parent.mkdir(parents=True)
    p.write_text(text, encoding='utf-8')


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def main():
    src = read(CS)
    if src is None:
        skipped.append('missing')
        print('::error::' + BATCH + ' SKIP missing')
        return
    if MARK in src:
        applied.append('exists')
        print('::error::' + BATCH + ' OK already')
        return
    bal0 = balance(src)
    out = src

    # ① import 补 getAssistantOf + getChatModelOf
    imp_anchor = 'import me.rerere.rikkahub.data.model.Conversation\n'
    if out.count(imp_anchor) == 1:
        out = out.replace(
            imp_anchor,
            imp_anchor +
            'import me.rerere.rikkahub.data.model.getAssistantOf // ' + MARK + NL +
            'import me.rerere.rikkahub.data.model.getChatModelOf // ' + MARK,
            1,
        )
        applied.append('imports')
    else:
        skipped.append('import-anchor=' + str(out.count(imp_anchor)))

    # ② 读助手链 → getAssistantOf(X)
    n_assistant = 0
    for var in ('initialConversation', 'currentConversation', 'conversation'):
        old = 'settings.getAssistantById(' + var + '.assistantId) ?: settings.getCurrentAssistant()'
        new = 'settings.getAssistantOf(' + var + ') // ' + MARK
        n_assistant += out.count(old)
        out = out.replace(old, new)
    if n_assistant > 0:
        applied.append('assistant x' + str(n_assistant))
    else:
        skipped.append('assistant-none')

    # ③ 选模型链 → getChatModelOf(X)
    n_model = 0
    for var in ('initialConversation', 'currentConversation', 'conversation'):
        old = 'settings.findModelById(' + var + '.chatModelId ?: assistant.chatModelId ?: settings.chatModelId)'
        new = 'settings.getChatModelOf(' + var + ') // ' + MARK
        n_model += out.count(old)
        out = out.replace(old, new)
    if n_model > 0:
        applied.append('model x' + str(n_model))
    else:
        skipped.append('model-none')

    # ④ 校验 + 落盘
    if balance(out) != bal0:
        skipped.append('balance')
        print('::error::' + BATCH + ' SKIP balance')
        return
    if n_assistant == 0 and n_model == 0:
        skipped.append('no-op')
        print('::error::' + BATCH + ' SKIP no-op (0 replacements)')
        return
    write(CS, out)
    print('::error::' + BATCH + ' OK applied=[' + joinlist(applied) + '] skipped=[' + joinlist(skipped) + ']')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::error::' + BATCH + ' crashed: ' + str(exc)[:300])
    sys.exit(0)
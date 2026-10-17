#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch231: A3 接线侦察（只读）—— 列出 ChatService + ChatVM 里所有"读助手/选模型"的点

A3 要把 fork 的 `getAssistantById(conversation.assistantId) ?: getCurrentAssistant()`
+ `findModelById(conversation.chatModelId ?: assistant.chatModelId ?: settings.chatModelId)`
全部换成 getAssistantOf/getChatModelOf。本批只清点所有落点(行号+内容), 不改代码。

扫描: ChatService.kt + ChatVM.kt 里
  - 含 'getAssistantById' 的行
  - 含 'getCurrentAssistant()' 的行
  - 含 'chatModelId' 的行
  - 含 'getChatModelOf' / 'getAssistantOf' 的行(确认上游新法是否已出现)
走 ::error(不占 warning 配额)。纯只读, exit 0。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch231'
FILES = (
    'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt',
    'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatVM.kt',
)
PATTERNS = (
    ('getAssistantById', 'getAssistantById'),
    ('getCurrentAssistant', 'getCurrentAssistant()'),
    ('chatModelId', 'chatModelId'),
    ('getChatModelOf', 'getChatModelOf'),
    ('getAssistantOf', 'getAssistantOf'),
)


def read(path):
    p = ROOT / path
    if not p.exists():
        return None
    try:
        return p.read_text(encoding='utf-8')
    except Exception:
        return None


def main():
    for path in FILES:
        src = read(path)
        name = path.split('/')[-1]
        if src is None:
            print('::error::' + BATCH + ' ' + name + ' MISSING')
            continue
        lines = src.split(NL)
        for label, needle in PATTERNS:
            hits = [(i + 1, lines[i].strip()[:90]) for i, ln in enumerate(lines) if needle in ln]
            if not hits:
                continue
            for ln_num, text in hits:
                print('::error::' + BATCH + ' ' + name + ':' + str(ln_num) + ' [' + label + '] ' + text)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::error::' + BATCH + ' crashed: ' + str(exc)[:300])
    sys.exit(0)
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch222: 死功能审查第一批 —— 引用功能 + 通知工具 + 顶栏玻璃（只读清点，走 ::error 通道）

背景: 引用功能装机反馈「看不到也没 UI」。batch68 的菜单项是 if (onQuote != null) Card,
      onQuote 默认 null, 靠 ChatPage → ChatList → ChatMessage 逐层转发 —— 与榨干 token
      断链同型: 任何一环没传参, 菜单永远隐藏。本批只清点各文件的引用标记位计数,
      用来定位断在哪一环。通知工具(batch87 曾把注册行绑进 Toast 开关, batch96 修过)顺带复验。

通道: ::warning 已被 10/步配额挤满, 改用 ::error(空通道)。不是错误, 只是露出。
纯只读, 不写文件, exit 0。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
BATCH = 'batch222'

CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
LT = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt'
AP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/detail/AssistantLocalToolPage.kt'
CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
CMA = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageActions.kt'
NT = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/local/NotificationTool.kt'

# (label, path, [needles...])  —— 计数 "a+b"
CHECKS = (
    ('svc-quoteId', CS, ['quotedMessageId']),
    ('page-quoting', CP, ['quotingMessage']),
    ('page-onQuote', CP, ['onQuote']),
    ('page-topbar', CP, ['rhTopBar']),
    ('list-onQuote', CL, ['onQuote']),
    ('list-QuoteBlock', CL, ['QuoteBlock']),
    ('msg-onQuote', CM, ['onQuote']),
    ('act-onQuote', CMA, ['onQuote']),
    ('lt-notifTool', LT, ['notificationTool']),
    ('lt-notifEnum', LT, ['LocalToolOption.Notification']),
    ('ap-notifRow', AP, ['rhNotifSwitch']),
    ('ap-notifEnum', AP, ['LocalToolOption.Notification']),
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
    parts = []
    for label, path, needles in CHECKS:
        src = read(path)
        if src is None:
            parts.append(label + '=NOFILE')
            continue
        counts = []
        for n in needles:
            counts.append(str(src.count(n)))
        parts.append(label + '=' + '+'.join(counts))
    # 通知工具文件存在性
    parts.append('notif-file=' + ('yes' if (ROOT / NT).exists() else 'NO'))
    line = BATCH + '-AUDIT ' + ' '.join(parts)
    print('::error::' + line[:1900])
    print(line[:1900])


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::error::' + BATCH + ' crashed: ' + str(exc)[:300])
    sys.exit(0)
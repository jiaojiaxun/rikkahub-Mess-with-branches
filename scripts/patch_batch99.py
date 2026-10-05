#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch99 v3: 修 v2 的 Unresolved reference 'ChatNotificationManager'

v2 死因:RikkaHubApp.kt 在 me.rerere.rikkahub 包,ChatNotificationManager 在
me.rerere.rikkahub.service 子包 → 需要 import,v2 漏了。
v3 = v2 + 加 import 行(锚 WebServerService import 后,同 service 包)。

每次 CI fresh checkout 重跑,所以 v3 处理原始态(不需要处理 v1/v2 残留)。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhNotifMgr'
RA = 'app/src/main/java/me/rerere/rikkahub/RikkaHubApp.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch99v3 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + RA + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


t = (ROOT / RA).read_text(encoding='utf-8')
if MARK in t:
    print('batch99v3: already applied')
else:
    lines = t.split(NL)
    applied = []

    # 0. 加 import ChatNotificationManager(锚 WebServerService import 后)
    has_import = any(ln.strip() == 'import me.rerere.rikkahub.service.ChatNotificationManager' for ln in lines)
    if not has_import:
        hits = [i for i, ln in enumerate(lines) if ln.strip() == 'import me.rerere.rikkahub.service.WebServerService']
        if len(hits) != 1:
            fail('WebServerService import anchor count=' + str(len(hits)))
        lines.insert(hits[0] + 1, 'import me.rerere.rikkahub.service.ChatNotificationManager')
        applied.append('import')

    # A. 常量
    CONST_ANCHOR = 'const val POMODORO_NOTIFICATION_CHANNEL_ID = ' + Q + 'plugin_pomodoro' + Q
    hits = [i for i, ln in enumerate(lines) if ln.strip() == CONST_ANCHOR]
    if len(hits) != 1:
        fail('POMODORO const anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ci = hits[0]
    d = ind(lines[ci])
    lines.insert(ci + 1, d + 'const val CHAT_COMPLETED_NOTIFICATION_CHANNEL_ID = ' + Q + 'chat_completed' + Q + ' // ' + MARK)
    applied.append('const')

    # B. 渠道
    CH_END = 'notificationManager.createNotificationChannel(pluginPomodoroChannel)'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == CH_END]
    if len(hits) != 1:
        fail('pomodoro channel anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    chi = hits[0]
    d = ind(lines[chi])
    ch_block = [
        d + '',
        d + '// ' + MARK + ' (batch99): 生成完成通知渠道',
        d + 'val chatCompletedChannel = NotificationChannelCompat',
        d + '    .Builder(CHAT_COMPLETED_NOTIFICATION_CHANNEL_ID, NotificationManagerCompat.IMPORTANCE_DEFAULT)',
        d + '    .setName(getString(R.string.notification_channel_chat_live_update))',
        d + '    .setVibrationEnabled(true)',
        d + '    .build()',
        d + 'notificationManager.createNotificationChannel(chatCompletedChannel)',
    ]
    lines[chi + 1:chi + 1] = ch_block
    applied.append('channel')

    # C. 初始化(显式 get() 类型参数)
    INIT_ANCHOR = 'eagerlyInitChatService()'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == INIT_ANCHOR]
    if len(hits) != 1:
        fail('eagerlyInitChatService anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ii = hits[0]
    d = ind(lines[ii])
    init_block = [
        d + 'ChatNotificationManager(',
        d + '    this,',
        d + '    get<me.rerere.rikkahub.AppScope>(),',
        d + '    get<me.rerere.rikkahub.data.event.AppEventBus>(),',
        d + '    get<me.rerere.rikkahub.data.datastore.SettingsStore>()',
        d + ') // ' + MARK + ' (batch99v3)',
    ]
    lines[ii + 1:ii + 1] = init_block
    applied.append('init')

    out = NL.join(lines)
    for need in [MARK, 'CHAT_COMPLETED_NOTIFICATION_CHANNEL_ID', 'ChatNotificationManager(',
                 'import me.rerere.rikkahub.service.ChatNotificationManager']:
        if need not in out:
            fail('selfcheck missing: ' + need)

    (ROOT / RA).write_text(out, encoding='utf-8')
    print('batch99v3: OK (' + ', '.join(applied) + ')')

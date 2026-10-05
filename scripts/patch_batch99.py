#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch99 v2: 修 v1 的 get() 类型推断失败

v1(c4e9522)死因:Unresolved reference 'ChatNotificationManager' + Cannot infer type for type parameter 'T'。
Koin 的 get() 是 inline reified T,Kotlin 编译器不能从构造函数参数推断 T。
v2:每个 get() 都加显式类型参数。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhNotifMgr'
RA = 'app/src/main/java/me/rerere/rikkahub/RikkaHubApp.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch99v2 ' + str(msg)
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
    # v1 已应用但编译失败,需要替换 init 行
    lines = t.split(NL)
    OLD_INIT = 'ChatNotificationManager(this, get(), get<me.rerere.rikkahub.data.event.AppEventBus>(), get())'
    hits = [i for i, ln in enumerate(lines) if OLD_INIT in ln]
    if len(hits) == 1:
        d = ind(lines[hits[0]])
        lines[hits[0]] = (
            d + 'ChatNotificationManager(' + NL +
            d + '    this,' + NL +
            d + '    get<me.rerere.rikkahub.AppScope>(),' + NL +
            d + '    get<me.rerere.rikkahub.data.event.AppEventBus>(),' + NL +
            d + '    get<me.rerere.rikkahub.data.datastore.SettingsStore>()' + NL +
            d + ') // ' + MARK + ' (batch99v2)'
        )
        out = NL.join(lines)
        (ROOT / RA).write_text(out, encoding='utf-8')
        print('batch99v2: init line fixed (explicit type params)')
    else:
        fail('v1 init line count=' + str(len(hits)))
else:
    # v1 未应用(fresh checkout),完整应用
    lines = t.split(NL)
    applied = []

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

    # C. 初始化(v2:每个 get() 显式类型参数)
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
        d + ') // ' + MARK + ' (batch99v2)',
    ]
    lines[ii + 1:ii + 1] = init_block
    applied.append('init')

    out = NL.join(lines)
    for need in [MARK, 'CHAT_COMPLETED_NOTIFICATION_CHANNEL_ID', 'ChatNotificationManager(']:
        if need not in out:
            fail('selfcheck missing: ' + need)

    (ROOT / RA).write_text(out, encoding='utf-8')
    print('batch99v2: OK (' + ', '.join(applied) + ')')

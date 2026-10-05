#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch99: 接入 ChatNotificationManager —— 补常量+渠道+初始化

fork 缺 ChatNotificationManager.kt 和 NotificationUtil.kt(已直接推送)。
本 patch 改 RikkaHubApp.kt:
  A. 加 CHAT_COMPLETED_NOTIFICATION_CHANNEL_ID 常量
  B. createNotificationChannel() 加 chat_completed 渠道(IMPORTANCE_DEFAULT)
  C. onCreate 加 ChatNotificationManager 初始化

五查:
1. import:零新增(ChatNotificationManager 同包 me.rerere.rikkahub.service;
   AppEventBus 用全限定名;AppScope/SettingsStore 已 import)
2. 同文件冲突:RikkaHubApp.kt 无在链 patch 碰过
3. 作用域:常量在文件顶层;渠道在 createNotificationChannel() 内;初始化在 onCreate() 内
4. 括号配对:渠道创建自平衡;初始化单行
5. 函数签名:不改
Python 三查:Q=chr(34)/NL 手写/helper 先定义/失败 exit(1)
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhNotifMgr'
RA = 'app/src/main/java/me/rerere/rikkahub/RikkaHubApp.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch99 ' + str(msg)
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
    print('batch99: already applied')
else:
    lines = t.split(NL)
    applied = []

    # A. 加常量(锚 POMODORO 常量行后)
    CONST_ANCHOR = 'const val POMODORO_NOTIFICATION_CHANNEL_ID = ' + Q + 'plugin_pomodoro' + Q
    hits = [i for i, ln in enumerate(lines) if ln.strip() == CONST_ANCHOR]
    if len(hits) != 1:
        fail('POMODORO const anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ci = hits[0]
    d = ind(lines[ci])
    lines.insert(ci + 1, d + 'const val CHAT_COMPLETED_NOTIFICATION_CHANNEL_ID = ' + Q + 'chat_completed' + Q + ' // ' + MARK)
    applied.append('const')

    # B. 加渠道(锚 pomodoro 渠道创建行后)
    CH_END = 'notificationManager.createNotificationChannel(pluginPomodoroChannel)'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == CH_END]
    if len(hits) != 1:
        fail('pomodoro channel create anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
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

    # C. 初始化 ChatNotificationManager(锚 eagerlyInitChatService() 调用行后)
    INIT_ANCHOR = 'eagerlyInitChatService()'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == INIT_ANCHOR]
    if len(hits) != 1:
        fail('eagerlyInitChatService call anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ii = hits[0]
    d = ind(lines[ii])
    lines.insert(ii + 1, d + 'ChatNotificationManager(this, get(), get<me.rerere.rikkahub.data.event.AppEventBus>(), get()) // ' + MARK)
    applied.append('init')

    out = NL.join(lines)
    for need in [MARK, 'CHAT_COMPLETED_NOTIFICATION_CHANNEL_ID', 'ChatNotificationManager(this']:
        if need not in out:
            fail('selfcheck missing: ' + need)

    (ROOT / RA).write_text(out, encoding='utf-8')
    print('batch99: OK (' + ', '.join(applied) + ')')

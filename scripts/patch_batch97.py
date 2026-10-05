#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch97: 修复所有通知不显示 —— App 从未请求 POST_NOTIFICATIONS 运行时权限

【根因】(实读 RikkaHubApp.kt + RouteActivity.kt 确证)
  - RikkaHubApp.onCreate 只调了 createNotificationChannel()（创建渠道）
  - RouteActivity.onCreate 没有请求 POST_NOTIFICATIONS 运行时权限
  - Android 13+(API 33+) 要求运行时请求用户授权 POST_NOTIFICATIONS
  - 没请求 → 所有通知被系统静默丢弃（nm.notify 无效，不崩但不可见）
  → 影响：App 的所有通知功能都不显示（完成通知/流式Live Update/前台服务通知/send_notification工具）

【修法】在 RouteActivity.onCreate 的 super.onCreate() 之后插入权限请求：
  if (SDK >= 33 && 未授权) requestPermissions(POST_NOTIFICATIONS)
  全限定名，零 import 新增。

五查:
1. import:零新增（android.os.Build/androidx.core.content.ContextCompat/android.Manifest/
   android.content.pm.PackageManager 全用全限定名）
2. 同文件冲突:RouteActivity.kt 无在链 patch 碰过（patch 列表已核查）
3. 作用域:onCreate 函数体内
4. 括号配对:if() {} 块自平衡
5. 函数签名:不改
Python 三查:无引号字面量 / NL 手写 concat / helper 先定义后用 / 失败显式 exit(1)
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhNotifPerm'
RA = 'app/src/main/java/me/rerere/rikkahub/RouteActivity.kt'


def fail(path, msg, lines=None, around=-1):
    body = 'batch97 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + path + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


ra = (ROOT / RA).read_text(encoding='utf-8')
if MARK in ra:
    print('batch97: already applied')
else:
    bal0 = balance(ra)
    lines = ra.split(NL)

    # 锚点 = super.onCreate(savedInstanceState) 行(onCreate 内唯一)
    ANCHOR = 'super.onCreate(savedInstanceState)'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == ANCHOR]
    if len(hits) != 1:
        fail(RA, 'super.onCreate anchor count=' + str(len(hits)), lines,
             hits[0] if hits else 0)
    i = hits[0]
    d = ind(lines[i])

    # 确认下一行是 CrashHandler 检查(验证锚点位置正确)
    if 'CrashHandler.hasCrashed' not in lines[i + 1]:
        fail(RA, 'line after super.onCreate is not CrashHandler check', lines, i + 1)

    block = [
        d + '// ' + MARK + ' (batch97): Android 13+ 需运行时请求通知权限,否则所有通知被静默丢弃',
        d + 'if (android.os.Build.VERSION.SDK_INT >= 33 &&',
        d + '    androidx.core.content.ContextCompat.checkSelfPermission(',
        d + '        this, android.Manifest.permission.POST_NOTIFICATIONS',
        d + '    ) != android.content.pm.PackageManager.PERMISSION_GRANTED',
        d + ') {',
        d + '    requestPermissions(arrayOf(android.Manifest.permission.POST_NOTIFICATIONS), 1001)',
        d + '}',
    ]
    lines[i + 1:i + 1] = block
    out = NL.join(lines)

    for need in [MARK, 'POST_NOTIFICATIONS', 'requestPermissions']:
        if need not in out:
            fail(RA, 'selfcheck missing: ' + need, lines, i)
    if balance(out) != bal0:
        fail(RA, 'bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

    (ROOT / RA).write_text(out, encoding='utf-8')
    print('batch97: OK (POST_NOTIFICATIONS runtime request added to RouteActivity.onCreate)')

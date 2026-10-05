#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
batch87 v2: 注册 send_notification —— 修 #245 自检串带 indent

#245 根因：自检 `ln.strip() == NEW_REG` 比较，但 NEW_REG 包含 indent（d 前缀），
  而 ln.strip() 去掉了 indent → 永远不匹配 → "registration read-back failed"
  与 #236 同类：自检串与插入串构造不一致。

v2 修法：自检一律用 ln.strip() == NEW_REG.strip()（铁律 33 思想：比较对齐）。
  其余逻辑与 v1 完全一致。

五查（与 v1 一致）：
1. import：notificationTool 同包，需 import 行（锚 toastTool import）
2. 同文件冲突：LocalTools.kt 被多批碰过，锚点在不重叠区
3. 作用域：enum 在 sealed class 内；注册在 getTools 内
4. 括号配对：enum 行自闭合；注册行单行
5. 函数签名：不改

Python 三查：引号变量 / helper 先定义 / 无 f-string
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhSendNotification'
Q = chr(34)

LT = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt'


def fail(msg, dump_text=''):
    body = str(msg)[:800]
    if dump_text:
        body = body + ' || DUMP: ' + str(dump_text)[:1500]
    print('::error file=' + LT + '::batch87v2 ' + body)
    sys.stdout.flush()
    sys.exit(1)


def concat(lines):
    t = ''
    for i, ln in enumerate(lines):
        if i > 0:
            t += NL
        t += ln
    return t


def dump_str(lines, lo, hi):
    out = []
    for i in range(max(0, lo), min(hi, len(lines))):
        out.append('L' + str(i + 1) + ':' + lines[i].strip()[:90])
    return ' | '.join(out)


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


t = (ROOT / LT).read_text(encoding='utf-8')
if MARK in t:
    print('batch87v2: already applied')
    sys.exit(0)

lines = t.split(NL)
bal0 = balance(t)
applied = []

# 1. import 行
IMP_ANCHOR = 'import me.rerere.rikkahub.data.ai.tools.local.toastTool'
hits = [i for i, ln in enumerate(lines) if ln.strip() == IMP_ANCHOR]
if len(hits) != 1:
    fail('toastTool import anchor count=' + str(len(hits)), dump_str(lines, 0, len(lines)))
NEW_IMP = 'import me.rerere.rikkahub.data.ai.tools.local.notificationTool // ' + MARK
lines.insert(hits[0] + 1, NEW_IMP)
if not any(ln.strip() == NEW_IMP.strip() for ln in lines):
    fail('import read-back failed')
applied.append('import')

# 2. LocalToolOption.Notification enum 项
ENUM_ANCHOR = '@Serializable @SerialName(' + Q + 'toast' + Q + ')          data object Toast          : LocalToolOption()'
hits = [i for i, ln in enumerate(lines) if ln.strip() == ENUM_ANCHOR]
if len(hits) != 1:
    hits = [i for i, ln in enumerate(lines)
            if 'SerialName(' in ln and Q + 'toast' + Q in ln and 'data object Toast' in ln]
if len(hits) != 1:
    fail('Toast enum anchor count=' + str(len(hits)), dump_str(lines, 0, len(lines)))
ei = hits[0]
NEW_ENUM = '@Serializable @SerialName(' + Q + 'notification' + Q + ') data object Notification : LocalToolOption() // ' + MARK
lines.insert(ei + 1, NEW_ENUM)
if not any(ln.strip() == NEW_ENUM.strip() for ln in lines):
    fail('enum read-back failed')
applied.append('enum')

# 3. getTools 注册（自检用 strip 对齐，铁律 33 思想）
REG_ANCHOR = 'tools.add(toastTool(context))'
hits = [i for i, ln in enumerate(lines) if ln.strip() == REG_ANCHOR]
if len(hits) != 1:
    fail('toastTool registration anchor count=' + str(len(hits)), dump_str(lines, 0, len(lines)))
ri = hits[0]
d = lines[ri][:len(lines[ri]) - len(lines[ri].lstrip())]
NEW_REG = d + 'tools.add(notificationTool(context)) // ' + MARK
lines.insert(ri + 1, NEW_REG)
if not any(ln.strip() == NEW_REG.strip() for ln in lines):
    fail('registration read-back failed', dump_str(lines, ri, ri + 5))
applied.append('register')

# 自检
t2 = concat(lines)
for need in [MARK,
             'import me.rerere.rikkahub.data.ai.tools.local.notificationTool',
             'data object Notification : LocalToolOption()',
             'tools.add(notificationTool(context))']:
    if need not in t2:
        fail('selfcheck missing: ' + need, dump_str(lines, 0, len(lines)))
if balance(t2) != bal0:
    fail('balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
toast_i = [i for i, ln in enumerate(lines) if 'data object Toast' in ln and 'LocalToolOption' in ln]
if not toast_i:
    fail('Toast enum lost')
sealed_found = any('sealed class LocalToolOption' in lines[i] for i in range(toast_i[0], -1, -1))
if not sealed_found:
    fail('Notification enum inserted outside sealed class')
notif_i = [i for i, ln in enumerate(lines) if 'notificationTool(context)' in ln and 'tools.add' in ln]
gettools_i = [i for i, ln in enumerate(lines) if 'fun getTools(' in ln]
if not notif_i or not gettools_i:
    fail('registration or getTools not found')
if notif_i[0] < gettools_i[0]:
    fail('registration before getTools')

(ROOT / LT).write_text(t2, encoding='utf-8')
print('batch87v2: OK (' + ', '.join(applied) + ')')

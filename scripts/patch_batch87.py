#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
batch87: 注册 send_notification 工具 + LocalToolOption.Notification enum 项

改动（3 处，全在 LocalTools.kt 单文件）：
1. import 行（锚：import ...local.toastTool  → 插其后）
2. LocalToolOption sealed class 内加 Notification 项
   （锚：@SerialName("toast") data object Toast : LocalToolOption() → 插其后）
3. getTools 函数内注册
   （锚：tools.add(toastTool(context))  → 插其后）

新文件 NotificationTool.kt 已在上一 commit 落地，本批只做注册。

五查：
1. import：notificationTool 来自同包（me.rerere.rikkahub.data.ai.tools.local）
   → 需加 import 行（锚 toastTool import，行级 strip 全等）
2. 同文件冲突：LocalTools.kt 被 batch55-4b/74/85/86b 碰过
   → 三个锚点都在【不与那些补丁重叠】的区域（enum 区 / getTools toast 行）
3. 作用域：enum 项在 sealed class 内；注册在 getTools 函数体内
4. 括号配对：enum 行自闭合（data object X : LocalToolOption()）；注册行单行
5. 函数签名：不改任何签名

铁律 20：import 行级 strip 全等 + 插入后回读
铁律 25：enum 项在 Toast 行之后（该行有尾逗号且是 sealed class 成员，无尾逗号问题）
铁律 30/31：dump 塞 ::error；失败显式 exit(1)

Python 三查：引号一律变量构造 / helper 先定义后用 / 无 f-string
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
    print('::error file=' + LT + '::batch87 ' + body)
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
    print('batch87: already applied')
    sys.exit(0)

lines = t.split(NL)
bal0 = balance(t)
applied = []

# -------------------------------------------------------------------------
# 1. import 行（锚：import ...local.toastTool，行级 strip 全等）
# -------------------------------------------------------------------------
IMP_ANCHOR = 'import me.rerere.rikkahub.data.ai.tools.local.toastTool'
hits = [i for i, ln in enumerate(lines) if ln.strip() == IMP_ANCHOR]
if len(hits) != 1:
    fail('toastTool import anchor count=' + str(len(hits)), dump_str(lines, 0, len(lines)))
NEW_IMP = 'import me.rerere.rikkahub.data.ai.tools.local.notificationTool // ' + MARK
lines.insert(hits[0] + 1, NEW_IMP)
if not any(ln.strip() == NEW_IMP for ln in lines):
    fail('import read-back failed')
applied.append('import')

# -------------------------------------------------------------------------
# 2. LocalToolOption.Notification enum 项
#    锚：@SerialName("toast")          data object Toast          : LocalToolOption()
#    （行级 strip 全等；插其后一行）
# -------------------------------------------------------------------------
ENUM_ANCHOR = '@Serializable @SerialName(' + Q + 'toast' + Q + ')          data object Toast          : LocalToolOption()'
hits = [i for i, ln in enumerate(lines) if ln.strip() == ENUM_ANCHOR]
if len(hits) != 1:
    # fallback: 逐行找含 'toast' SerialName 且含 data object Toast 的行
    hits = [i for i, ln in enumerate(lines)
            if 'SerialName(' in ln and Q + 'toast' + Q in ln and 'data object Toast' in ln]
if len(hits) != 1:
    fail('Toast enum anchor count=' + str(len(hits)), dump_str(lines, 0, len(lines)))
ei = hits[0]
NEW_ENUM = '@Serializable @SerialName(' + Q + 'notification' + Q + ') data object Notification : LocalToolOption() // ' + MARK
lines.insert(ei + 1, NEW_ENUM)
if not any(ln.strip() == NEW_ENUM for ln in lines):
    fail('enum read-back failed')
applied.append('enum')

# -------------------------------------------------------------------------
# 3. getTools 注册（锚：tools.add(toastTool(context))）
#    插其后一行
# -------------------------------------------------------------------------
REG_ANCHOR = 'tools.add(toastTool(context))'
hits = [i for i, ln in enumerate(lines) if ln.strip() == REG_ANCHOR]
if len(hits) != 1:
    fail('toastTool registration anchor count=' + str(len(hits)), dump_str(lines, 0, len(lines)))
ri = hits[0]
d = lines[ri][:len(lines[ri]) - len(lines[ri].lstrip())]
NEW_REG = d + 'tools.add(notificationTool(context)) // ' + MARK
lines.insert(ri + 1, NEW_REG)
if not any(ln.strip() == NEW_REG for ln in lines):
    fail('registration read-back failed')
applied.append('register')

# -------------------------------------------------------------------------
# 自检
# -------------------------------------------------------------------------
t2 = concat(lines)
for need in [MARK,
             'import me.rerere.rikkahub.data.ai.tools.local.notificationTool',
             'data object Notification : LocalToolOption()',
             'tools.add(notificationTool(context))']:
    if need not in t2:
        fail('selfcheck missing: ' + need, dump_str(lines, 0, len(lines)))
if balance(t2) != bal0:
    fail('balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
# 确认 enum 项在 sealed class 内（Toast 行之前必须有 sealed class 行）
toast_i = [i for i, ln in enumerate(lines) if 'data object Toast' in ln and 'LocalToolOption' in ln]
if not toast_i:
    fail('Toast enum lost')
sealed_found = False
for i in range(toast_i[0], -1, -1):
    if 'sealed class LocalToolOption' in lines[i]:
        sealed_found = True
        break
if not sealed_found:
    fail('Notification enum inserted outside sealed class')
# 确认注册在 getTools 内
notif_i = [i for i, ln in enumerate(lines) if 'notificationTool(context)' in ln and 'tools.add' in ln]
gettools_i = [i for i, ln in enumerate(lines) if 'fun getTools(' in ln]
if not notif_i or not gettools_i:
    fail('registration or getTools not found')
if notif_i[0] < gettools_i[0]:
    fail('registration before getTools')

(ROOT / LT).write_text(t2, encoding='utf-8')
print('batch87: OK (' + ', '.join(applied) + ')')

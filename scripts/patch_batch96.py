#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch96: 修复通知工具(send_notification)不可达 —— 注册移出 Toast 块 + UI 加开关行

【缺陷1】注册行绑在 Toast 开关内(实读 LocalTools.kt 确证)
  batch87 把 tools.add(notificationTool(context)) 插在 tools.add(toastTool(context)) 之后,
  而后者在 if (options.contains(LocalToolOption.Toast)) { 块内
  → 通知工具被 Toast 开关绑定:开 Toast 才有,关 Toast 就没有。
  修法:注册行移出 Toast 块,改成独立的 if (options.contains(LocalToolOption.Notification))。

【缺陷2】UI 设置页无 Notification 开关行(实读 AssistantLocalToolPage.kt 确证)
  该页硬编码每工具一行 Switch,patch_local_tool_page.py 注释明示
  "new enum entries are invisible until a row is added here"。
  修法:仿 Toast item 模式,在其后加 Notification item。
  标题/描述硬编码中文(与 patch_local_tool_page.py 的硬编码先例一致,零 strings.xml 改动)。

五查:
1. import:LocalTools.kt 零新增(notificationTool 的 import 由 batch87 已加);
   AssistantLocalToolPage.kt 零新增(PermissionedSwitch/Text/LocalToolOption 均已在,实读确认)
2. 同文件冲突:LocalTools.kt 被 batch87 碰过——本批锚点 = batch87 注入行本身
   (tools.add(notificationTool(context)) // rhSendNotification,唯一);
   AssistantLocalToolPage.kt 被 patch_local_tool_page.py 碰过(javascript_engine item 前插
   3 个 item,在 Built-in section)——本批锚点 = Toast 的 onCheckedChange 行(Output
   section),零重叠
3. 作用域:注册块在 getTools 函数体内;新 item 在 CardGroup item 区(与 Toast item 同级)
4. 括号配对:三行(toastTool/notif/})重写为五行,if 块自平衡;item 块自平衡
   插入前后全文括号差值必须不变
5. 函数签名:不改任何签名

Python 三查:引号 Q=chr(34) 构造 / NL=chr(10) 手写 concat / helper 先定义后用 /
失败显式 exit(1) 且 dump 塞 ::error message
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK_REG = 'rhNotifScope'
MARK_UI = 'rhNotifSwitch'
LT = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt'
AP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/detail/AssistantLocalToolPage.kt'


def fail(path, msg, lines=None, around=-1):
    body = 'batch96 ' + str(msg)
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


# ============================================================
# A. LocalTools.kt —— 注册移出 Toast 块
# ============================================================
lt = (ROOT / LT).read_text(encoding='utf-8')
if MARK_REG in lt:
    print('batch96: LocalTools already applied')
else:
    bal0 = balance(lt)
    lines = lt.split(NL)

    # 锚点 = batch87 注入行(带 MARK 注释,全文件唯一)
    OLD_NOTIF = 'tools.add(notificationTool(context)) // rhSendNotification'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == OLD_NOTIF]
    if len(hits) != 1:
        fail(LT, 'batch87 notif registration count=' + str(len(hits)), lines,
             hits[0] if hits else 0)
    ri = hits[0]

    # 形态断言:前一行 = toastTool 注册,后一行 = Toast if 块闭合 }
    if lines[ri - 1].strip() != 'tools.add(toastTool(context))':
        fail(LT, 'prev line is not toastTool registration', lines, ri - 1)
    if lines[ri + 1].strip() != '}':
        fail(LT, 'next line is not Toast block closing brace', lines, ri + 1)

    # 缩进:if 块闭合 } 的缩进 = if 行缩进
    d0 = ind(lines[ri + 1])
    new_block = [
        d0 + 'if (options.contains(LocalToolOption.Notification)) { // ' + MARK_REG + ' (batch96)',
        d0 + '    tools.add(notificationTool(context))',
        d0 + '}',
    ]
    # 重写:删除 batch87 注入行,在 } 之后插入独立 if 块
    lines = lines[:ri] + lines[ri + 1:ri + 2] + new_block + lines[ri + 2:]
    out = NL.join(lines)

    # 自检 1:新独立 if 块存在
    need_if = 'if (options.contains(LocalToolOption.Notification)) {'
    if need_if not in out:
        fail(LT, 'independent Notification gate missing')
    # 自检 2:toastTool 行的下一行必须是 }(不再夹着 notificationTool)
    ti = [i for i, ln in enumerate(lines) if ln.strip() == 'tools.add(toastTool(context))']
    if len(ti) != 1:
        fail(LT, 'toastTool registration count=' + str(len(ti)))
    if lines[ti[0] + 1].strip() != '}':
        fail(LT, 'toastTool still has notificationTool inside its block', lines, ti[0] + 1)
    # 自检 3:notificationTool 注册行唯一且缩进在新块内(+4)
    ni = [i for i, ln in enumerate(lines) if ln.strip() == 'tools.add(notificationTool(context))']
    if len(ni) != 1:
        fail(LT, 'notificationTool registration count=' + str(len(ni)))
    if ind(lines[ni[0]]) != d0 + '    ':
        fail(LT, 'notificationTool indent mismatch', lines, ni[0])
    # 自检 4:括号配平不变
    if balance(out) != bal0:
        fail(LT, 'bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

    (ROOT / LT).write_text(out, encoding='utf-8')
    print('batch96: LocalTools OK (registration moved to own gate)')


# ============================================================
# B. AssistantLocalToolPage.kt —— 加 Notification 开关行
# ============================================================
ap = (ROOT / AP).read_text(encoding='utf-8')
if MARK_UI in ap:
    print('batch96: AssistantLocalToolPage already applied')
else:
    bal0 = balance(ap)
    lines = ap.split(NL)

    # 锚点 = Toast 的 onCheckedChange 行(Output section,全文件唯一)
    OC_ANCHOR = 'onCheckedChange = { toggleLocalTool(LocalToolOption.Toast, it) }'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == OC_ANCHOR]
    if len(hits) != 1:
        fail(AP, 'Toast onCheckedChange anchor count=' + str(len(hits)), lines,
             hits[0] if hits else 0)
    oc = hits[0]

    # 形态断言:oc+1=)(PermissionedSwitch 闭合) oc+2=}(trailingContent 闭合) oc+3=)(item 闭合)
    if lines[oc + 1].strip() != ')':
        fail(AP, 'line after onCheckedChange is not PermissionedSwitch close', lines, oc + 1)
    if lines[oc + 2].strip() != '}':
        fail(AP, 'trailingContent close not found', lines, oc + 2)
    if lines[oc + 3].strip() != ')':
        fail(AP, 'item close not found', lines, oc + 3)

    # item 缩进 = 从 oc 往上找 item( 行(strip 全等;patch_local_tool_page 插的 item
    # 在 javascript_engine 区域,不在 15 行窗口内,零干扰)
    item_idx = -1
    for j in range(oc, max(oc - 15, -1), -1):
        if lines[j].strip() == 'item(':
            item_idx = j
            break
    if item_idx < 0:
        fail(AP, 'Toast item( not found above onCheckedChange', lines, oc)
    di = ind(lines[item_idx])

    # 新 item(仿 Toast 形态,硬编码中文)
    new_item = [
        di + 'item( // ' + MARK_UI + ' (batch96)',
        di + '    headlineContent = {',
        di + '        Text(' + Q + '系统通知' + Q + ')',
        di + '    },',
        di + '    supportingContent = {',
        di + '        Text(' + Q + '允许 AI 主动发送系统通知（状态栏提醒）' + Q + ')',
        di + '    },',
        di + '    trailingContent = {',
        di + '        PermissionedSwitch(',
        di + '            checked = assistant.localTools.contains(LocalToolOption.Notification),',
        di + '            onCheckedChange = { toggleLocalTool(LocalToolOption.Notification, it) }',
        di + '        )',
        di + '    }',
        di + ')',
    ]
    # 插入位置 = Toast item 闭合 ) 之后
    lines[oc + 4:oc + 4] = new_item
    out = NL.join(lines)

    # 自检
    for need in [
        MARK_UI,
        'LocalToolOption.Notification',
        'toggleLocalTool(LocalToolOption.Notification, it)',
    ]:
        if need not in out:
            fail(AP, 'selfcheck missing: ' + need)
    # Notification 的 toggle 调用点必须恰好 1 处(不误伤)
    if out.count('toggleLocalTool(LocalToolOption.Notification, it)') != 1:
        fail(AP, 'Notification toggle call count != 1')
    # 括号配平不变
    if balance(out) != bal0:
        fail(AP, 'bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

    (ROOT / AP).write_text(out, encoding='utf-8')
    print('batch96: AssistantLocalToolPage OK (Notification switch row added)')

print('batch96: OK (send_notification is now independently gated + user-visible)')

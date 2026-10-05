#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch100: UI 清理 —— 删 QQ群/Discord 链接 + 删高级服务里的工作区文件入口

【任务1】删 SettingPage.kt 关于 item trailingContent 里的 QQ群+Discord 两个 IconButton
  (TencentQQIcon + QQGroupBottomSheet + DiscordIcon + openUrl discord)
【任务2】删 SettingPage.kt advancedServices section 里的工作区文件入口 item
  (navController.navigate(Screen.SettingFiles))

五查:
1. import:删块不删 import(unused import 只警告不报错);零新增
2. 同文件冲突:SettingPage.kt 被 batch75 碰过(删赞助弹窗+文档/赞助/分享入口)——
   batch100 锚点在 QQ/Discord trailingContent(aboutSettings 区)和工作区文件(advancedServices 区),
   与 batch75 删的区域(赞助弹窗+文档/赞助/分享 item)不重叠
3. 作用域:LazyColumn item 区
4. 括号配对:删整块用配平扫描;插入前后括号差值不变
5. 函数签名:不改
Python 三查:无引号字面量 / NL 手写 / helper 先定义 / 失败 exit(1)
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhUICleanup'
SP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPage.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch100 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + SP + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def find_block_end_brace(lines, start):
    '''从 start 行(含 trailingContent = { )开始,找配平的 } 结束行(含 },)'''
    depth = 0
    started = False
    for i in range(start, len(lines)):
        for ch in lines[i]:
            if ch == '{':
                depth += 1
                started = True
            elif ch == '}':
                depth -= 1
        if started and depth <= 0:
            return i
    return -1


def find_item_end_paren(lines, start):
    '''从 start 行(含 item( )开始,找配平的 ) 结束行'''
    depth = 0
    started = False
    for i in range(start, len(lines)):
        for ch in lines[i]:
            if ch == '(':
                depth += 1
                started = True
            elif ch == ')':
                depth -= 1
        if started and depth <= 0:
            return i
    return -1


t = (ROOT / SP).read_text(encoding='utf-8')
if MARK in t:
    print('batch100: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    applied = []

    # ============================================================
    # 任务1: 删 QQ群/Discord trailingContent
    # ============================================================
    # 锚点: var showQQGroupSheet by remember (唯一)
    qq_hits = [i for i, ln in enumerate(lines) if ln.strip() == 'var showQQGroupSheet by remember { mutableStateOf(false) }']
    if len(qq_hits) != 1:
        fail('showQQGroupSheet anchor count=' + str(len(qq_hits)), lines, qq_hits[0] if qq_hits else 0)
    qq_i = qq_hits[0]

    # 往上找 trailingContent = { 行
    tc_start = -1
    for j in range(qq_i, max(qq_i - 20, -1), -1):
        if lines[j].strip() == 'trailingContent = {':
            tc_start = j
            break
    if tc_start < 0:
        fail('trailingContent start not found above showQQGroupSheet', lines, qq_i)

    # 往下找配平的 } 结束(trailingContent = { 的闭合)
    tc_end = find_block_end_brace(lines, tc_start)
    if tc_end < 0:
        fail('trailingContent block end not found', lines, tc_start)
    # tc_end 行应该是 } 或 },
    # 删除从 tc_start 到 tc_end(含)
    lines = lines[:tc_start] + lines[tc_end + 1:]
    applied.append('qq-discord-removed')

    # ============================================================
    # 任务2: 删工作区文件入口 item
    # ============================================================
    # 锚点: navController.navigate(Screen.SettingFiles) 行
    wf_hits = [i for i, ln in enumerate(lines) if ln.strip() == 'onClick = { navController.navigate(Screen.SettingFiles) },']
    if len(wf_hits) != 1:
        fail('SettingFiles navigate anchor count=' + str(len(wf_hits)), lines, wf_hits[0] if wf_hits else 0)
    wf_i = wf_hits[0]

    # 往上找 item( 行
    item_start = -1
    for j in range(wf_i, max(wf_i - 10, -1), -1):
        if lines[j].strip() == 'item(':
            item_start = j
            break
    if item_start < 0:
        fail('item( start not found above SettingFiles navigate', lines, wf_i)

    # 往下找配平的 ) 结束(item( 的闭合)
    item_end = find_item_end_paren(lines, item_start)
    if item_end < 0:
        fail('item block end not found', lines, item_start)
    # 删除从 item_start 到 item_end(含)
    lines = lines[:item_start] + lines[item_end + 1:]
    applied.append('workspace-files-removed')

    out = NL.join(lines)

    # 自检
    if 'showQQGroupSheet' in out:
        fail('QQ group sheet still present')
    if 'DiscordIcon' in out:
        fail('Discord icon still present')
    if 'Screen.SettingFiles' in out:
        fail('SettingFiles navigate still present')
    if balance(out) != bal0:
        fail('bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

    (ROOT / SP).write_text(out, encoding='utf-8')
    print('batch100: OK (' + ', '.join(applied) + ')')

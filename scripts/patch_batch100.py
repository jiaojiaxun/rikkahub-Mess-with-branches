#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch100 v2: 修 v1 自检误判 DiscordIcon import 行

v1 死因:自检 if 'DiscordIcon' in out 误伤 import 行
(import ...DiscordIcon 还在,但调用已删)。
v2:自检改查 discord.gg URL(只在 openUrl 调用里出现,import 行不含)。
逻辑一字不改。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhUICleanup'
SP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPage.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch100v2 ' + str(msg)
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
    print('batch100v2: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    applied = []

    # 任务1: 删 QQ群/Discord trailingContent
    qq_hits = [i for i, ln in enumerate(lines) if ln.strip() == 'var showQQGroupSheet by remember { mutableStateOf(false) }']
    if len(qq_hits) != 1:
        fail('showQQGroupSheet anchor count=' + str(len(qq_hits)), lines, qq_hits[0] if qq_hits else 0)
    qq_i = qq_hits[0]

    tc_start = -1
    for j in range(qq_i, max(qq_i - 20, -1), -1):
        if lines[j].strip() == 'trailingContent = {':
            tc_start = j
            break
    if tc_start < 0:
        fail('trailingContent start not found above showQQGroupSheet', lines, qq_i)

    tc_end = find_block_end_brace(lines, tc_start)
    if tc_end < 0:
        fail('trailingContent block end not found', lines, tc_start)
    lines = lines[:tc_start] + lines[tc_end + 1:]
    applied.append('qq-discord-removed')

    # 任务2: 删工作区文件入口 item
    wf_hits = [i for i, ln in enumerate(lines) if ln.strip() == 'onClick = { navController.navigate(Screen.SettingFiles) },']
    if len(wf_hits) != 1:
        fail('SettingFiles navigate anchor count=' + str(len(wf_hits)), lines, wf_hits[0] if wf_hits else 0)
    wf_i = wf_hits[0]

    item_start = -1
    for j in range(wf_i, max(wf_i - 10, -1), -1):
        if lines[j].strip() == 'item(':
            item_start = j
            break
    if item_start < 0:
        fail('item( start not found above SettingFiles navigate', lines, wf_i)

    item_end = find_item_end_paren(lines, item_start)
    if item_end < 0:
        fail('item block end not found', lines, item_start)
    lines = lines[:item_start] + lines[item_end + 1:]
    applied.append('workspace-files-removed')

    out = NL.join(lines)

    # v2 自检:用调用形态不用裸类名(避免误伤 import 行)
    if 'showQQGroupSheet' in out:
        fail('QQ group sheet still present')
    if 'discord.gg' in out:
        fail('Discord URL still present')
    if 'Screen.SettingFiles' in out:
        fail('SettingFiles navigate still present')
    if balance(out) != bal0:
        fail('bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

    (ROOT / SP).write_text(out, encoding='utf-8')
    print('batch100v2: OK (' + ', '.join(applied) + ')')

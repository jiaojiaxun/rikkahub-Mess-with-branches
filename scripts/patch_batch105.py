#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch105: add scheduled jobs entry in SettingPage advanced services

SettingScheduledJobsPage exists and is fully functional (list jobs, toggle,
execution history, detail dialog with cron/prompt/next/last run, manual
trigger). But there is NO navigation entry anywhere - users can only access
it through AI tools. This patch adds the missing entry in SettingPage's
advanced services section.

Five checks:
1. import: zero new (HugeIcons.Clock02 already imported in SettingPage.kt)
2. conflict: SettingPage.kt touched by batch75 (deleted sponsor alert +
   docs/donate/share items) and batch100 (deleted workspace files entry).
   Anchor (SettingToolApprovals navigate) is NOT in either region.
3. scope: inside advancedServices CollapsibleSettingsDrawer CardGroup
4. brackets: added item block is self-balanced
5. signature: no change
Python three checks: Q=chr(34) / NL handwritten / helper before use / exit(1) on fail
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhCronEntry'
SP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPage.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch105 ' + str(msg)
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


def find_item_end(lines, start):
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
    print('batch105: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)

    # Anchor: the Tool Approvals navigate line (inside advancedServices)
    ANCHOR = 'onClick = { navController.navigate(Screen.SettingToolApprovals) },'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == ANCHOR]
    if len(hits) != 1:
        fail('SettingToolApprovals anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ta_i = hits[0]

    # Find the closing paren of the item( containing the anchor
    item_start = -1
    for j in range(ta_i, max(ta_i - 10, -1), -1):
        if lines[j].strip() == 'item(':
            item_start = j
            break
    if item_start < 0:
        fail('item( not found above anchor', lines, ta_i)

    item_end = find_item_end(lines, item_start)
    if item_end < 0:
        fail('item block end not found', lines, item_start)

    # Insert after the item block ends
    d = ind(lines[item_start])
    new_item = [
        d + 'item(',
        d + '    onClick = { navController.navigate(Screen.SettingScheduledJobs) },',
        d + '    leadingContent = { Icon(HugeIcons.Clock02, null) },',
        d + '    supportingContent = { Text("\u67e5\u770b\u3001\u5f00\u5173\u548c\u7ba1\u7406 AI \u521b\u5efa\u7684\u5b9a\u65f6\u4efb\u52a1") },',
        d + '    headlineContent = { Text("\u5b9a\u65f6\u4efb\u52a1") }, // ' + MARK,
        d + ')',
    ]
    lines[item_end + 1:item_end + 1] = new_item

    out = NL.join(lines)
    for need in [MARK, 'SettingScheduledJobs']:
        if need not in out:
            fail('selfcheck missing: ' + need)
    if balance(out) != bal0:
        fail('bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

    (ROOT / SP).write_text(out, encoding='utf-8')
    print('batch105: OK (scheduled jobs entry added)')

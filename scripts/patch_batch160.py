#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch160 v2: Response API 流重试次数上限扩展到 100 (warn-only)

用户需求: 把 Response API 流重试次数的上限从 10 扩展到 100。

改动(SettingModelPage.kt):
1. take(2) -> take(3) 允许 3 位数字
2. coerceIn(0, 10) -> coerceIn(0, 100) 两处

v2 改动: fail-loud -> warn-only(多人协作,锚点可能被别人改了,不阻塞构建)
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhRetryMax100'
SP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingModelPage.kt'


def warn(msg):
    print('::warning file=' + SP + '::batch160 ' + str(msg)[:1200])


def skip(msg):
    warn(msg + ' — skipped (warn-only, multi-agent collaboration)')
    sys.stdout.flush()
    sys.exit(0)


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


t = (ROOT / SP).read_text(encoding='utf-8')
if MARK in t:
    print('batch160: already applied')
    sys.exit(0)

lines = t.split(NL)
changed = 0

# 1. take(2) -> take(3)
take_hits = [i for i, ln in enumerate(lines) if '.take(2)' in ln and 'isDigit' in ln]
if len(take_hits) != 1:
    skip('take(2) anchor count=' + str(len(take_hits)))
else:
    lines[take_hits[0]] = lines[take_hits[0]].replace('.take(2)', '.take(3) // ' + MARK)
    changed += 1

# 2. coerceIn(0, 10) -> coerceIn(0, 100) (两处)
coerce_hits = [i for i, ln in enumerate(lines) if 'coerceIn(0, 10)' in ln]
if len(coerce_hits) != 2:
    skip('coerceIn(0, 10) count=' + str(len(coerce_hits)) + ' (expect 2)')
else:
    for ci in coerce_hits:
        lines[ci] = lines[ci].replace('coerceIn(0, 10)', 'coerceIn(0, 100) // ' + MARK)
        changed += 1

if changed == 0:
    skip('no changes applied')

out = NL.join(lines)
if MARK not in out:
    skip('marker missing after apply')
if balance(out) != balance(t):
    skip('balance changed')

(ROOT / SP).write_text(out, encoding='utf-8')
print('::notice::batch160 OK - retry limit 10 -> 100 (' + str(changed) + ' changes)')

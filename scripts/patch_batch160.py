#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch160: Response API 流重试次数上限扩展到 100

用户需求: 把 Response API 流重试次数的上限从 10 扩展到 100。

改动(SettingModelPage.kt):
1. take(2) -> take(3) 允许 3 位数字
2. coerceIn(0, 10) -> coerceIn(0, 100) 两处
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhRetryMax100'
SP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingModelPage.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch160 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + SP + '::' + body[:1400])
    sys.stdout.flush()
    sys.exit(1)


t = (ROOT / SP).read_text(encoding='utf-8')
if MARK in t:
    print('batch160: already applied')
    sys.exit(0)

lines = t.split(NL)
changed = 0

# 1. take(2) -> take(3)
take_hits = [i for i, ln in enumerate(lines) if '.take(2)' in ln and 'isDigit' in ln]
if len(take_hits) != 1:
    fail('take(2) anchor count=' + str(len(take_hits)), lines, take_hits[0] if take_hits else 0)
lines[take_hits[0]] = lines[take_hits[0]].replace('.take(2)', '.take(3) // ' + MARK)
changed += 1

# 2. coerceIn(0, 10) -> coerceIn(0, 100) (两处)
coerce_hits = [i for i, ln in enumerate(lines) if 'coerceIn(0, 10)' in ln]
if len(coerce_hits) != 2:
    fail('coerceIn(0, 10) count=' + str(len(coerce_hits)) + ' (expect 2)', lines, coerce_hits[0] if coerce_hits else 0)
for ci in coerce_hits:
    lines[ci] = lines[ci].replace('coerceIn(0, 10)', 'coerceIn(0, 100) // ' + MARK)
    changed += 1

out = NL.join(lines)
if MARK not in out:
    fail('marker missing')
if 'coerceIn(0, 100)' not in out:
    fail('coerceIn(0, 100) missing')
if 'take(3)' not in out:
    fail('take(3) missing')

(ROOT / SP).write_text(out, encoding='utf-8')
print('::notice::batch160 OK - retry limit 10 -> 100 (' + str(changed) + ' changes)')

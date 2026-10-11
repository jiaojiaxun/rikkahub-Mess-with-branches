#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch168: cron describeCron 诊断+修复(warning 通道)

背景: batch165 的诊断用 notice 通道,但输出丢失(notice 通道可能被占满)。
本批改用 warning 通道(已验证有效,batch149v2 的输出曾出现)。

逻辑:
1. 检查 SettingScheduledJobsPage.kt 里 describeCron 是否存在
2. 如果 Regex 还是错误的 4 反斜杠版本 → 直接修复(替换为 2 反斜杠)
3. 检查 call sites(列表项/详情弹窗)
4. 全部用 ::warning 通道输出诊断结果
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingScheduledJobsPage.kt'


def w(msg):
    print('::warning file=' + SP + '::batch168 ' + str(msg)[:1400])
    sys.stdout.flush()


try:
    t = (ROOT / SP).read_text(encoding='utf-8')
except Exception as e:
    w('read failed: ' + str(e))
    sys.exit(0)

changed = 0

# 1. describeCron 存在性
has_desc = 'private fun describeCron(' in t
w('STEP1 describeCron present=' + str(has_desc))

if not has_desc:
    # describeCron 完全缺失——batch143 v3 没应用。这里完整补上(和 batch143 同逻辑)。
    # 但为避免重复实现,只 warn——让 batch143 v3 处理。
    w('STEP1b describeCron MISSING; patch_batch143 should have added it. Dump first 3 formatTime area lines:')
    lines = t.split(NL)
    for i, ln in enumerate(lines):
        if 'formatTime' in ln:
            for j in range(max(0, i - 2), min(i + 3, len(lines))):
                w('  L' + str(j + 1) + ': ' + lines[j].strip()[:100])
            break
    sys.exit(0)

# 2. Regex 版本检查+修复
# 错误版: Kotlin 文件里 4 反斜杠 -> Python 表示 '\\\\\\\\s+' (8个)
# 正确版: Kotlin 文件里 2 反斜杠 -> Python 表示 '\\\\s+' (4个)
WRONG = 'Regex(' + Q + '\\\\\\\\s+' + Q + ')'   # 4 backslashes in file
RIGHT = 'Regex(' + Q + '\\\\s+' + Q + ')'       # 2 backslashes in file

if WRONG in t:
    t = t.replace(WRONG, RIGHT)
    changed += 1
    w('STEP2 FIXED: regex was 4-backslash (dead), now 2-backslash (correct)')
elif RIGHT in t:
    w('STEP2 regex OK (2 backslashes, correct)')
else:
    # 未知形态——dump 实际行
    lines = t.split(NL)
    for i, ln in enumerate(lines):
        if 'split(Regex' in ln or 'describeCron' in ln and 'Regex' in ln:
            w('STEP2 unknown regex form at L' + str(i + 1) + ': ' + ln.strip()[:120])

# 3. call sites 检查
if 'describeCron(job.cronExpression)' in t:
    w('STEP3 call sites OK (list+dialog wired)')
else:
    w('STEP3 call sites MISSING; dump cronExpression lines:')
    lines = t.split(NL)
    for i, ln in enumerate(lines):
        if 'job.cronExpression' in ln:
            w('  L' + str(i + 1) + ': ' + ln.strip()[:120])

# 4. 写回(如果有修复)
if changed > 0:
    (ROOT / SP).write_text(t, encoding='utf-8')
    w('WROTE file with ' + str(changed) + ' fixes')
else:
    w('no changes needed')

print('batch168: DONE')

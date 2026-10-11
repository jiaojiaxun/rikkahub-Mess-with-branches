#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch165: 诊断——dump SettingScheduledJobsPage.kt 的 describeCron 实际状态

用户反馈: cron 中文解释还是用不了。
batch143 v3 的脚本是对的(Regex 4反斜杠源码),但用户说还是不行。
本脚本只诊断: dump 关键行到 annotation,不修改文件,不阻塞构建。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
SP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingScheduledJobsPage.kt'

try:
    t = (ROOT / SP).read_text(encoding='utf-8')
except Exception as e:
    print('::warning::batch165 read failed: ' + str(e))
    sys.exit(0)

lines = t.split(NL)

# 1. 找 describeCron 相关行
dc_lines = []
for i, ln in enumerate(lines):
    if 'describeCron' in ln or 'split(Regex' in ln or 'private fun formatTime' in ln:
        dc_lines.append('L' + str(i + 1) + ':' + ln.strip()[:110])

print('::notice::batch165 DIAG-1 describeCron=[' + ' ;; '.join(dc_lines[:12]) + ']')

# 2. 找列表项和详情弹窗
list_lines = []
for i, ln in enumerate(lines):
    if 'job.cronExpression' in ln:
        list_lines.append('L' + str(i + 1) + ':' + ln.strip()[:110])

print('::notice::batch165 DIAG-2 cronExpression=[' + ' ;; '.join(list_lines[:8]) + ']')

# 3. 检查 MARK
if 'rhCronDesc' in t:
    print('::notice::batch165 DIAG-3 MARK rhCronDesc PRESENT')
else:
    print('::notice::batch165 DIAG-3 MARK rhCronDesc MISSING')

print('batch165: DIAG DONE')

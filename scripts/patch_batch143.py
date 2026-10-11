#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch143 v3: 定时任务 cron 表达式加中文解释(修 Regex 转义)

v2 死功能: split(Regex("\\\\s+")) 8 反斜杠源码→Kotlin 4反斜杠→解析 2反斜杠→正则匹配
字面量反斜杠+s,不匹配空白→split 失败→描述永不显示。JS 链路模拟验证:分割=1(失败)。

v3 修法: Python 源码 8反斜杠→4反斜杠,生成 Kotlin Regex("\\s+") 正确匹配空白。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SQ = chr(39)
MARK = 'rhCronDesc'
SP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingScheduledJobsPage.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch143v3 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + SP + '::' + body[:1400])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


t = (ROOT / SP).read_text(encoding='utf-8')
if MARK in t:
    print('batch143v3: already applied')
    sys.exit(0)

bal0 = balance(t)
lines = t.split(NL)
applied = []

# ---- 1. describeCron helper(插在 formatTime 之前) ----
fmt_hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('private fun formatTime(')]
if len(fmt_hits) != 1:
    fail('formatTime anchor count=' + str(len(fmt_hits)), lines, fmt_hits[0] if fmt_hits else 0)
fi = fmt_hits[0]
d = ind(lines[fi])
# v3: Regex 4 反斜杠源码(正确); when 无逗号; padStart 单引号
helper = [
    d + '// ' + MARK + ': cron 表达式 → 中文描述',
    d + 'private fun describeCron(expr: String): String {',
    d + '    val parts = expr.trim().split(Regex(' + Q + '\\\\s+' + Q + '))',
    d + '    if (parts.size != 5) return expr',
    d + '    val (min, hour, day, month, week) = parts',
    d + '    fun num(s: String): Int? = s.toIntOrNull()',
    d + '    fun pad2(n: Int): String = n.toString().padStart(2, ' + SQ + '0' + SQ + ')',
    d + '    return when {',
    d + '        min.startsWith(' + Q + '*/' + Q + ') -> ' + Q + '每 ' + Q + ' + min.removePrefix(' + Q + '*/' + Q + ') + ' + Q + ' 分钟' + Q,
    d + '        min == ' + Q + '*' + Q + ' -> ' + Q + '每分钟' + Q,
    d + '        hour == ' + Q + '*' + Q + ' -> ' + Q + '每小时第 ' + Q + ' + min + ' + Q + ' 分钟' + Q,
    d + '        week != ' + Q + '*' + Q + ' -> {',
    d + '            val dayName = when (week) {',
    d + '                ' + Q + '0' + Q + ', ' + Q + '7' + Q + ' -> ' + Q + '日' + Q,
    d + '                ' + Q + '1' + Q + ' -> ' + Q + '一' + Q,
    d + '                ' + Q + '2' + Q + ' -> ' + Q + '二' + Q,
    d + '                ' + Q + '3' + Q + ' -> ' + Q + '三' + Q,
    d + '                ' + Q + '4' + Q + ' -> ' + Q + '四' + Q,
    d + '                ' + Q + '5' + Q + ' -> ' + Q + '五' + Q,
    d + '                ' + Q + '6' + Q + ' -> ' + Q + '六' + Q,
    d + '                else -> week',
    d + '            }',
    d + '            ' + Q + '每周' + Q + ' + dayName + ' + Q + ' ' + Q + ' + (num(hour)?.let { pad2(it) } ?: hour) + ' + Q + ':' + Q + ' + (num(min)?.let { pad2(it) } ?: min)',
    d + '        }',
    d + '        day != ' + Q + '*' + Q + ' -> ' + Q + '每月 ' + Q + ' + day + ' + Q + ' 号 ' + Q + ' + (num(hour)?.let { pad2(it) } ?: hour) + ' + Q + ':' + Q + ' + (num(min)?.let { pad2(it) } ?: min)',
    d + '        else -> ' + Q + '每天 ' + Q + ' + (num(hour)?.let { pad2(it) } ?: hour) + ' + Q + ':' + Q + ' + (num(min)?.let { pad2(it) } ?: min)',
    d + '    }',
    d + '}',
    '',
]
for j, b in enumerate(helper):
    lines.insert(fi + j, b)
applied.append('describeCron')

# ---- 2. 列表项 ----
list_hits = [i for i, ln in enumerate(lines) if 'job.cronExpression + ' + Q + '  ·  ' + Q + ' + job.prompt.take(60)' in ln]
if len(list_hits) != 1:
    fail('list cronExpression anchor count=' + str(len(list_hits)), lines, list_hits[0] if list_hits else 0)
li = list_hits[0]
lines[li] = lines[li].replace(
    'job.cronExpression + ' + Q + '  ·  ' + Q + ' + job.prompt.take(60)',
    'describeCron(job.cronExpression) + ' + Q + '  ·  ' + Q + ' + job.prompt.take(60)',
)
applied.append('list-item')

# ---- 3. 详情弹窗 ----
dlg_hits = [i for i, ln in enumerate(lines) if 'Text(' + Q + 'cron：' + Q + ' + job.cronExpression)' in ln]
if len(dlg_hits) != 1:
    fail('dialog cron anchor count=' + str(len(dlg_hits)), lines, dlg_hits[0] if dlg_hits else 0)
di = dlg_hits[0]
lines[di] = lines[di].replace(
    'Text(' + Q + 'cron：' + Q + ' + job.cronExpression)',
    'Text(' + Q + 'cron：' + Q + ' + job.cronExpression + ' + Q + '（' + Q + ' + describeCron(job.cronExpression) + ' + Q + '）' + Q + ')',
)
applied.append('dialog')

# ---- 4. 自检 ----
out = NL.join(lines)
for need in [MARK, 'private fun describeCron(', 'describeCron(job.cronExpression)']:
    if need not in out:
        fail('selfcheck missing: ' + need)
two_bs = chr(92) + chr(92)
if 'Regex(' + Q + two_bs + 's+' + Q + ')' not in out:
    fail('selfcheck: Regex escape wrong (need 2 backslashes in Kotlin source)')
if balance(out) != bal0:
    fail('balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

(ROOT / SP).write_text(out, encoding='utf-8')
print('::notice::batch143v3 OK - ' + ', '.join(applied))

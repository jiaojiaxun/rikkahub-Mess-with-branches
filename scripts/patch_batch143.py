#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch143 v2: 定时任务 cron 表达式加中文解释

v1 死因: 两个语法错误
1. when 分支后面加了逗号 —— Kotlin 的 when 分支不需要逗号分隔
2. padStart(2, "0") 传了 String "0" 但期望 Char '0' —— 需要单引号

v2 修法: 去掉 when 分支逗号 + padStart 用单引号

其余逻辑不变(describeCron helper + 列表项/详情弹窗替换)。
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
    body = 'batch143v2 ' + str(msg)
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
    print('batch143v2: already applied')
    sys.exit(0)

bal0 = balance(t)
lines = t.split(NL)
applied = []

# ---- 1. 加 describeCron helper(插在 formatTime 之前) ----
fmt_hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('private fun formatTime(')]
if len(fmt_hits) != 1:
    fail('formatTime anchor count=' + str(len(fmt_hits)), lines, fmt_hits[0] if fmt_hits else 0)
fi = fmt_hits[0]
d = ind(lines[fi])
# v2: when 分支去掉逗号 + padStart 用单引号
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

# ---- 2. 列表项: cronExpression → describeCron ----
list_hits = [i for i, ln in enumerate(lines) if 'job.cronExpression + ' + Q + '  ·  ' + Q + ' + job.prompt.take(60)' in ln]
if len(list_hits) != 1:
    fail('list cronExpression anchor count=' + str(len(list_hits)), lines, list_hits[0] if list_hits else 0)
li = list_hits[0]
old_line = lines[li]
new_line = old_line.replace(
    'job.cronExpression + ' + Q + '  ·  ' + Q + ' + job.prompt.take(60)',
    'describeCron(job.cronExpression) + ' + Q + '  ·  ' + Q + ' + job.prompt.take(60)',
)
if new_line == old_line:
    fail('list line replacement no-op', lines, li)
lines[li] = new_line
applied.append('list-item')

# ---- 3. 详情弹窗: cron 行加描述 ----
dlg_hits = [i for i, ln in enumerate(lines) if 'Text(' + Q + 'cron：' + Q + ' + job.cronExpression)' in ln]
if len(dlg_hits) != 1:
    fail('dialog cron anchor count=' + str(len(dlg_hits)), lines, dlg_hits[0] if dlg_hits else 0)
di = dlg_hits[0]
old_line = lines[di]
new_line = old_line.replace(
    'Text(' + Q + 'cron：' + Q + ' + job.cronExpression)',
    'Text(' + Q + 'cron：' + Q + ' + job.cronExpression + ' + Q + '（' + Q + ' + describeCron(job.cronExpression) + ' + Q + '）' + Q + ')',
)
if new_line == old_line:
    fail('dialog line replacement no-op', lines, di)
lines[di] = new_line
applied.append('dialog')

# ---- 4. 自检 ----
out = NL.join(lines)
for need in [MARK, 'private fun describeCron(', 'describeCron(job.cronExpression)']:
    if need not in out:
        fail('selfcheck missing: ' + need)
if balance(out) != bal0:
    fail('balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

(ROOT / SP).write_text(out, encoding='utf-8')
print('::notice::batch143v2 OK - ' + ', '.join(applied))

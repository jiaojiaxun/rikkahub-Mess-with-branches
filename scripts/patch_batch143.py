#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch143: 定时任务 cron 表达式加中文解释

用户反馈(#15): "cron 无中文解释且让用户手写cron很奇怪"

改动(SettingScheduledJobsPage.kt 单文件):
1. 加 describeCron(expr) helper——把 cron 表达式翻译成中文描述
   例: "0 8 * * *" → "每天早上 08:00"
        "*/30 * * * *" → "每 30 分钟"
        "0 9 1 * *" → "每月 1 号 09:00"
        "0 8 * * 1" → "每周一 08:00"
2. 列表项: Text(job.cronExpression + "  ·  " + ...) → Text(describeCron(job.cronExpression) + "  ·  " + ...)
3. 详情弹窗: Text("cron：" + job.cronExpression) → Text("cron：" + job.cronExpression + "（" + describeCron(...) + "）")

五查:
1. import 清单: describeCron 是文件内函数,零新增 import;Regex 是 Kotlin 标准库
2. 同文件冲突: SettingScheduledJobsPage.kt 无在链 patch 触碰(list_commits 仅初始快照)
3. 作用域: describeCron 是文件级 private fun;调用点在 @Composable 函数体内
4. 括号配对: 插入块自平衡;全文件 balance 前后一致
5. 函数签名: 不改

Python 三查: 引号 Q=chr(34) 构造;NL 手写 concat;helper 先定义;失败显式 exit(1)
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhCronDesc'
SP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingScheduledJobsPage.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch143 ' + str(msg)
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
    print('batch143: already applied')
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
helper = [
    d + '// ' + MARK + ': cron 表达式 → 中文描述',
    d + 'private fun describeCron(expr: String): String {',
    d + '    val parts = expr.trim().split(Regex(' + Q + '\\\\s+' + Q + '))',
    d + '    if (parts.size != 5) return expr',
    d + '    val (min, hour, day, month, week) = parts',
    d + '    fun num(s: String): Int? = s.toIntOrNull()',
    d + '    fun pad2(n: Int): String = n.toString().padStart(2, ' + Q + '0' + Q + ')',
    d + '    return when {',
    d + '        min.startsWith(' + Q + '*/' + Q + ') -> ' + Q + '每 ' + Q + ' + min.removePrefix(' + Q + '*/' + Q + ') + ' + Q + ' 分钟' + Q + ',',
    d + '        min == ' + Q + '*' + Q + ' -> ' + Q + '每分钟' + Q + ',',
    d + '        hour == ' + Q + '*' + Q + ' -> ' + Q + '每小时第 ' + Q + ' + min + ' + Q + ' 分钟' + Q + ',',
    d + '        week != ' + Q + '*' + Q + ' -> {',
    d + '            val dayName = when (week) {',
    d + '                ' + Q + '0' + Q + ', ' + Q + '7' + Q + ' -> ' + Q + '日' + Q + '',
    d + '                ' + Q + '1' + Q + ' -> ' + Q + '一' + Q + '',
    d + '                ' + Q + '2' + Q + ' -> ' + Q + '二' + Q + '',
    d + '                ' + Q + '3' + Q + ' -> ' + Q + '三' + Q + '',
    d + '                ' + Q + '4' + Q + ' -> ' + Q + '四' + Q + '',
    d + '                ' + Q + '5' + Q + ' -> ' + Q + '五' + Q + '',
    d + '                ' + Q + '6' + Q + ' -> ' + Q + '六' + Q + '',
    d + '                else -> week',
    d + '            }',
    d + '            ' + Q + '每周' + Q + ' + dayName + ' + Q + ' ' + Q + ' + (num(hour)?.let { pad2(it) } ?: hour) + ' + Q + ':' + Q + ' + (num(min)?.let { pad2(it) } ?: min)',
    d + '        },',
    d + '        day != ' + Q + '*' + Q + ' -> ' + Q + '每月 ' + Q + ' + day + ' + Q + ' 号 ' + Q + ' + (num(hour)?.let { pad2(it) } ?: hour) + ' + Q + ':' + Q + ' + (num(min)?.let { pad2(it) } ?: min),',
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
print('::notice::batch143 OK - ' + ', '.join(applied))

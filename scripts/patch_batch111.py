#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch111 v2: manual cron job create/edit - fixes four v1 bugs

v1 bugs found by selfcheck + review:
1. MARK never written into inserted code -> selfcheck missing
2. Icon(onClick=...) does not exist in Material3; must be IconButton
3. Trailing comma after TextButton inside Row lambda is a syntax error
4. Dialog was anchored on the LAST '}' in the file, which closes
   recordSummary (a non-composable fun), not SettingScheduledJobsPage

v2 fixes all four. Dialog is inserted before the closing brace of
SettingScheduledJobsPage, located via the 'private fun formatTime' anchor.
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhCronManual'
SP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingScheduledJobsPage.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch111v2 ' + str(msg)
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
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


t = (ROOT / SP).read_text(encoding='utf-8')
if MARK in t:
    print('batch111v2: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    applied = []

    # 1. imports (after last import line)
    imp_hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('import ')]
    if not imp_hits:
        fail('no import lines found')
    last_imp = imp_hits[-1]
    existing = set(ln.strip() for ln in lines)
    new_imports = [imp for imp in [
        'import androidx.compose.material3.Icon',
        'import androidx.compose.material3.IconButton',
        'import androidx.compose.material3.OutlinedTextField',
        'import me.rerere.hugeicons.HugeIcons',
        'import me.rerere.hugeicons.stroke.Add01',
    ] if imp not in existing]
    for j, imp in enumerate(new_imports):
        lines.insert(last_imp + 1 + j, imp)
    applied.append('imports+' + str(len(new_imports)))

    # 2. state vars after detailJob declaration
    STATE_ANCHOR = 'var detailJob by remember { mutableStateOf<CronJob?>(null) }'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == STATE_ANCHOR]
    if len(hits) != 1:
        fail('state anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    si = hits[0]
    d = ind(lines[si])
    lines[si + 1:si + 1] = [
        d + 'var showCreateDialog by remember { mutableStateOf(false) } // ' + MARK,
        d + 'var editJob by remember { mutableStateOf<CronJob?>(null) } // ' + MARK,
    ]
    applied.append('state')

    # 3. top-bar actions with IconButton (NOT Icon) after the title line
    TITLE_ANCHOR = 'title = { Text("定时任务") },'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == TITLE_ANCHOR]
    if len(hits) != 1:
        fail('title anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ti = hits[0]
    d = ind(lines[ti])
    lines[ti + 1:ti + 1] = [
        d + 'actions = { // ' + MARK,
        d + '    IconButton(onClick = { showCreateDialog = true }) {',
        d + '        Icon(HugeIcons.Add01, contentDescription = "新建任务")',
        d + '    }',
        d + '},',
    ]
    applied.append('actions')

    # 4. Edit button before the trigger TextButton in detail dialog Row
    TRIGGER_ANCHOR = 'Text("立即执行")'
    hits = [i for i, ln in enumerate(lines) if TRIGGER_ANCHOR in ln]
    if len(hits) != 1:
        fail('trigger anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    tri = hits[0]
    tb_start = -1
    for j in range(tri, max(tri - 6, -1), -1):
        if 'TextButton(' in lines[j]:
            tb_start = j
            break
    if tb_start < 0:
        fail('TextButton start not found above trigger', lines, tri)
    d = ind(lines[tb_start])
    # NOTE: no trailing comma - composables in a Row lambda are statements
    lines[tb_start:tb_start] = [
        d + 'TextButton(onClick = { // ' + MARK,
        d + '    editJob = job',
        d + '    detailJob = null',
        d + '}) {',
        d + '    Text("编辑")',
        d + '}',
    ]
    applied.append('edit-btn')

    # 5. dialog before the closing brace of SettingScheduledJobsPage
    #    anchor: 'private fun formatTime' -> scan backwards for the '}' that closes the page
    fmt_hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('private fun formatTime')]
    if len(fmt_hits) != 1:
        fail('formatTime anchor count=' + str(len(fmt_hits)))
    fi = fmt_hits[0]
    close_idx = -1
    for j in range(fi - 1, -1, -1):
        if lines[j].strip() == '}':
            close_idx = j
            break
    if close_idx < 0:
        fail('page closing brace not found', lines, fi)
    d = ind(lines[close_idx]) + '    '
    dialog_block = [
        d + 'if (showCreateDialog || editJob != null) { // ' + MARK,
        d + '    val editing = editJob',
        d + '    var jobName by remember { mutableStateOf(editing?.name ?: "") }',
        d + '    var cronExpr by remember { mutableStateOf(editing?.cronExpression ?: "0 9 * * *") }',
        d + '    var jobPrompt by remember { mutableStateOf(editing?.prompt ?: "") }',
        d + '    var jobEnabled by remember { mutableStateOf(editing?.enabled ?: true) }',
        d + '    val cronValid = CronParser.isValid(cronExpr)',
        d + '    AlertDialog(',
        d + '        onDismissRequest = {',
        d + '            showCreateDialog = false',
        d + '            editJob = null',
        d + '        },',
        d + '        title = { Text(if (editing != null) "编辑任务" else "新建任务") },',
        d + '        text = {',
        d + '            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {',
        d + '                OutlinedTextField(',
        d + '                    value = jobName,',
        d + '                    onValueChange = { jobName = it },',
        d + '                    label = { Text("任务名称") },',
        d + '                    singleLine = true,',
        d + '                )',
        d + '                OutlinedTextField(',
        d + '                    value = cronExpr,',
        d + '                    onValueChange = { cronExpr = it },',
        d + '                    label = { Text("Cron 表达式") },',
        d + '                    supportingText = {',
        d + '                        Text(',
        d + '                            text = if (cronValid) "格式正确" else "格式错误，应为：分 时 日 月 周",',
        d + '                            color = if (cronValid) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,',
        d + '                        )',
        d + '                    },',
        d + '                    singleLine = true,',
        d + '                )',
        d + '                OutlinedTextField(',
        d + '                    value = jobPrompt,',
        d + '                    onValueChange = { jobPrompt = it },',
        d + '                    label = { Text("提示词") },',
        d + '                    minLines = 3,',
        d + '                )',
        d + '                Row(',
        d + '                    verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,',
        d + '                    horizontalArrangement = Arrangement.spacedBy(8.dp),',
        d + '                ) {',
        d + '                    Text("启用")',
        d + '                    Switch(checked = jobEnabled, onCheckedChange = { jobEnabled = it })',
        d + '                }',
        d + '            }',
        d + '        },',
        d + '        confirmButton = {',
        d + '            TextButton(',
        d + '                onClick = {',
        d + '                    scope.launch {',
        d + '                        val job = (editing ?: CronJob(',
        d + '                            id = java.util.UUID.randomUUID().toString(),',
        d + '                            name = jobName,',
        d + '                            prompt = jobPrompt,',
        d + '                            cronExpression = cronExpr,',
        d + '                        )).copy(',
        d + '                            name = jobName,',
        d + '                            prompt = jobPrompt,',
        d + '                            cronExpression = cronExpr,',
        d + '                            enabled = jobEnabled,',
        d + '                        )',
        d + '                        store.upsert(job)',
        d + '                        if (jobEnabled) scheduler.schedule(job) else scheduler.cancel(job.id)',
        d + '                    }',
        d + '                    showCreateDialog = false',
        d + '                    editJob = null',
        d + '                },',
        d + '                enabled = jobName.isNotBlank() && cronValid,',
        d + '            ) { Text("保存") }',
        d + '        },',
        d + '        dismissButton = {',
        d + '            TextButton(onClick = {',
        d + '                showCreateDialog = false',
        d + '                editJob = null',
        d + '            }) { Text("取消") }',
        d + '        },',
        d + '    )',
        d + '}',
    ]
    lines[close_idx:close_idx] = dialog_block
    applied.append('dialog')

    out = NL.join(lines)
    for need in [MARK, 'showCreateDialog', 'editJob', 'OutlinedTextField', 'CronParser.isValid', 'IconButton']:
        if need not in out:
            fail('selfcheck missing: ' + need)
    if balance(out) != bal0:
        fail('bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

    (ROOT / SP).write_text(out, encoding='utf-8')
    print('batch111v2: OK (' + ', '.join(applied) + ')')

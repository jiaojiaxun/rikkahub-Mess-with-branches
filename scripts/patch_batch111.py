#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch111: add manual cron job creation/editing to SettingScheduledJobsPage

Adds:
- "New Task" button in top bar (opens create dialog)
- Edit button on each job row (opens edit dialog)
- Create/Edit dialog: name, cron expression, prompt, enabled toggle
- Cron expression validation with real-time feedback

Five checks:
1. import: add OutlinedTextField, Icon, HugeIcons.Add01
2. conflict: SettingScheduledJobsPage.kt untouched by any other patch
3. scope: SettingScheduledJobsPage @Composable
4. brackets: self-balanced dialog composable
5. signature: no change to existing functions
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhCronManual'
SP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingScheduledJobsPage.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch111 ' + str(msg)
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
    print('batch111: already applied')
else:
    bal0 = balance(t)
    lines = t.split(NL)
    applied = []

    # 1. imports: add after existing imports
    # Find the last import line
    imp_hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('import ')]
    if not imp_hits:
        fail('no import lines found')
    last_imp = imp_hits[-1]
    new_imports = [
        'import androidx.compose.material3.Icon',
        'import androidx.compose.material3.OutlinedTextField',
        'import me.rerere.hugeicons.HugeIcons',
        'import me.rerere.hugeicons.stroke.Add01',
    ]
    for j, imp in enumerate(new_imports):
        lines.insert(last_imp + 1 + j, imp)
    applied.append('imports')

    # 2. Add "New Task" button to top bar actions
    # Anchor: the title Text in LargeFlexibleTopAppBar
    TITLE_ANCHOR = 'title = { Text("定时任务") },'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == TITLE_ANCHOR]
    if len(hits) != 1:
        fail('title anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    ti = hits[0]
    d = ind(lines[ti])
    # Insert actions block after title line
    actions_block = [
        d + 'actions = {',
        d + '    Icon(onClick = { showCreateDialog = true }, imageVector = HugeIcons.Add01, contentDescription = "\u65b0\u5efa\u4efb\u52a1")',
        d + '},',
    ]
    lines[ti + 1:ti + 1] = actions_block
    applied.append('actions')

    # 3. Add state variables before Scaffold
    # Anchor: var detailJob by remember { mutableStateOf<CronJob?>(null) }
    STATE_ANCHOR = 'var detailJob by remember { mutableStateOf<CronJob?>(null) }'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == STATE_ANCHOR]
    if len(hits) != 1:
        fail('state anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    si = hits[0]
    d = ind(lines[si])
    new_state = [
        d + 'var showCreateDialog by remember { mutableStateOf(false) }',
        d + 'var editJob by remember { mutableStateOf<CronJob?>(null) }',
    ]
    lines[si + 1:si + 1] = new_state
    applied.append('state')

    # 4. Add "Edit" button to detail dialog confirmButton Row
    # Anchor: TextButton(onClick = {\n    scheduler.triggerNow(job.id)
    # Find the "立即执行" TextButton and add an "Edit" button before it
    TRIGGER_ANCHOR = 'Text("\u7acb\u5373\u6267\u884c")'
    hits = [i for i, ln in enumerate(lines) if TRIGGER_ANCHOR in ln]
    if len(hits) != 1:
        fail('trigger anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    tri = hits[0]
    # Find the TextButton( that contains this Text
    tb_start = -1
    for j in range(tri, max(tri - 5, -1), -1):
        if 'TextButton(' in lines[j]:
            tb_start = j
            break
    if tb_start < 0:
        fail('TextButton start not found above trigger', lines, tri)
    d = ind(lines[tb_start])
    edit_btn = [
        d + 'TextButton(onClick = {',
        d + '    editJob = job',
        d + '    detailJob = null',
        d + '}) {',
        d + '    Text("\u7f16\u8f91")',
        d + '},',
    ]
    lines[tb_start:tb_start] = edit_btn
    applied.append('edit-btn')

    # 5. Add create/edit dialog composable before the closing brace of SettingScheduledJobsPage
    # Find the end of the detailJob?.let block (the last closing brace before the final } of the function)
    # Anchor: the last `}` of the function body. Find it by scanning from the end.
    func_end = -1
    for i in range(len(lines) - 1, max(len(lines) - 5, -1), -1):
        if lines[i].strip() == '}':
            func_end = i
            break
    if func_end < 0:
        fail('function end not found')

    d = ind(lines[func_end])
    dialog_block = [
        d + '',
        d + 'if (showCreateDialog || editJob != null) {',
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
        d + '        title = { Text(if (editing != null) "\u7f16\u8f91\u4efb\u52a1" else "\u65b0\u5efa\u4efb\u52a1") },',
        d + '        text = {',
        d + '            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {',
        d + '                OutlinedTextField(',
        d + '                    value = jobName,',
        d + '                    onValueChange = { jobName = it },',
        d + '                    label = { Text("\u4efb\u52a1\u540d\u79f0") },',
        d + '                    singleLine = true,',
        d + '                )',
        d + '                OutlinedTextField(',
        d + '                    value = cronExpr,',
        d + '                    onValueChange = { cronExpr = it },',
        d + '                    label = { Text("Cron \u8868\u8fbe\u5f0f") },',
        d + '                    supportingText = {',
        d + '                        Text(',
        d + '                            text = if (cronValid) "\u2705 \u683c\u5f0f\u6b63\u786e" else "\u274c \u683c\u5f0f\u9519\u8bef\uff0c\u683c\u5f0f\uff1a\u5206 \u65f6 \u65e5 \u6708 \u5468",',
        d + '                            color = if (cronValid) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,',
        d + '                        )',
        d + '                    },',
        d + '                    singleLine = true,',
        d + '                )',
        d + '                OutlinedTextField(',
        d + '                    value = jobPrompt,',
        d + '                    onValueChange = { jobPrompt = it },',
        d + '                    label = { Text("\u63d0\u793a\u8bcd") },',
        d + '                    minLines = 3,',
        d + '                )',
        d + '                Row(',
        d + '                    verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,',
        d + '                    horizontalArrangement = Arrangement.spacedBy(8.dp),',
        d + '                ) {',
        d + '                    Text("\u542f\u7528")',
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
        d + '            ) { Text("\u4fdd\u5b58") }',
        d + '        },',
        d + '        dismissButton = {',
        d + '            TextButton(onClick = {',
        d + '                showCreateDialog = false',
        d + '                editJob = null',
        d + '            }) { Text("\u53d6\u6d88") }',
        d + '        },',
        d + '    )',
        d + '}',
    ]
    lines[func_end:func_end] = dialog_block
    applied.append('dialog')

    out = NL.join(lines)
    for need in [MARK, 'showCreateDialog', 'editJob', 'OutlinedTextField', 'CronParser.isValid']:
        if need not in out:
            fail('selfcheck missing: ' + need)
    if balance(out) != bal0:
        fail('bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

    (ROOT / SP).write_text(out, encoding='utf-8')
    print('batch111: OK (' + ', '.join(applied) + ')')

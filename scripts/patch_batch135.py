#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch135 v3: WebDAV/S3 备份上传改用 AppScope（后台传输）

v2 死因: find_fn_end 的括号扫描逻辑 bug——suspend fun restore( 行没有 {,depth=0,
下一行 item: WebDavBackupItem 也没有 {,depth=0 → 条件 depth==0 and j>start 立刻命中,
返回了 start+1 而不是函数真正结尾。只删了 2 行插入了 15 行,原函数体的 } 全留着。

v3 修法: find_fn_end 加 seen_brace 标志——必须先看到 { 才开始算 depth 归零。

其余不变:AppScope 注入 + isBackingUp + 4 个函数转 AppScope + 全部 warn-only。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhBgBackup'
VM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/backup/BackupVM.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch135v3 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:100] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + VM + '::' + body[:1400])
    sys.stdout.flush()
    sys.exit(1)


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


def warn(msg):
    print('::warning file=' + VM + '::batch135v3 ' + str(msg))


t = (ROOT / VM).read_text(encoding='utf-8')
if MARK in t and 'appScope.launch' in t and 'suspend fun backup()' not in t:
    print('batch135v3: fully applied, skip')
    sys.exit(0)

bal0 = balance(t)
lines = t.split(NL)
changed = 0


def find_fn(lines, name_pattern, verify_pattern):
    candidates = [i for i, ln in enumerate(lines) if name_pattern in ln]
    for i in candidates:
        window = lines[i:i + 8]
        if any(verify_pattern in w for w in window):
            return i
    return -1


def find_fn_end(lines, start):
    '''v3 fix: must see { before checking depth==0'''
    depth = 0
    seen_brace = False
    for j in range(start, min(start + 25, len(lines))):
        depth += lines[j].count('{') - lines[j].count('}')
        if '{' in lines[j]:
            seen_brace = True
        if seen_brace and depth == 0:
            return j
    return -1


# ---- 1. import AppScope ----
if 'import me.rerere.rikkahub.AppScope' not in t:
    hits = [i for i, ln in enumerate(lines) if ln.strip() == 'import me.rerere.rikkahub.data.datastore.SettingsStore']
    if len(hits) != 1:
        warn('import anchor count=' + str(len(hits)) + ', skip import')
    else:
        lines.insert(hits[0] + 1, 'import me.rerere.rikkahub.AppScope')
        changed += 1
        print('batch135v3: AppScope import added')

# ---- 2. constructor: add appScope param ----
if 'private val appScope: AppScope' not in t:
    hits = [i for i, ln in enumerate(lines) if ln.strip() == 'private val filesManager: FilesManager,']
    if len(hits) != 1:
        warn('constructor anchor count=' + str(len(hits)) + ', skip constructor')
    else:
        i = hits[0]
        indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
        lines.insert(i + 1, indent + 'private val appScope: AppScope,  // ' + MARK)
        changed += 1
        print('batch135v3: appScope param added')

# ---- 3. add isBackingUp after progress declaration ----
if 'isBackingUp' not in t:
    hits = [i for i, ln in enumerate(lines) if 'val progress = MutableStateFlow<BackupProgress?>(null)' in ln]
    if len(hits) != 1:
        warn('progress anchor count=' + str(len(hits)) + ', skip isBackingUp')
    else:
        i = hits[0]
        indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
        lines.insert(i + 1, indent + 'val isBackingUp = MutableStateFlow(false)  // ' + MARK)
        changed += 1
        print('batch135v3: isBackingUp added')


def convert_to_appscope(lines, fn_name_pattern, fn_verify_pattern, build_body_fn, label):
    i = find_fn(lines, fn_name_pattern, fn_verify_pattern)
    if i < 0:
        warn(label + ' anchor not found, skip')
        return lines, 0
    if 'appScope.launch' in NL.join(lines[i:i + 10]):
        print('batch135v3: ' + label + ' already converted, skip')
        return lines, 0
    end = find_fn_end(lines, i)
    if end < 0:
        warn(label + ' closing brace not found, skip')
        return lines, 0
    d = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    new_lines = build_body_fn(d, NL.join(lines[i:end + 1]))
    lines[i:end + 1] = new_lines
    return lines, 1


# ---- 4. backup() ----
lines, c = convert_to_appscope(
    lines,
    'suspend fun backup()',
    'webDavSync.backup',
    lambda d, body: [
        d + 'fun backup() {  // ' + MARK + ': 改用 AppScope,切页面继续传',
        d + '    isBackingUp.value = true',
        d + '    appScope.launch {',
        d + '        try {',
        d + '            runWithProgress { report ->',
        d + '                webDavSync.backup(settings.value.webDavConfig, report)',
        d + '            }',
        d + '            recordBackupTime()',
        d + '        } finally {',
        d + '            isBackingUp.value = false',
        d + '        }',
        d + '    }',
        d + '}',
    ],
    'backup()',
)
changed += c

# ---- 5. restore() ----
lines, c = convert_to_appscope(
    lines,
    'suspend fun restore(',
    'WebDavBackupItem',
    lambda d, body: [
        d + 'fun restore(',
        d + '    item: WebDavBackupItem,',
        d + '    mode: BackupRestoreMode = BackupRestoreMode.OVERWRITE,',
        d + ') {  // ' + MARK,
        d + '    isBackingUp.value = true',
        d + '    appScope.launch {',
        d + '        try {',
        d + '            runWithProgress { report ->',
        d + '                webDavSync.restore(config = settings.value.webDavConfig, item = item, mode = mode, onProgress = report)',
        d + '            }',
        d + '        } finally {',
        d + '            isBackingUp.value = false',
        d + '        }',
        d + '    }',
        d + '}',
    ],
    'restore()',
)
changed += c

# ---- 6. backupToS3() ----
lines, c = convert_to_appscope(
    lines,
    'suspend fun backupToS3()',
    's3Sync.backupToS3',
    lambda d, body: [
        d + 'fun backupToS3() {  // ' + MARK,
        d + '    isBackingUp.value = true',
        d + '    appScope.launch {',
        d + '        try {',
        d + '            runWithProgress { report ->',
        d + '                s3Sync.backupToS3(settings.value.s3Config, report)',
        d + '            }',
        d + '            recordBackupTime()',
        d + '        } finally {',
        d + '            isBackingUp.value = false',
        d + '        }',
        d + '    }',
        d + '}',
    ],
    'backupToS3()',
)
changed += c

# ---- 7. restoreFromS3() ----
lines, c = convert_to_appscope(
    lines,
    'suspend fun restoreFromS3(',
    'S3BackupItem',
    lambda d, body: [
        d + 'fun restoreFromS3(',
        d + '    item: S3BackupItem,',
        d + '    mode: BackupRestoreMode = BackupRestoreMode.OVERWRITE,',
        d + ') {  // ' + MARK,
        d + '    isBackingUp.value = true',
        d + '    appScope.launch {',
        d + '        try {',
        d + '            runWithProgress { report ->',
        d + '                s3Sync.restoreFromS3(',
        d + '                    config = settings.value.s3Config,',
        d + '                    item = item,',
        d + '                    mode = mode,',
        d + '                    onProgress = report,',
        d + '                )',
        d + '            }',
        d + '        } finally {',
        d + '            isBackingUp.value = false',
        d + '        }',
        d + '    }',
        d + '}',
    ],
    'restoreFromS3()',
)
changed += c

# ---- write + selfcheck ----
if changed == 0:
    print('batch135v3: nothing changed (all anchors already applied or not found)')
    sys.exit(0)

out = NL.join(lines)
if balance(out) != bal0:
    fail('balance mismatch: ' + str(bal0) + ' -> ' + str(balance(out)))
for need in ['appScope.launch']:
    if need not in out:
        fail('selfcheck missing: ' + need)

(ROOT / VM).write_text(out, encoding='utf-8')
print('::notice::batch135v3 OK - changed=' + str(changed) + ' (backup/restore/backupToS3/restoreFromS3 to AppScope)')

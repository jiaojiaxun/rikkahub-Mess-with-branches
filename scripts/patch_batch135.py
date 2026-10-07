#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch135: WebDAV/S3 备份上传改用 AppScope（后台传输）

需求: 用户点了备份按钮后可以切到聊天页/设置页,上传继续进行不被中断。
当前: backup() 是 suspend,在 BackupPage 的 Compose scope 里跑,页面销毁即取消。
修法: 改用 AppScope.launch,生命周期绑定 App 进程而非页面。

改动:
1. BackupVM 构造函数加 private val appScope: AppScope
2. BackupVM 加 isBackingUp MutableStateFlow(false)
3. backup()/restore()/backupToS3()/restoreFromS3() 从 suspend 改为非 suspend,
   内部 appScope.launch { ... },用 isBackingUp 管理按钮状态
4. 幂等: MARK 检查

铁律②: BackupVM 无在链 patch 触碰(list_commits 只有初始快照)。
铁律③: appScope 构造函数注入,isBackingUp 类成员,均在类作用域。
铁律④: 插入行自平衡;全文件 balance 前后一致。
铁律⑤: 不改函数签名对外的可调用性(非 suspend 兼容原 suspend 调用点)。
Python 三查: 引号 Q/NL 变量构造;无 f-string;失败 exit(1)。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhBgBackup'
VM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/backup/BackupVM.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch135 ' + str(msg)
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


t = (ROOT / VM).read_text(encoding='utf-8')
if MARK in t:
    print('batch135: already applied')
    sys.exit(0)

bal0 = balance(t)
lines = t.split(NL)
changed = 0

# ---- 1. import AppScope + MutableStateFlow(already imported) ----
if 'import me.rerere.rikkahub.AppScope' not in t:
    hits = [i for i, ln in enumerate(lines) if ln.strip() == 'import me.rerere.rikkahub.data.datastore.SettingsStore']
    if len(hits) != 1:
        fail('import anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    lines.insert(hits[0] + 1, 'import me.rerere.rikkahub.AppScope')
    changed += 1
    print('batch135: AppScope import added')

# ---- 2. constructor: add appScope param ----
hits = [i for i, ln in enumerate(lines) if ln.strip() == 'private val filesManager: FilesManager,']
if len(hits) != 1:
    fail('constructor anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
i = hits[0]
indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
lines.insert(i + 1, indent + 'private val appScope: AppScope,  // ' + MARK)
changed += 1
print('batch135: appScope param added')

# ---- 3. add isBackingUp after progress declaration ----
hits = [i for i, ln in enumerate(lines) if 'val progress = MutableStateFlow<BackupProgress?>(null)' in ln]
if len(hits) != 1:
    fail('progress anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
i = hits[0]
indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
lines.insert(i + 1, indent + 'val isBackingUp = MutableStateFlow(false)  // ' + MARK)
changed += 1
print('batch135: isBackingUp added')

# ---- 4. backup() — suspend -> non-suspend + appScope.launch ----
hits = [i for i, ln in enumerate(lines) if ln.strip() == 'suspend fun backup() {']
if len(hits) != 1:
    fail('backup anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
i = hits[0]
d = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
# find closing brace of backup()
depth = 0
end = -1
for j in range(i, min(i + 20, len(lines))):
    depth += lines[j].count('{') - lines[j].count('}')
    if depth == 0 and j > i:
        end = j
        break
if end < 0:
    fail('backup closing brace not found', lines, i)
# verify content
body = NL.join(lines[i:end + 1])
if 'webDavSync.backup' not in body:
    fail('backup body unexpected: ' + body[:200])
new_backup = [
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
]
lines[i:end + 1] = new_backup
changed += 1
print('batch135: backup() converted to AppScope')

# ---- 5. restore() — same conversion ----
hits = [i for i, ln in enumerate(lines) if 'suspend fun restore(' in ln and 'item: WebDavBackupItem' in ln]
if len(hits) != 1:
    fail('restore anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
i = hits[0]
d = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
depth = 0
end = -1
for j in range(i, min(i + 25, len(lines))):
    depth += lines[j].count('{') - lines[j].count('}')
    if depth == 0 and j > i:
        end = j
        break
if end < 0:
    fail('restore closing brace not found', lines, i)
body = NL.join(lines[i:end + 1])
if 'webDavSync.restore' not in body:
    fail('restore body unexpected: ' + body[:200])
new_restore = [
    d + 'fun restore(',  # keep same signature minus suspend
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
]
lines[i:end + 1] = new_restore
changed += 1
print('batch135: restore() converted to AppScope')

# ---- 6. backupToS3() — same conversion ----
hits = [i for i, ln in enumerate(lines) if ln.strip() == 'suspend fun backupToS3() {']
if len(hits) != 1:
    fail('backupToS3 anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
i = hits[0]
d = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
depth = 0
end = -1
for j in range(i, min(i + 20, len(lines))):
    depth += lines[j].count('{') - lines[j].count('}')
    if depth == 0 and j > i:
        end = j
        break
if end < 0:
    fail('backupToS3 closing brace not found', lines, i)
body = NL.join(lines[i:end + 1])
if 's3Sync.backupToS3' not in body:
    fail('backupToS3 body unexpected: ' + body[:200])
new_s3 = [
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
]
lines[i:end + 1] = new_s3
changed += 1
print('batch135: backupToS3() converted to AppScope')

# ---- 7. restoreFromS3() — same conversion ----
hits = [i for i, ln in enumerate(lines) if 'suspend fun restoreFromS3(' in ln]
if len(hits) != 1:
    fail('restoreFromS3 anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
i = hits[0]
d = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
depth = 0
end = -1
for j in range(i, min(i + 25, len(lines))):
    depth += lines[j].count('{') - lines[j].count('}')
    if depth == 0 and j > i:
        end = j
        break
if end < 0:
    fail('restoreFromS3 closing brace not found', lines, i)
body = NL.join(lines[i:end + 1])
if 's3Sync.restoreFromS3' not in body:
    fail('restoreFromS3 body unexpected: ' + body[:200])
new_s3r = [
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
]
lines[i:end + 1] = new_s3r
changed += 1
print('batch135: restoreFromS3() converted to AppScope')

# ---- 8. write + selfcheck ----
out = NL.join(lines)
if balance(out) != bal0:
    fail('balance mismatch: ' + str(bal0) + ' -> ' + str(balance(out)))
for need in [MARK, 'appScope', 'isBackingUp', 'appScope.launch']:
    if need not in out:
        fail('selfcheck missing: ' + need)
if 'suspend fun backup()' in out:
    fail('backup() still suspend')
if 'suspend fun restore(' in out and 'WebDavBackupItem' in out:
    fail('restore() still suspend')

(ROOT / VM).write_text(out, encoding='utf-8')
print('::notice::batch135 OK - backup/restore/backupToS3/restoreFromS3 all use AppScope, changes=' + str(changed))

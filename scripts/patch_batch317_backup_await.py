#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch317: 修 WebDAV / S3 备份「刚开始就提示成功」

现象: 点「立即备份」或「覆盖恢复」后约 0.1 秒就弹「备份成功 / 恢复成功」,
      实际传输/恢复才刚开始; 覆盖恢复还会立刻弹出重启对话框。

根因(batch135 引入): BackupVM 的 backup / restore / backupToS3 / restoreFromS3
从 suspend 改成 appScope.launch 的 fire-and-forget 形态(后台传输,切页继续传),
但调用方 WebDavTab / S3Tab 仍按同步语义写:
    runCatching { vm.backup(); toaster.show(备份成功) }
函数立刻返回 -> 任务刚排进队列, toast 已经弹出来了。

修法: VM 返回 Deferred<Unit>(CompletableDeferred 桥接后台任务结果),
      UI 侧 .await() 之后再提示; 取消(切页)时把 CancellationException 抛回协程,
      不弹假失败。

原子性: 三个文件先在内存里全部改成功才写盘(UI await 而 VM 没改会编译红)。
MARK=rhBackupAwait317   diag=ci_diag_batch317_backup_await.txt
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhBackupAwait317'
DIAG = 'ci_diag_batch317_backup_await.txt'
VM = 'app/src/main/java/me/rerere/rikkahub/ui/pages/backup/BackupVM.kt'
WDAV = 'app/src/main/java/me/rerere/rikkahub/ui/pages/backup/tabs/WebDavTab.kt'
S3T = 'app/src/main/java/me/rerere/rikkahub/ui/pages/backup/tabs/S3Tab.kt'
CANCEL = 'kotlinx.coroutines.CancellationException'


def note(msg):
    try:
        with open(DIAG, 'a', encoding='utf-8') as f:
            f.write(msg + NL)
    except Exception:
        pass
    print('::warning title=batch317::' + str(msg)[:180])


def indent_of(line):
    return line[:len(line) - len(line.lstrip())]


def find_exact(lines, stripped):
    return [i for i, ln in enumerate(lines) if ln.strip() == stripped]


def find_prefix(lines, prefix):
    return [i for i, ln in enumerate(lines) if ln.strip().startswith(prefix)]


def fn_end(lines, start, limit=80):
    depth = 0
    seen = False
    for j in range(start, min(start + limit, len(lines))):
        depth += lines[j].count('{') - lines[j].count('}')
        if '{' in lines[j]:
            seen = True
        if seen and depth == 0:
            return j
    return -1


def bal(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}'))


CATCH_TAIL = [
    '        } catch (e: ' + CANCEL + ') {',
    '            done.cancel(e)',
    '            throw e',
    '        } catch (e: Throwable) {',
    '            done.completeExceptionally(e)',
    '        } finally {',
    '            isBackingUp.value = false',
    '        }',
    '    }',
    '    return done',
    '}',
]

VM_SPECS = [
    (
        'fun backup()',
        [
            'fun backup(): Deferred<Unit> {  // ' + MARK + ': 后台执行,返回可等待句柄',
            '    isBackingUp.value = true',
            '    val done = CompletableDeferred<Unit>()',
            '    appScope.launch {',
            '        try {',
            '            runWithProgress { report ->',
            '                webDavSync.backup(settings.value.webDavConfig, report)',
            '            }',
            '            recordBackupTime()',
            '            done.complete(Unit)',
        ] + CATCH_TAIL,
        'VM.backup',
    ),
    (
        'fun restore(',
        [
            'fun restore(',
            '    item: WebDavBackupItem,',
            '    mode: BackupRestoreMode = BackupRestoreMode.OVERWRITE,',
            '): Deferred<Unit> {  // ' + MARK,
            '    isBackingUp.value = true',
            '    val done = CompletableDeferred<Unit>()',
            '    appScope.launch {',
            '        try {',
            '            runWithProgress { report ->',
            '                webDavSync.restore(config = settings.value.webDavConfig, item = item, mode = mode, onProgress = report)',
            '            }',
            '            done.complete(Unit)',
        ] + CATCH_TAIL,
        'VM.restore',
    ),
    (
        'fun backupToS3()',
        [
            'fun backupToS3(): Deferred<Unit> {  // ' + MARK,
            '    isBackingUp.value = true',
            '    val done = CompletableDeferred<Unit>()',
            '    appScope.launch {',
            '        try {',
            '            runWithProgress { report ->',
            '                s3Sync.backupToS3(settings.value.s3Config, report)',
            '            }',
            '            recordBackupTime()',
            '            done.complete(Unit)',
        ] + CATCH_TAIL,
        'VM.backupToS3',
    ),
    (
        'fun restoreFromS3(',
        [
            'fun restoreFromS3(',
            '    item: S3BackupItem,',
            '    mode: BackupRestoreMode = BackupRestoreMode.OVERWRITE,',
            '): Deferred<Unit> {  // ' + MARK,
            '    isBackingUp.value = true',
            '    val done = CompletableDeferred<Unit>()',
            '    appScope.launch {',
            '        try {',
            '            runWithProgress { report ->',
            '                s3Sync.restoreFromS3(',
            '                    config = settings.value.s3Config,',
            '                    item = item,',
            '                    mode = mode,',
            '                    onProgress = report,',
            '                )',
            '            }',
            '            done.complete(Unit)',
        ] + CATCH_TAIL,
        'VM.restoreFromS3',
    ),
]

WDAV_CALLS = [
    ('vm.backup()', 'vm.backup().await()', 'WebDav.backup'),
    (
        'vm.restore(item, BackupRestoreMode.OVERWRITE)',
        'vm.restore(item, BackupRestoreMode.OVERWRITE).await()',
        'WebDav.restore',
    ),
]

S3_CALLS = [
    ('vm.backupToS3()', 'vm.backupToS3().await()', 'S3.backup'),
    (
        'vm.restoreFromS3(item, BackupRestoreMode.OVERWRITE)',
        'vm.restoreFromS3(item, BackupRestoreMode.OVERWRITE).await()',
        'S3.restore',
    ),
]


def replace_fn(lines, prefix, spec, label):
    hits = find_prefix(lines, prefix)
    if len(hits) != 1:
        note('FAIL ' + label + ' anchor count=' + str(len(hits)))
        return 0
    i = hits[0]
    if MARK in lines[i]:
        note('SKIP ' + label + ' marker present')
        return 1
    end = fn_end(lines, i)
    if end < 0:
        note('FAIL ' + label + ' end missing :: ' + ' | '.join(x.strip() for x in lines[i:i + 5]))
        return 0
    ind = indent_of(lines[i])
    lines[i:end + 1] = [(ind + b) if b else b for b in spec]
    note('OK ' + label + ' L' + str(i + 1) + '-' + str(end + 1) + ' -> ' + str(len(spec)) + ' lines')
    return 1


def prep_vm(text):
    if MARK in text:
        note('SKIP VM (already patched)')
        return True, text
    b0 = bal(text)
    lines = text.split(NL)
    need = []
    if 'import kotlinx.coroutines.Deferred' not in text:
        need.append('import kotlinx.coroutines.Deferred')
    if 'import kotlinx.coroutines.CompletableDeferred' not in text:
        need.append('import kotlinx.coroutines.CompletableDeferred')
    if need:
        anchor = find_exact(lines, 'import kotlinx.coroutines.launch')
        if len(anchor) != 1:
            note('FAIL VM import anchor count=' + str(len(anchor)))
            return False, text
        for k, imp in enumerate(need):
            lines.insert(anchor[0] + 1 + k, imp)
        note('OK VM imports +' + str(len(need)))
    cnt = 0
    for prefix, spec, label in VM_SPECS:
        cnt += replace_fn(lines, prefix, spec, label)
    if cnt != 4:
        note('FAIL VM only ' + str(cnt) + '/4 functions converted')
        return False, text
    out = NL.join(lines)
    if bal(out) != b0:
        note('FAIL VM balance ' + str(b0) + ' -> ' + str(bal(out)))
        return False, text
    if out.count('Deferred<Unit>') != 4:
        note('FAIL VM Deferred<Unit> count=' + str(out.count('Deferred<Unit>')))
        return False, text
    if out.count('CompletableDeferred<Unit>()') != 4:
        note('FAIL VM CompletableDeferred count=' + str(out.count('CompletableDeferred<Unit>()')))
        return False, text
    if out.count(MARK) != 4:
        note('FAIL VM MARK count=' + str(out.count(MARK)))
        return False, text
    if 'import kotlinx.coroutines.Deferred' not in out:
        note('FAIL VM Deferred import missing')
        return False, text
    if 'import kotlinx.coroutines.CompletableDeferred' not in out:
        note('FAIL VM CompletableDeferred import missing')
        return False, text
    return True, out


def patch_ui_call(lines, call_strip, new_call, label):
    hits = find_exact(lines, call_strip)
    if len(hits) != 1:
        note('FAIL ' + label + ' call count=' + str(len(hits)))
        return 0
    i = hits[0]
    lines[i] = indent_of(lines[i]) + new_call
    j = -1
    for k in range(i, min(i + 14, len(lines))):
        if '.onFailure' in lines[k]:
            j = k
            break
    if j < 0:
        note('FAIL ' + label + ' onFailure missing')
        return 0
    if CANCEL in NL.join(lines[j:j + 4]):
        note('SKIP ' + label + ' guard present')
        return 1
    head = lines[j].strip()
    var = 'it'
    if '->' in head:
        var = (head.split('->')[0].replace('.onFailure', '')
               .replace('{', '').replace('}', '').strip() or 'it')
    if j + 1 >= len(lines):
        note('FAIL ' + label + ' no line after onFailure')
        return 0
    guard = indent_of(lines[j + 1]) + 'if (' + var + ' is ' + CANCEL + ') throw ' + var + '  // ' + MARK
    lines.insert(j + 1, guard)
    note('OK ' + label + ' await + guard(' + var + ')')
    return 1


def prep_ui(text, name, calls):
    if MARK in text:
        note('SKIP ' + name + ' (already patched)')
        return True, text
    b0 = bal(text)
    lines = text.split(NL)
    cnt = 0
    for call_strip, new_call, label in calls:
        cnt += patch_ui_call(lines, call_strip, new_call, label)
    if cnt != len(calls):
        note('FAIL ' + name + ' only ' + str(cnt) + '/' + str(len(calls)))
        return False, text
    out = NL.join(lines)
    if bal(out) != b0:
        note('FAIL ' + name + ' balance ' + str(b0) + ' -> ' + str(bal(out)))
        return False, text
    if out.count('.await()') != len(calls):
        note('FAIL ' + name + ' await count=' + str(out.count('.await()')))
        return False, text
    if out.count(CANCEL) != len(calls):
        note('FAIL ' + name + ' guard count=' + str(out.count(CANCEL)))
        return False, text
    return True, out


def read_text(path):
    p = ROOT / path
    if not p.exists():
        return None
    return p.read_text(encoding='utf-8')


def main():
    vm_text = read_text(VM)
    wd_text = read_text(WDAV)
    s3_text = read_text(S3T)
    if vm_text is None or wd_text is None or s3_text is None:
        note('FAIL missing source: vm=' + str(vm_text is not None)
             + ' webdav=' + str(wd_text is not None)
             + ' s3=' + str(s3_text is not None))
        return
    ok_vm, out_vm = prep_vm(vm_text)
    ok_wd, out_wd = prep_ui(wd_text, 'WebDavTab', WDAV_CALLS)
    ok_s3, out_s3 = prep_ui(s3_text, 'S3Tab', S3_CALLS)
    if not (ok_vm and ok_wd and ok_s3):
        note('ABORT nothing written (vm=' + str(ok_vm)
             + ' webdav=' + str(ok_wd) + ' s3=' + str(ok_s3) + ')')
        return
    (ROOT / VM).write_text(out_vm, encoding='utf-8')
    (ROOT / WDAV).write_text(out_wd, encoding='utf-8')
    (ROOT / S3T).write_text(out_s3, encoding='utf-8')
    back_vm = (ROOT / VM).read_text(encoding='utf-8')
    back_wd = (ROOT / WDAV).read_text(encoding='utf-8')
    back_s3 = (ROOT / S3T).read_text(encoding='utf-8')
    checks = [
        ('VM.Deferred', back_vm.count('Deferred<Unit>') == 4),
        ('VM.Completable', back_vm.count('CompletableDeferred<Unit>()') == 4),
        ('VM.importDeferred', 'import kotlinx.coroutines.Deferred' in back_vm),
        ('VM.importCompletable', 'import kotlinx.coroutines.CompletableDeferred' in back_vm),
        ('VM.MARK', back_vm.count(MARK) == 4),
        ('WebDav.await', back_wd.count('.await()') == 2),
        ('WebDav.guard', back_wd.count(CANCEL) == 2),
        ('S3.await', back_s3.count('.await()') == 2),
        ('S3.guard', back_s3.count(CANCEL) == 2),
    ]
    bad = [name for name, ok in checks if not ok]
    if bad:
        note('POSTCHECK FAIL ' + ','.join(bad))
    else:
        note('DONE 3/3 written, await=4, guards=4, MARK=' + MARK)


try:
    main()
except Exception as exc:
    note('EXCEPTION ' + type(exc).__name__ + ': ' + str(exc)[:300])
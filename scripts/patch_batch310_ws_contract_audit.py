#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch310: workspace 引擎契约审计（静态）

这个脚本不修代码, 只做可验证的断言并把结果写进 ci_diag_batch310.txt。
CI 的 patch 步骤是 warn-only（exit 被 sed 改掉）, 所以 diag 文件比 annotation 可靠。

断言项:
1. app 侧所有 import me.rerere.workspace.X 的符号, 必须在模块里有定义
2. 13 个必需符号全部存在
3. 22 个方法名（含 hasRootfs / createRootfsStaging / commitRootfs）均有 fun 定义
4. BackgroundStatus / WorkspaceCommandResult / WorkspaceFileEntry / RootfsInstallProgress 字段名逐个匹配
5. 每个 .kt 括号配平（圆/花/方）
6. ProotShellRunner 不含 --kill-on-exit 与 /bin/bash, 且 argv 含 /rh-libs 与 APPLET_PATH
7. RepositoryModule 三处命名参数（baseDir / shellRunner / nativeLibraryDir / bindMounts）
8. jniLibs 里是否真的落了 libbusybox.so（大小/SHA256/ELF 头）
'''
import hashlib
import struct
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MOD = 'workspace/src/main/java/me/rerere/workspace'
APPJAVA = 'app/src/main/java'
DIAG = 'ci_diag_batch310.txt'

REQUIRED_SYMBOLS = [
    'BackgroundStatus', 'ProotShellRunner', 'RootfsInstallProgress', 'RootfsInstallStage',
    'RootfsInstaller', 'Workspace', 'WorkspaceBindMount', 'WorkspaceCommandResult',
    'WorkspaceFileEntry', 'WorkspaceManager', 'WorkspaceShellStatus', 'WorkspaceStorageArea',
    'WorkspaceTreeResult',
]

REQUIRED_METHODS = [
    'ensureWorkspace', 'workspaceDir', 'hasRootfs', 'listFiles', 'readText', 'writeText',
    'importFile', 'fileSize', 'resolveFile', 'exportFile', 'deleteFile', 'moveFile',
    'rootfsTree', 'rootfsFileSize', 'exportRootfsFile', 'executeCommand', 'startBackground',
    'backgroundStatus', 'listBackground', 'killBackground', 'deleteWorkspace',
    'createRootfsStaging', 'commitRootfs',
]

FIELDS = {
    'BackgroundStatus': ['id', 'command', 'cwd', 'running', 'exitCode', 'startedAtMillis',
                         'stdout', 'stderr', 'droppedStdout', 'droppedStderr'],
    'WorkspaceCommandResult': ['exitCode', 'stdout', 'stderr', 'timedOut', 'truncated'],
    'WorkspaceFileEntry': ['path', 'name', 'isDirectory', 'sizeBytes', 'updatedAt'],
    'RootfsInstallProgress': ['stage', 'bytesRead', 'totalBytes', 'entriesExtracted', 'currentEntry'],
}

report = []
failures = []


def note(m):
    report.append(str(m)[:900])


def fail(m):
    failures.append(str(m)[:400])
    note('FAIL ' + str(m)[:400])


def balance(t):
    return (t.count('(') - t.count(')')
            + t.count('{') - t.count('}')
            + t.count('[') - t.count(']'))


def read_all():
    out = {}
    base = ROOT / MOD
    if not base.is_dir():
        fail('module dir missing: ' + MOD)
        return out
    for p in sorted(base.glob('*.kt')):
        try:
            out[p.name] = p.read_text(encoding='utf-8')
        except Exception as exc:
            fail('read fail ' + p.name + ' ' + str(exc)[:120])
    return out


def check_brackets(sources):
    for name, text in sources.items():
        bal = balance(text)
        if bal != 0:
            fail('bracket balance ' + name + ' = ' + str(bal))
    note('brackets checked files=' + str(len(sources)))


def check_symbols(sources):
    joined = NL.join(sources.values())
    for sym in REQUIRED_SYMBOLS:
        hits = [key for key, text in sources.items()
                if ('class ' + sym) in text or ('enum class ' + sym) in text
                or ('data class ' + sym) in text or ('object ' + sym) in text]
        if not hits:
            fail('symbol missing: ' + sym)
        else:
            note('symbol ' + sym + ' in ' + ','.join(hits))

    # app 侧 import 的符号必须都能在模块里找到
    app_imports = set()
    appdir = ROOT / APPJAVA
    if appdir.is_dir():
        for p in appdir.rglob('*.kt'):
            try:
                text = p.read_text(encoding='utf-8', errors='ignore')
            except Exception:
                continue
            for line in text.split(NL):
                s = line.strip()
                if s.startswith('import me.rerere.workspace.'):
                    sym = s[len('import me.rerere.workspace.'):].strip()
                    if sym and '.' not in sym and '*' not in sym:
                        app_imports.add(sym)
    note('app imports (' + str(len(app_imports)) + '): ' + ','.join(sorted(app_imports)))
    for sym in sorted(app_imports):
        if not any(('class ' + sym) in t or ('enum class ' + sym) in t
                   or ('data class ' + sym) in t or ('object ' + sym) in t
                   for t in sources.values()):
            fail('app imports unknown symbol: ' + sym)


def check_methods(sources):
    joined = NL.join(sources.values())
    for name in REQUIRED_METHODS:
        if ('fun ' + name + '(') not in joined:
            fail('method missing: ' + name)
    note('methods checked=' + str(len(REQUIRED_METHODS)))


def check_fields(sources):
    joined = NL.join(sources.values())
    for owner, fields in FIELDS.items():
        for field in fields:
            if ('val ' + field + ':') not in joined:
                fail('field missing: ' + owner + '.' + field)
    note('fields checked=' + str(sum(len(v) for v in FIELDS.values())))


def check_proot(sources):
    text = sources.get('ProotShellRunner.kt', '')
    if not text:
        fail('ProotShellRunner.kt missing')
        return
    for bad in ['--kill-on-exit', '/bin/bash']:
        if bad in text:
            fail('ProotShellRunner still contains ' + bad)
    for need in ['WorkspaceBusybox.RH_LIBS', 'WorkspaceBusybox.APPLET_PATH', 'LD_LIBRARY_PATH']:
        if need not in text:
            fail('ProotShellRunner missing ' + need)
    if 'nativeLibraryDir' not in text:
        fail('ProotShellRunner missing nativeLibraryDir')
    note('proot runner checked')


def check_busybox(sources):
    text = sources.get('WorkspaceBusybox.kt', '')
    if not text:
        fail('WorkspaceBusybox.kt missing')
        return
    for need in ['object WorkspaceBusybox', 'const val EXEC_PATH', 'fun listApplets(',
                 'fun ensureFarm(', 'fun hasFarm(', 'fun isReady(']:
        if need not in text:
            fail('WorkspaceBusybox missing ' + need)

    lib = ROOT / 'workspace/src/main/jniLibs/arm64-v8a/libbusybox.so'
    if not lib.is_file():
        fail('libbusybox.so not present in jniLibs')
        return
    data = lib.read_bytes()
    sha = hashlib.sha256(data).hexdigest()
    note('libbusybox.so size=' + str(len(data)) + ' sha256=' + sha)
    if len(data) < 128 or data[0:4] != bytes([127, 69, 76, 70]):
        fail('libbusybox.so is not ELF')
        return
    e_machine = struct.unpack_from('<H', data, 18)[0]
    if e_machine != 183:
        fail('libbusybox.so e_machine=' + str(e_machine) + ' (expect 183)')
    e_phoff = struct.unpack_from('<Q', data, 32)[0]
    e_phentsize = struct.unpack_from('<H', data, 54)[0]
    e_phnum = struct.unpack_from('<H', data, 56)[0]
    interp = False
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        if off + 4 > len(data):
            break
        if struct.unpack_from('<I', data, off)[0] == 3:
            interp = True
    if interp:
        fail('libbusybox.so has PT_INTERP (must be static)')
    note('libbusybox.so ELF ok')


def check_di():
    p = ROOT / 'app/src/main/java/me/rerere/rikkahub/di/RepositoryModule.kt'
    if not p.is_file():
        fail('RepositoryModule.kt missing')
        return
    text = p.read_text(encoding='utf-8', errors='ignore')
    for need in ['baseDir =', 'shellRunner =', 'nativeLibraryDir =', 'bindMounts =']:
        if need not in text:
            fail('RepositoryModule missing ' + need)
    note('DI checked')


def write_diag():
    body = ''
    body += 'FAILURES=' + str(len(failures)) + NL
    body += '---- detail ----' + NL
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:
        print('::error::batch310 diag write failed ' + str(exc)[:200])


def main():
    sources = read_all()
    note('module files=' + str(len(sources)) + ' -> ' + ','.join(sorted(sources.keys())))
    checks = [
        ('brackets', lambda: check_brackets(sources)),
        ('symbols', lambda: check_symbols(sources)),
        ('methods', lambda: check_methods(sources)),
        ('fields', lambda: check_fields(sources)),
        ('proot', lambda: check_proot(sources)),
        ('busybox', lambda: check_busybox(sources)),
        ('di', check_di),
    ]
    for label, fn in checks:
        try:
            fn()
            note('check ' + label + ' DONE')
        except Exception as exc:
            fail('check ' + label + ' EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:200])


def finish():
    note('---- summary ----')
    note('failures=' + str(len(failures)))
    for item in failures:
        note('  * ' + item)
    write_diag()
    for line in report:
        print('::error::batch310 ' + str(line)[:900])
    print('::error::batch310 END failures=' + str(len(failures)))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        fail('main crashed ' + str(exc)[:300])
    finish()
    sys.exit(0)

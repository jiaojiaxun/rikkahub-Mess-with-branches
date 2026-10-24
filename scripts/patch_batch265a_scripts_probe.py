#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch265a: scripts 进备份的取证（只读，不改代码）

用户提出：脚本也要可以存入备份。我需要先弄清三件事：
1. `FileFolders` 常量的真实定义（`UPLOAD` / `SKILLS` / `IMAGES` / `TOOL_OUTPUTS` 是哪个对象的属性，scripts 有没有对应常量）
2. 设备上 scripts 目录的真实相对路径（`filesDir` 下的子目录名是什么）
3. `BackupArchiveRestorer.normalizeEntryName` 的 rootAliases 里需不需要加 scripts（恢复时能不能解回 filesDir）

本批只 dump 取证，不改任何源码。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch265a.txt'

report = []


def note(msg):
    report.append(str(msg)[:900])


def grep_lines(rel_glob, keywords):
    base = ROOT / rel_glob
    if not base.exists():
        note('probe missing dir ' + rel_glob)
        return
    for p in sorted(base.rglob('*.kt')):
        try:
            lines = p.read_text(encoding='utf-8').split(NL)
        except Exception:
            continue
        hits = []
        for i, ln in enumerate(lines):
            s = ln.strip()
            for k in keywords:
                if k in s:
                    hits.append('L' + str(i + 1) + ':' + s[:180])
                    break
        if hits:
            note('FILE ' + str(p.relative_to(ROOT)))
            for h in hits[:24]:
                note('  ' + h)


def main():
    # 1. FileFolders 定义
    grep_lines('app/src/main/java', ['object FileFolders', 'class FileFolders', 'FileFolders('])

    # 2. scripts 目录引用
    grep_lines('app/src/main/java', ['"scripts"', 'FileFolders.SCRIPTS', 'SCRIPTS =', 'val SCRIPTS',
                                     'File(context.filesDir, "scripts")', 'filesDir, "scripts"'])

    # 3. 备份恢复侧的 normalizeEntryName / resolveAppFile 的别名表
    p = ROOT / 'app/src/main/java/me/rerere/rikkahub/data/sync/webdav/BackupArchiveRestorer.kt'
    if p.exists():
        lines = p.read_text(encoding='utf-8').split(NL)
        keys = ['rootAliases', 'resolveAppFile', 'normalizeEntryName', 'FileFolders.', '"scripts"']
        hits = []
        for i, ln in enumerate(lines):
            s = ln.strip()
            for k in keys:
                if k in s:
                    hits.append('L' + str(i + 1) + ':' + s[:190])
                    break
        note('BackupArchiveRestorer hits=' + str(len(hits)))
        for h in hits[:60]:
            note('rec ' + h)

    # 4. 备份打包侧 backupFileEntries 的目录清单
    p = ROOT / 'app/src/main/java/me/rerere/rikkahub/data/sync/webdav/WebDavSync.kt'
    if p.exists():
        lines = p.read_text(encoding='utf-8').split(NL)
        keys = ['backupFileEntries', 'FileFolders.', 'listOf(', 'trees =', 'filesDir, folder']
        hits = []
        for i, ln in enumerate(lines):
            s = ln.strip()
            for k in keys:
                if k in s:
                    hits.append('L' + str(i + 1) + ':' + s[:190])
                    break
        note('WebDavSync backupFileEntries hits=' + str(len(hits)))
        for h in hits[:50]:
            note('webdav ' + h)

    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch265a diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch265a diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()
    for line in report:
        print('::error::batch265a ' + str(line)[:800])
    print('::error::batch265a END lines=' + str(len(report)))


main()
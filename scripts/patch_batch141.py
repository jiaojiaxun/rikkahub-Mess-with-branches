#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch141: 诊断 —— dump AppDatabase 版本号 + DataSourceModule addMigrations 行

编译错误: DataSourceModule.kt line 50 Unresolved reference 'Migration_35_36'。
仓库态没有 Migration_35_36——某个在链 patch 在 CI 上加了它。

本脚本只做诊断: dump 关键行到 annotation,不修改任何文件,不阻塞构建。
一次 CI run 拿到真形态,二次修准。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)

ADB = 'app/src/main/java/me/rerere/rikkahub/data/db/AppDatabase.kt'
DM = 'app/src/main/java/me/rerere/rikkahub/di/DataSourceModule.kt'

# ---- 1. AppDatabase.kt 版本号 + migration 类 ----
adb = (ROOT / ADB).read_text(encoding='utf-8')
adb_lines = adb.split(NL)

version_line = 'MISSING'
for ln in adb_lines:
    if ln.strip().startswith('version ='):
        version_line = ln.strip()
        break

mig_classes = []
for ln in adb_lines:
    s = ln.strip()
    if s.startswith('class Migration_') or s.startswith('object Migration_'):
        mig_classes.append(s[:80])
    if 'AutoMigration(from' in ln:
        mig_classes.append('AM:' + ln.strip()[:80])

print('::notice::DIAG-ADB version=[' + version_line + '] migrations=[' + ' ;; '.join(mig_classes[:15]) + ']')

# ---- 2. DataSourceModule.kt addMigrations 行 ----
dm = (ROOT / DM).read_text(encoding='utf-8')
dm_lines = dm.split(NL)

addmig_line = 'MISSING'
for i, ln in enumerate(dm_lines):
    if 'addMigrations(' in ln:
        addmig_line = 'L' + str(i + 1) + ':' + ln.strip()[:200]
        break

import_mig = []
for ln in dm_lines:
    s = ln.strip()
    if s.startswith('import') and 'Migration_' in s:
        import_mig.append(s.split('.')[-1])

print('::notice::DIAG-DM addMigrations=[' + addmig_line + '] imports=[' + ' ;; '.join(import_mig) + ']')

# ---- 3. 检查 Migration_35_36 类是否存在 ----
mig35_exists = False
for p in ROOT.rglob('Migration_35_36*'):
    mig35_exists = True
    print('::notice::DIAG-MIG35 found: ' + str(p))

if not mig35_exists:
    print('::notice::DIAG-MIG35 not found in repo')

print('batch141: DIAG DONE')

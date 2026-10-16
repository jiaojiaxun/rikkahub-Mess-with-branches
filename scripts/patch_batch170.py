#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch170: 修 models.dev 目录的并发竞态(warn-only)

对抗性检查发现: batch169 的 modelsDevFetchAttempted 检查-设置不是原子的。
多个协程并发调用 queryModelsDev 时,可能同时通过检查,各拉一次 api.json(几百KB×N)。

修法: 用 Mutex.withLock 保护 "检查+拉取" 临界区。
需要加 import: kotlinx.coroutines.sync.Mutex / kotlinx.coroutines.sync.withLock

warn-only: 任何锚点失败只 ::warning + 跳过,不阻塞构建。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhModelsDevLock'
F = 'app/src/main/java/me/rerere/rikkahub/data/model/ModelContextLengthResolver.kt'


def warn(msg):
    print('::warning file=' + F + '::batch170 ' + str(msg)[:1200])


def skip(msg):
    warn(msg + ' — skipped (warn-only)')
    sys.stdout.flush()
    sys.exit(0)


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


try:
    t = (ROOT / F).read_text(encoding='utf-8')
except Exception as e:
    skip('read failed: ' + str(e))

if MARK in t:
    print('batch170: already applied')
    sys.exit(0)

if 'rhModelsDev' not in t:
    skip('batch169 not applied yet (no rhModelsDev marker)')

bal0 = balance(t)
lines = t.split(NL)

# ---- 1. 加 import(sync.Mutex / sync.withLock) ----
need_imports = [
    ('import kotlinx.coroutines.sync.Mutex', 'import kotlinx.coroutines.withContext'),
    ('import kotlinx.coroutines.sync.withLock', 'import kotlinx.coroutines.sync.Mutex'),
]
for imp, anchor in need_imports:
    if any(ln.strip() == imp for ln in lines):
        continue
    hits = [i for i, ln in enumerate(lines) if ln.strip() == anchor]
    if len(hits) != 1:
        # anchor 可能是刚要插入的 Mutex import —— 再试一次
        hits = [i for i, ln in enumerate(lines) if ln.strip() == anchor]
        if len(hits) != 1:
            skip('import anchor failed: ' + anchor + ' count=' + str(len(hits)))
    lines.insert(hits[0] + 1, imp)

# ---- 2. 加 mutex 字段(锚点: modelsDevFetchAttempted 字段) ----
f_hits = [i for i, ln in enumerate(lines) if 'private var modelsDevFetchAttempted = false' in ln]
if len(f_hits) != 1:
    skip('modelsDevFetchAttempted anchor count=' + str(len(f_hits)))
fi = f_hits[0]
d = lines[fi][:len(lines[fi]) - len(lines[fi].lstrip())]
lines.insert(fi + 1, d + 'private val modelsDevMutex = Mutex() // ' + MARK + ': 保护目录拉取')

# ---- 3. 改 queryModelsDev 的临界区 ----
# 锚点: if (!modelsDevFetchAttempted) {  (batch169 插入的)
old_hits = [i for i, ln in enumerate(lines) if ln.strip() == 'if (!modelsDevFetchAttempted) {']
if len(old_hits) != 1:
    skip('if(!modelsDevFetchAttempted) anchor count=' + str(len(old_hits)))
oi = old_hits[0]
d = lines[oi][:len(lines[oi]) - len(lines[oi].lstrip())]

# 找临界区结束(配平)
depth = 0
end = -1
for j in range(oi, len(lines)):
    depth += lines[j].count('{') - lines[j].count('}')
    if depth == 0 and j > oi:
        end = j
        break
if end < 0:
    skip('critical section closing not found')

old_block = lines[oi:end + 1]
# 校验: 应含 fetchModelsDevCatalog
if not any('fetchModelsDevCatalog()' in ln for ln in old_block):
    skip('critical section lacks fetchModelsDevCatalog')

new_block = [
    d + 'val catalog = modelsDevMutex.withLock { // ' + MARK,
    d + '    if (!modelsDevFetchAttempted) {',
    d + '        modelsDevFetchAttempted = true',
    d + '        modelsDevCatalog = fetchModelsDevCatalog()',
    d + '    }',
    d + '    modelsDevCatalog',
    d + '}',
]
lines[oi:end + 1] = new_block

out = NL.join(lines)
for need in [MARK, 'modelsDevMutex', 'withLock', 'val catalog = modelsDevMutex']:
    if need not in out:
        skip('selfcheck missing: ' + need)
if balance(out) != bal0:
    skip('balance changed')

(ROOT / F).write_text(out, encoding='utf-8')
print('::notice::batch170 OK - models.dev fetch now Mutex-guarded')

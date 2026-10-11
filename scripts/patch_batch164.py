#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch164: 综合修复(warn-only)

两个编译错误:
1. BackupArchiveRestorer.kt: Conflicting import 'JsonArray'/'JsonElement' is ambiguous
   —— batch163 加的 import 和别的会话已加的冲突。
   修法: 删掉 batch163 加的重复 import(只保留已有的)。

2. ReasoningPicker.kt: Unresolved reference 'onUpdateSqueezeToken'/'squeezeTokenEnabled'
   —— batch162 加了 UI 引用但没在 ReasoningButton/ReasoningPicker 签名里加参数。
   修法: 在签名里加 squeezeTokenEnabled: Boolean = false 和 onUpdateSqueezeToken: ((Boolean) -> Unit)? = null

warn-only: 任何锚点失败只 ::warning + 跳过,不阻塞构建(多人协作)。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhBatch164Fix'
BR = 'app/src/main/java/me/rerere/rikkahub/data/sync/webdav/BackupArchiveRestorer.kt'
RP = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ReasoningPicker.kt'


def warn(msg, path):
    print('::warning file=' + path + '::batch164 ' + str(msg)[:1200])


def skip(msg, path):
    warn(msg + ' — skipped (warn-only)', path)
    sys.stdout.flush()
    sys.exit(0)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


# ---- 1. BackupArchiveRestorer.kt: 删掉 batch163 加的重复 import ----
try:
    br = (ROOT / BR).read_text(encoding='utf-8')
except Exception as e:
    skip('read BackupArchiveRestorer failed: ' + str(e), BR)

# 删掉 batch163 加的重复 import(标记为 rhBackupRestorerFix)
lines = br.split(NL)
removed = 0
new_lines = []
for ln in lines:
    if 'rhBackupRestorerFix' in ln and ln.strip().startswith('import '):
        removed += 1
        continue
    new_lines.append(ln)

if removed > 0:
    out = NL.join(new_lines)
    (ROOT / BR).write_text(out, encoding='utf-8')
    print('batch164: BackupArchiveRestorer removed ' + str(removed) + ' duplicate imports')
else:
    print('batch164: BackupArchiveRestorer no duplicate imports found')

# ---- 2. ReasoningPicker.kt: 加 squeezeTokenEnabled/onUpdateSqueezeToken 参数 ----
try:
    rp = (ROOT / RP).read_text(encoding='utf-8')
except Exception as e:
    skip('read ReasoningPicker failed: ' + str(e), RP)

if MARK in rp:
    print('batch164: ReasoningPicker already applied')
else:
    lines = rp.split(NL)
    bal0 = balance(rp)
    changed = 0

    # 在 ReasoningButton 签名里加参数(在 onUpdateReasoningLevel 后)
    for i, ln in enumerate(lines):
        if 'onUpdateReasoningLevel: (ReasoningLevel) -> Unit,' in ln.strip():
            d = ind(lines[i])
            lines.insert(i + 1, d + 'squeezeTokenEnabled: Boolean = false, // ' + MARK)
            lines.insert(i + 2, d + 'onUpdateSqueezeToken: ((Boolean) -> Unit)? = null, // ' + MARK)
            changed += 1
            break

    # 在 ReasoningPicker 签名里也加(在 onUpdateReasoningLevel 后)
    found_picker = False
    for i, ln in enumerate(lines):
        if 'fun ReasoningPicker(' in ln:
            # 往后找 onUpdateReasoningLevel
            for j in range(i, min(i + 12, len(lines))):
                if 'onUpdateReasoningLevel: (ReasoningLevel) -> Unit,' in lines[j].strip():
                    d = ind(lines[j])
                    lines.insert(j + 1, d + 'squeezeTokenEnabled: Boolean = false, // ' + MARK)
                    lines.insert(j + 2, d + 'onUpdateSqueezeToken: ((Boolean) -> Unit)? = null, // ' + MARK)
                    changed += 1
                    found_picker = True
                    break
            break

    if not found_picker:
        skip('ReasoningPicker signature anchor not found', RP)

    out = NL.join(lines)
    if MARK not in out or balance(out) != bal0:
        skip('selfcheck failed', RP)
    (ROOT / RP).write_text(out, encoding='utf-8')
    print('batch164: ReasoningPicker params added (' + str(changed) + ' signatures)')

print('batch164: OK')

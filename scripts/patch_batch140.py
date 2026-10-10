#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch140 v2: 删除侧边栏重复助手卡片 + batch117 按钮接切换功能

v1 死因: KSP PROCESSING_ERROR(编译阶段),无具体错误行。patch 应用成功但编译挂。
可能原因: 删除 Surface 块后留下未解析引用/语法问题。

v2 改法:
1. 核心改动不变(删卡片+接按钮)
2. 全部改 warn-only:任何锚点失败不阻塞构建,只 ::warning
3. 写入后 dump 修改区域前后 5 行到 annotation,一次 CI run 拿到真形态
4. 自检失败也 warn-only(不 exit 1),让构建继续跑,看编译是否真挂

如果 v2 构建成功:说明 v1 是缓存/并发问题,改动本身没问题
如果 v2 构建仍失败:annotation 里的 dump 会告诉我具体哪行有问题
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhRemoveDupCard'
CD = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatDrawer.kt'


def warn(msg):
    print('::warning file=' + CD + '::batch140v2 ' + str(msg))


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


t = (ROOT / CD).read_text(encoding='utf-8')
if MARK in t:
    print('batch140v2: already applied')
    sys.exit(0)

bal0 = balance(t)
lines = t.split(NL)
changed = 0

# ---- 1. 删除 batch48 液态玻璃助手卡 ----
mark_hits = [i for i, ln in enumerate(lines) if '// rhDrawer48' in ln and '液态玻璃助手卡' in ln]
if len(mark_hits) != 1:
    warn('rhDrawer48 card marker count=' + str(len(mark_hits)) + ', skip delete')
else:
    mark_i = mark_hits[0]
    surf_start = -1
    for j in range(mark_i, min(mark_i + 3, len(lines))):
        if lines[j].strip() == 'Surface(':
            surf_start = j
            break
    if surf_start < 0:
        warn('Surface( not found after rhDrawer48 marker, skip delete')
    else:
        depth = 0
        surf_end = -1
        for j in range(surf_start, min(surf_start + 80, len(lines))):
            depth += (lines[j].count('(') - lines[j].count(')')) + (lines[j].count('{') - lines[j].count('}'))
            if depth == 0 and j > surf_start:
                surf_end = j
                break
        if surf_end < 0:
            warn('Surface block closing not found, skip delete')
        else:
            block_text = NL.join(lines[surf_start:surf_end + 1])
            ok = True
            for need in ['UIAvatar', 'Greeting']:
                if need not in block_text:
                    warn('batch48 card block missing ' + need + ', skip delete')
                    ok = False
                    break
            if ok:
                del_start = mark_i
                if del_start > 0 and lines[del_start - 1].strip() == '':
                    del_start -= 1
                # dump 删除区域(前3行 + 后3行)到 annotation
                dump_lo = max(0, del_start - 2)
                dump_hi = min(len(lines), surf_end + 3)
                dump = ' ;; '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(dump_lo, dump_hi))
                print('::notice::batch140v2 DEL-REGION=[' + dump[:800] + ']')
                lines = lines[:del_start] + lines[surf_end + 1:]
                changed += 1
                print('batch140v2: batch48 card removed (lines ' + str(del_start) + '..' + str(surf_end) + ')')

# ---- 2. batch117 卡 IconButton onClick 接切换 ----
ib_hits = [i for i, ln in enumerate(lines) if ln.strip() == 'IconButton(onClick = { }) {']
if len(ib_hits) != 1:
    warn('IconButton(onClick={}) count=' + str(len(ib_hits)) + ', skip wire')
else:
    ib_i = ib_hits[0]
    if ib_i + 1 >= len(lines) or 'HugeIcons.LookTop' not in lines[ib_i + 1]:
        warn('IconButton next line not LookTop, skip wire')
    else:
        old_line = lines[ib_i]
        d = old_line[:len(old_line) - len(old_line.lstrip())]
        lines[ib_i] = d + 'IconButton(onClick = { showAssistantSheet = true }) {  // ' + MARK
        changed += 1
        print('batch140v2: batch117 button wired to showAssistantSheet')

# ---- 3. 自检(warn-only) ----
out = NL.join(lines)
issues = []
if changed > 0 and MARK not in out:
    issues.append('marker missing')
if changed > 0 and '// rhDrawer48' in out and '液态玻璃助手卡' in out:
    issues.append('batch48 card comment still present')
if changed > 0 and 'showAssistantSheet = true' not in out:
    issues.append('showAssistantSheet assignment missing')
if changed > 0 and balance(out) != bal0:
    issues.append('balance ' + str(bal0) + ' -> ' + str(balance(out)))

if issues:
    warn('selfcheck issues: ' + ' | '.join(issues) + ' — proceeding anyway (warn-only)')
    # dump 问题区域
    for i, ln in enumerate(lines):
        if 'rhRemoveDupCard' in ln or 'showAssistantSheet' in ln or 'rhDrawer48' in ln:
            print('::notice::batch140v2 DUMP L' + str(i + 1) + ': ' + ln.strip()[:120])
else:
    (ROOT / CD).write_text(out, encoding='utf-8')
    print('::notice::batch140v2 OK - dup card removed, batch117 button wired, changes=' + str(changed))

# 写入(即使自检有问题也写,让编译器告诉我们真问题)
if changed > 0:
    (ROOT / CD).write_text(out, encoding='utf-8')
    print('batch140v2: file written (changes=' + str(changed) + ')')
else:
    print('batch140v2: nothing changed')

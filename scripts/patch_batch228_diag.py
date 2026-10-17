#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch228_diag: 工具链真形态只读诊断(不改任何文件, 恒 exit 0)

目的: 为「工具调用行 AI 生成显示文案」功能定位注入点
 1. ChatService.kt      tools buildList 声明行 / 配平收尾行 / 收尾后 25 行(下游使用)
 2. GenerationHandler.kt toolsInternal / buildMemoryTools / val tools 命中 + 上下文
 3. ChatMessageTools.kt  renderer.title / resolve 调用点
 4. scripts/*.py        同文件冲突扫描(ToolUI / ChatMessageTools / GenerationHandler)

输出走 ::error 通道(warning 通道每步 10 条已满, batch221/222 惯例)
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)

CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
GH = 'app/src/main/java/me/rerere/rikkahub/data/ai/GenerationHandler.kt'
CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageTools.kt'


def emit(tag, body):
    msg = str(tag) + ' || ' + str(body)
    print('::error::' + msg[:1450])
    sys.stdout.flush()


def read_lines(path):
    return (ROOT / path).read_text(encoding='utf-8').split(NL)


def seg(lines, lo, hi):
    out = []
    for j in range(max(0, lo), min(len(lines), hi)):
        out.append('L' + str(j + 1) + ':' + lines[j].strip()[:80])
    return ' ;; '.join(out)


def scan_block_end(lines, start):
    depth = 0
    started = False
    for j in range(start, len(lines)):
        for ch in lines[j]:
            if ch == '{':
                depth += 1
                started = True
            elif ch == '}':
                depth -= 1
        if started and depth <= 0:
            return j
    return -1


# ============ 1. ChatService.kt: tools buildList ============
try:
    lines = read_lines(CS)
    decl = -1
    for i, ln in enumerate(lines):
        if 'tools = buildList' in ln:
            decl = i
            break
    if decl < 0:
        for i, ln in enumerate(lines):
            if 'tools' in ln and 'buildList' in ln:
                decl = i
                break
    if decl < 0:
        hits = [i + 1 for i, ln in enumerate(lines) if 'val tools' in ln][:20]
        emit('diag-CS', 'no buildList decl; val tools hits=' + str(hits))
    else:
        end = scan_block_end(lines, decl)
        emit('diag-CS-decl', seg(lines, decl, decl + 3))
        if end < 0:
            emit('diag-CS-end', 'block end NOT FOUND from L' + str(decl + 1))
        else:
            emit('diag-CS-end', seg(lines, end - 2, end + 1))
            emit('diag-CS-use', seg(lines, end + 1, end + 26))
except Exception as e:
    emit('diag-CS-err', str(e))

# ============ 2. GenerationHandler.kt ============
try:
    lines = read_lines(GH)
    hits = [i for i, ln in enumerate(lines)
            if ('toolsInternal' in ln) or ('buildMemoryTools' in ln) or ('val tools' in ln)]
    emit('diag-GH-hits', 'total=' + str(len(lines)) + ' hits=' + str([h + 1 for h in hits][:30]))
    shown = 0
    lasti = -40
    for h in hits:
        if shown >= 2:
            break
        if h < lasti + 30:
            continue
        emit('diag-GH-ctx-L' + str(h + 1), seg(lines, h - 6, h + 20))
        shown += 1
        lasti = h
except Exception as e:
    emit('diag-GH-err', str(e))

# ============ 3. ChatMessageTools.kt: title 调用点 ============
try:
    lines = read_lines(CM)
    hits = [i for i, ln in enumerate(lines) if '.title(' in ln or 'resolve(' in ln]
    emit('diag-CM-hits', 'hits=' + str([h + 1 for h in hits][:20]))
    if hits:
        emit('diag-CM-ctx', seg(lines, hits[0] - 6, hits[0] + 6))
except Exception as e:
    emit('diag-CM-err', str(e))

# ============ 4. scripts 同文件冲突扫描 ============
try:
    sdir = ROOT / 'scripts'
    conflict = []
    for p in sorted(sdir.glob('*.py')):
        t = p.read_text(encoding='utf-8', errors='replace')
        if ('ToolUI' in t) or ('ChatMessageTools' in t) or ('GenerationHandler' in t):
            conflict.append(p.name)
    emit('diag-conflict', 'ToolUI/CM/GH touched by: ' + (', '.join(conflict) if conflict else 'NONE'))
except Exception as e:
    emit('diag-conflict-err', str(e))

print('batch228_diag: done')
sys.exit(0)

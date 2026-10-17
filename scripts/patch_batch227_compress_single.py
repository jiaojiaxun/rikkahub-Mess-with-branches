#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch227 v2: 压缩改单请求 —— 外科手术式三处行编辑（覆盖 v1）

v1 教训: 用「注释行 + while 深度扫描」做整段替换, 切进了别的函数, 编译红。
v2 改法: 只做三处单行级编辑, 不动函数结构, 不做大段替换。

三处编辑(都在 ChatService.generateAndStoreCompaction 内):
  1. 分块取消: `val fullSourceGroups = ContextCompactionPlanner.partitionSources(...)`(4行)
     → `val fullSourceGroups = listOf(fullSources)` —— 全部内容一组, compressGroups 只发一次请求。
  2. 输出预算: `modelSummaryTargetTokens.coerceAtMost(COMPACTION_MAX_REQUEST_OUTPUT_TOKENS)`
     → `modelSummaryTargetTokens` —— 直接用用户输入的目标值(targetTokens), 不再被 16384 截。
  3. 单请求超时: `withTimeout(COMPACTION_REQUEST_TIMEOUT_MS)`(3min)
     → `withTimeout(COMPACTION_TOTAL_TIMEOUT_MS)`(8min) —— 单请求等它完整输出。

效果: compressGroups 拿到单组 → 一次 generateText 请求 → 归并循环一轮即出。
幂等 marker rhSingleCompress; 三处锚点均要求唯一; warn-only。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch227'
MARK = 'rhSingleCompress'
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'

E1_ANCHOR = '        val fullSourceGroups = ContextCompactionPlanner.partitionSources('
E1_TAIL = ('            sources = fullSources,', '            maxInputTokens = mapInputBudgetTokens,', '        )')
E1_NEW = '        val fullSourceGroups = listOf(fullSources) // ' + MARK + ': 单请求不分块'

E2_OLD = 'modelSummaryTargetTokens.coerceAtMost(COMPACTION_MAX_REQUEST_OUTPUT_TOKENS)'
E2_NEW = 'modelSummaryTargetTokens // ' + MARK + ': 预算=目标值'

E3_OLD = 'withTimeout(COMPACTION_REQUEST_TIMEOUT_MS)'
E3_NEW = 'withTimeout(COMPACTION_TOTAL_TIMEOUT_MS) // ' + MARK + ': 单请求放宽到总量超时'

applied = []
skipped = []


def joinlist(items):
    t = ''
    for i, s in enumerate(items):
        if i > 0:
            t += ','
        t += s
    return t


def read(path):
    p = ROOT / path
    if not p.exists():
        return None
    try:
        return p.read_text(encoding='utf-8')
    except Exception:
        return None


def write(path, text):
    p = ROOT / path
    if not p.parent.exists():
        p.parent.mkdir(parents=True)
    p.write_text(text, encoding='utf-8')


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def main():
    src = read(CS)
    if src is None:
        skipped.append('missing')
        print('::error::' + BATCH + ' SKIP missing')
        return
    if MARK in src:
        applied.append('exists')
        print('::error::' + BATCH + ' OK already')
        return
    lines = src.split(NL)
    bal0 = balance(src)

    # Edit 1: 分块 → 单组
    idx = -1
    for i, ln in enumerate(lines):
        if ln == E1_ANCHOR:
            idx = i
            break
    if idx < 0:
        skipped.append('e1-anchor-miss')
        print('::error::' + BATCH + ' SKIP e1-anchor-miss')
        return
    tail_ok = True
    for k in range(3):
        if idx + 1 + k >= len(lines) or lines[idx + 1 + k] != E1_TAIL[k]:
            tail_ok = False
            break
    if not tail_ok:
        skipped.append('e1-tail-mismatch')
        print('::error::' + BATCH + ' SKIP e1-tail-mismatch')
        return
    lines[idx:idx + 4] = [E1_NEW]

    # Edit 2: 输出预算
    src2 = NL.join(lines)
    if src2.count(E2_OLD) != 1:
        skipped.append('e2-count=' + str(src2.count(E2_OLD)))
        print('::error::' + BATCH + ' SKIP e2-count=' + str(src2.count(E2_OLD)))
        return
    src2 = src2.replace(E2_OLD, E2_NEW, 1)

    # Edit 3: 超时
    if src2.count(E3_OLD) != 1:
        skipped.append('e3-count=' + str(src2.count(E3_OLD)))
        print('::error::' + BATCH + ' SKIP e3-count=' + str(src2.count(E3_OLD)))
        return
    src2 = src2.replace(E3_OLD, E3_NEW, 1)

    out = src2
    if balance(out) != bal0:
        skipped.append('balance')
        print('::error::' + BATCH + ' SKIP balance')
        return
    for need in ('listOf(fullSources)', MARK):
        if need not in out:
            skipped.append('selfcheck:' + need)
            print('::error::' + BATCH + ' SKIP selfcheck ' + need)
            return
    write(CS, out)
    applied.append('e1,e2,e3')
    print('::error::' + BATCH + ' OK applied single-request compression (e1 single-group, e2 budget=target, e3 timeout=8min)')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::error::' + BATCH + ' crashed: ' + str(exc)[:300])
    sys.exit(0)
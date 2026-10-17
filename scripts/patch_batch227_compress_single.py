#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch227 v3: 压缩改单请求 —— 修 v1/v2 的同一个 bug

v1/v2 编译红的根因(读 CI 真形态发现): compressSources 在 CI 里是 batch3 加的流式版本
  `val summaryText = withTimeout(COMPACTION_REQUEST_TIMEOUT_MS) { ...流式+兜底... }`。
  我的超时编辑把行尾注释 `// rhSingleCompress: ...` 加在 `withTimeout(...) {` 后面,
  把那个 `{` 注释掉了 → withTimeout 没了函数体块 → "Missing return statement"/
  "Expecting member declaration"。v1/v2 是同一个注释 bug, 不是锚点问题。

v3: E3 去掉行尾注释(不碰 `{`)。E1/E2 已在 run424 验证落地, 保持不动。
  1. 分块 partitionSources → listOf(fullSources) 一组(单请求)
  2. 输出预算 coerceAtMost(16384) → modelSummaryTargetTokens(=用户目标值)
  3. 单请求超时 3min → 8min(等完整输出) —— 不带行尾注释

幂等 marker rhSingleCompress(由 E1/E2 行尾注释提供); 三处锚点要求唯一; warn-only; 括号差值断言。
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
E3_NEW = 'withTimeout(COMPACTION_TOTAL_TIMEOUT_MS)'

applied = []
skipped = []


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

    src2 = NL.join(lines)

    # Edit 2: 输出预算=目标值
    if src2.count(E2_OLD) != 1:
        skipped.append('e2-count=' + str(src2.count(E2_OLD)))
        print('::error::' + BATCH + ' SKIP e2-count=' + str(src2.count(E2_OLD)))
        return
    src2 = src2.replace(E2_OLD, E2_NEW, 1)

    # Edit 3: 超时放宽(不带行尾注释, 不碰 withTimeout 的 {)
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
    for need in ('listOf(fullSources)', 'withTimeout(COMPACTION_TOTAL_TIMEOUT_MS) {', MARK):
        if need not in out:
            skipped.append('selfcheck:' + need)
            print('::error::' + BATCH + ' SKIP selfcheck ' + need)
            return
    write(CS, out)
    applied.append('e1,e2,e3')
    print('::error::' + BATCH + ' OK applied single-request compression (v3: fixed comment-eats-brace bug)')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::error::' + BATCH + ' crashed: ' + str(exc)[:300])
    sys.exit(0)
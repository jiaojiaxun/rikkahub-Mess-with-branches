#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch227: 压缩改单请求 —— 砍掉切块并发/多轮归并，一次请求等它完整输出

用户实测(请求日志): 手动点压缩 → 4 次并发请求(每个 max_tokens=256) → 一半直接消失。
根因: generateAndStoreCompaction 的 map-reduce 把一次压缩拆成多个并发小请求 + 多轮归并,
      并发批里一个超时/失败就 coroutineScope 连坐取消整批 → 用户看到"重复请求又取消"。

用户要求: 只跑一个请求, 一直等到完整输出, 不做任何其他操作; 输出预算 = 用户输入的目标值。

修法(替换 generateAndStoreCompaction 的中间段, 不动开头/结尾):
  删掉 [// Ordinary compression is a map pass...] 注释行 → while(finalSummary==null)循环结束
  这一整段(fullSources/partition/compressGroups/reduction 循环), 换成:
    val fullSource = messagesToCompress.map(sourceText).joinToString
    val finalSummary = compressSources(listOf(fullSource), targetTokens)   // maxTokens=targetTokens
  结尾段(boundary 校验 + ConversationCompaction 构造 + upsert)原样保留, 它只用 finalSummary
  /toolDigest/rawContextRetentionReport —— 被删的变量(sourceGroups/usingMapPreviews/compressGroups
  /reductionPasses)结尾都不引用, 已逐一核实。

另把 compressSources 的 withTimeout 从 COMPACTION_REQUEST_TIMEOUT_MS(3min) 放宽到
  COMPACTION_TOTAL_TIMEOUT_MS(8min) —— 单请求等它完整输出, 不再被 3 分钟砍掉。

锚点: start='// Ordinary compression is a map pass' 注释行; end=while(finalSummary==null){}
  用括号深度扫描定位其收尾 }; 替换区间 [startLine, whileEndLine]。
幂等 marker rhSingleCompress; warn-only; 括号差值断言。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch227'
MARK = 'rhSingleCompress'
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'

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

    # ① 删 map-reduce 段: 从 "// Ordinary compression is a map pass" 注释行
    #    到 "while (finalSummary == null) {" 的收尾 }。
    start = -1
    for i, ln in enumerate(lines):
        if ln.strip().startswith('// Ordinary compression is a map pass'):
            start = i
            break
    if start < 0:
        skipped.append('start-anchor-miss')
        print('::error::' + BATCH + ' SKIP start-anchor-miss')
        return
    # 找 while(finalSummary==null) 行
    wline = -1
    for j in range(start, min(start + 120, len(lines))):
        if lines[j].strip().startswith('while (finalSummary == null)'):
            wline = j
            break
    if wline < 0:
        skipped.append('while-anchor-miss')
        print('::error::' + BATCH + ' SKIP while-anchor-miss')
        return
    # 深度扫描找 while 的收尾 }
    depth = 0
    wend = -1
    began = False
    for j in range(wline, len(lines)):
        for ch in lines[j]:
            if ch == '{':
                depth += 1
                began = True
            elif ch == '}':
                depth -= 1
        if began and depth == 0:
            wend = j
            break
    if wend < 0:
        skipped.append('while-end-miss')
        print('::error::' + BATCH + ' SKIP while-end-miss')
        return

    new_block = [
        '        // [batch227] ' + MARK + ': 单请求压缩 —— 不切块/不并发/不多轮, 一次请求等完整输出。',
        '        // 输出预算直接用用户输入的目标值(targetTokens)。',
        '        val rhCombinedSource = messagesToCompress',
        '            .map(ContextCompactionPlanner::sourceText)',
        '            .joinToString("\\n\\n")',
        '        check(rhCombinedSource.isNotBlank()) { "No usable messages selected for compression" }',
        '        Log.i(TAG, "Compaction single-request: model=" + model.modelId + ", targetTokens=" + targetTokens)',
        '        val finalSummary = compressSources(listOf(rhCombinedSource), targetTokens)',
    ]
    lines[start:wend + 1] = new_block
    out = concat = None
    out = NL.join(lines)

    # ② compressSources 超时放宽: 3min → 8min(单请求等完整输出)
    if 'withTimeout(COMPACTION_REQUEST_TIMEOUT_MS)' in out:
        out = out.replace(
            'withTimeout(COMPACTION_REQUEST_TIMEOUT_MS)',
            'withTimeout(COMPACTION_TOTAL_TIMEOUT_MS) // ' + MARK + ': 单请求放宽到总量超时',
            1,
        )
    else:
        skipped.append('timeout-anchor-miss')

    if balance(out) != bal0:
        skipped.append('balance')
        print('::error::' + BATCH + ' SKIP balance')
        return
    for need in ('val finalSummary = compressSources(', MARK):
        if need not in out:
            skipped.append('selfcheck:' + need)
            print('::error::' + BATCH + ' SKIP selfcheck ' + need)
            return
    # 被删变量不得在残留代码中被引用
    for gone in ('compressGroups(', 'var reductionPasses', 'fullSourceGroups', 'var sourceGroups'):
        if gone in out:
            skipped.append('leftover-ref:' + gone)
            print('::error::' + BATCH + ' SKIP leftover-ref ' + gone)
            return
    write(CS, out)
    applied.append('single-request')
    print('::error::' + BATCH + ' OK applied single-request compression, timeout widened')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::error::' + BATCH + ' crashed: ' + str(exc)[:300])
    sys.exit(0)
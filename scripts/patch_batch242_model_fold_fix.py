#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch242: 修复「选择模型」弹窗分组折叠失效（折叠箭头点了列表不收起）

根因（batch124 回归）: batch12 的 collapse-by-provider 依赖 collapsedProviderIds 过滤
  可见模型；batch124 重写 searchFilteredModelsByProvider（它是 LazyColumn items 的
  实际数据源）时只保留了搜索条件，丢掉了 collapsedProviderIds 过滤
  -> 箭头 glyph 会翻转，但模型列表不收起。typeFilteredModelsByProvider（带折叠过滤）
  只剩初始滚动定位在用。

修法: 把折叠过滤补回 searchFilteredModelsByProvider，remember key 增加
  collapsedProviderIds（与 typeFilteredModelsByProvider 保持一致）。
锚点按 CI 真形态（snapshot 实读，8 空格缩进）；幂等 marker rhModelFoldFix；
warn-only；括号差值断言；失败 dump 现场行。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
ML = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ModelList.kt'
MARK = 'rhModelFoldFix'


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def fail(msg, lines=None, around=-1):
    body = 'batch242 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        body = body + ' || ctx: ' + ' ;; '.join('L' + str(i + 1) + ':' + lines[i].strip()[:120] for i in range(lo, hi))
    print('::error file=' + ML + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


def main():
    p = ROOT / ML
    if not p.exists():
        fail('ModelList.kt not found')
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        print('::error::batch242 already applied (marker present)')
        sys.exit(0)

    lines = t.split(NL)
    hits = [i for i, ln in enumerate(lines) if ln.strip().startswith('val searchFilteredModelsByProvider')]
    if len(hits) != 1:
        fail('anchor count=' + str(len(hits)), lines, hits[0] if hits else -1)
    b_i = hits[0]
    d = lines[b_i][:len(lines[b_i]) - len(lines[b_i].lstrip())]

    depth = 0
    seen_brace = False
    b_end = -1
    for j in range(b_i, min(b_i + 30, len(lines))):
        depth += lines[j].count('{') - lines[j].count('}')
        if '{' in lines[j]:
            seen_brace = True
        if seen_brace and depth == 0:
            b_end = j
            break
    if b_end < 0:
        fail('brace scan failed from L' + str(b_i + 1), lines, b_i)
    block = NL.join(lines[b_i:b_end + 1])
    if 'rhProviderSearchExtras(provider)' not in block or 'rhQuery' not in block:
        fail('block shape unexpected; dump=' + block[:400], lines, b_i)
    if 'collapsedProviderIds' in block:
        print('::error::batch242 block already collapse-aware; nothing to do')
        sys.exit(0)

    new_block = [
        d + 'val searchFilteredModelsByProvider = remember(providers, modelType, searchKeywords, collapsedProviderIds) {',
        d + '    val rhQuery = searchKeywords.trim()',
        d + '    providers.associate { provider ->',
        d + '        val rhProviderHit = rhQuery.isNotEmpty() && rhProviderSearchExtras(provider).contains(rhQuery, true)',
        d + '        provider.id to provider.models.fastFilter {',
        d + '            it.matchesPickerType(modelType) && (rhProviderHit || it.displayName.contains(rhQuery, true))',
        d + '        }.let { if (provider.id.toString() in collapsedProviderIds) emptyList() else it }',
        d + '    }',
        d + '} // ' + MARK + ': 折叠状态重新参与 items 过滤（batch124 重写时丢失）',
    ]
    out = NL.join(lines[:b_i] + new_block + lines[b_end + 1:])

    if balance(out) != balance(t):
        fail('balance mismatch ' + str(balance(t)) + ' -> ' + str(balance(out)), lines, b_i)
    for need in [MARK, 'remember(providers, modelType, searchKeywords, collapsedProviderIds)',
                 'in collapsedProviderIds) emptyList() else it }', 'rhProviderSearchExtras(provider)',
                 'it.matchesPickerType(modelType) && (rhProviderHit || it.displayName.contains(rhQuery, true))']:
        if need not in out:
            fail('selfcheck missing: ' + need, lines, b_i)
    if 'rhModelSearch' not in out:
        fail('batch124 marker comment lost', lines, b_i)

    p.write_text(out, encoding='utf-8')
    print('::error::batch242 OK fold filter restored @L' + str(b_i + 1) + ' keys+collapsed, lines=' + str(len(new_block)))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::error::batch242 crashed: ' + str(exc)[:300])
    sys.exit(0)
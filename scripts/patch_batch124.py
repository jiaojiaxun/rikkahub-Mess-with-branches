#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch124 v2: 模型选择器搜索扩展——同时匹配 模型名 / 供应商名 / API Key / BaseUrl

v1 死因: search block anchor count=0 —— CI 形态下 ModelList.kt 的
val searchFilteredModelsByProvider = remember( 行被某个前置 patch 改了格式,
startswith 匹配不到。

v2 修法:
1. 搜索从行级 startswith 改为 contains('searchFilteredModelsByProvider')
   (tolerant: 不管行前缀/缩进/额外参数,只要变量名在就能匹配)
2. 找不到时 dump 包含 search/Filtered/remember/keywords 的行到 annotation,
   warn-only 跳过(不阻塞构建),一次 CI run 拿到真形态,二次修准。
3. helper 插入(formatModelContext 锚点)v1 已成功,保持不变。

其余逻辑不变(ProviderSetting 扫描+helper 构建+block 替换)。
'''
from pathlib import Path
import re
import sys

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhModelSearch'
ML = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ModelList.kt'
PS = 'ai/src/main/java/me/rerere/ai/provider/ProviderSetting.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch124v2 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 4)
        hi = min(len(lines), around + 5)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:100] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + ML + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def find_subclasses(src):
    sealed_at = src.find('sealed class ProviderSetting')
    if sealed_at < 0:
        return []
    res = []
    for m in re.finditer(r'data class (\w+)\s*\(', src):
        if m.start() < sealed_at:
            continue
        i = m.end()
        depth = 1
        while i < len(src) and depth > 0:
            c = src[i]
            if c == '(':
                depth += 1
            elif c == ')':
                depth -= 1
            i += 1
        if depth != 0:
            continue
        params = src[m.end():i - 1]
        if re.match(r'\s*:\s*ProviderSetting\s*\(', src[i:i + 60]):
            res.append((m.group(1), params))
    return res


# ---- 0. scan ProviderSetting subclasses ----
ps_path = ROOT / PS
if not ps_path.exists():
    hit = None
    for p in ROOT.rglob('ProviderSetting.kt'):
        sp = str(p)
        if sp.startswith('build/') or '/build/' in sp:
            continue
        hit = p
        break
    if hit is None:
        fail('cannot locate ProviderSetting.kt')
    ps_path = hit

src = ps_path.read_text(encoding='utf-8', errors='ignore')
if 'sealed class ProviderSetting' not in src:
    fail('ProviderSetting.kt missing sealed class')

subs = find_subclasses(src)
print('::notice::batch124v2 nested subclasses = ' + str(len(subs)) + ' : ' + ','.join(n for n, _ in subs))

branches = []
seen = set()
for name, params in subs:
    if name in seen:
        continue
    parts = []
    if re.search(r'\bvar apiKey\b', params):
        parts.append('provider.apiKey')
    if re.search(r'\bvar baseUrl\b', params):
        parts.append('provider.baseUrl')
    if not parts:
        continue
    seen.add(name)
    sep = ' + ' + Q + ' ' + Q + ' + '
    branches.append('        is ProviderSetting.' + name + ' -> ' + sep.join(parts))

if not branches:
    print('::warning::batch124v2 no apiKey/baseUrl branches; fallback to toString()')
    helper = (
        '// ' + MARK + ': 搜索时把 供应商名 / API Key / BaseUrl 一起纳入匹配。' + NL +
        'private fun rhProviderSearchExtras(provider: ProviderSetting): String =' + NL +
        '    provider.name + ' + Q + ' ' + Q + ' + provider.toString()' + NL + NL
    )
else:
    helper = (
        '// ' + MARK + ': 搜索时把 供应商名 / API Key / BaseUrl 一起纳入匹配。' + NL +
        '// ProviderSetting 是 sealed class，apiKey/baseUrl 只挂在部分子类上，按实际子类提取。' + NL +
        'private fun rhProviderSearchExtras(provider: ProviderSetting): String {' + NL +
        '    val extras = when (provider) {' + NL +
        NL.join(branches) + NL +
        '        else -> ' + Q + Q + NL +
        '    }' + NL +
        '    return provider.name + ' + Q + ' ' + Q + ' + extras' + NL +
        '}' + NL + NL
    )

# ---- 1. read ModelList.kt ----
ml_path = ROOT / ML
if not ml_path.exists():
    fail('ModelList.kt not found')
t = ml_path.read_text(encoding='utf-8')

if MARK in t:
    print('batch124v2: already applied')
    sys.exit(0)

bal0 = balance(t)
lines = t.split(NL)

# ---- 2. insert helper before formatModelContext ----
ANCHOR_FMT = 'private fun formatModelContext'
fmt_hits = [i for i, ln in enumerate(lines) if ANCHOR_FMT in ln]
if len(fmt_hits) != 1:
    # warn-only: dump context, don't fail
    dump = ' ;; '.join('L' + str(i + 1) + ':' + lines[i].strip()[:80] for i in range(min(10, len(lines))))
    print('::warning::batch124v2 formatModelContext anchor count=' + str(len(fmt_hits)) + ' dump=[' + dump[:600] + ']')
    # skip helper insertion, still try block replacement
    helper_lines = []
else:
    fmt_i = fmt_hits[0]
    helper_lines = helper.split(NL)
    lines = lines[:fmt_i] + helper_lines + lines[fmt_i:]

# ---- 3. replace search block (v2: tolerant contains search + dump on miss) ----
# v2: search by contains instead of startswith
search_hits = [i for i, ln in enumerate(lines) if 'searchFilteredModelsByProvider' in ln]

if len(search_hits) == 0:
    # dump all lines containing search/Filtered/remember/keywords for diagnosis
    dump_lines = []
    for i, ln in enumerate(lines):
        low = ln.lower()
        if 'search' in low or 'filtered' in low or 'remember' in low or 'keywords' in low:
            dump_lines.append('L' + str(i + 1) + ':' + ln.strip()[:100])
    print('::notice::batch124v2 search anchor MISS; dump=[' + ' ;; '.join(dump_lines[:30]) + ']')
    print('::warning::batch124v2 searchFilteredModelsByProvider not found in CI form; skipped (warn-only)')
    # still write helper if inserted (harmless addition)
    if helper_lines:
        out = NL.join(lines)
        ml_path.write_text(out, encoding='utf-8')
    print('::notice::batch124v2 DONE (search skipped, helper ' + ('inserted' if helper_lines else 'skipped') + ')')
    sys.exit(0)

if len(search_hits) > 1:
    # multiple matches - dump them all
    dump = ' ;; '.join('L' + str(i + 1) + ':' + lines[i].strip()[:100] for i in search_hits[:10])
    print('::warning::batch124v2 search anchor count=' + str(len(search_hits)) + ' dump=[' + dump[:600] + ']')
    print('::notice::batch124v2 DONE (ambiguous, skipped)')
    if helper_lines:
        out = NL.join(lines)
        ml_path.write_text(out, encoding='utf-8')
    sys.exit(0)

b_i = search_hits[0]

# brace-scan to find block end
depth = 0
b_end = -1
for j in range(b_i, min(b_i + 30, len(lines))):
    depth += lines[j].count('{') - lines[j].count('}')
    if depth == 0 and j > b_i:
        b_end = j
        break

if b_end < 0:
    dump = ' ;; '.join('L' + str(i + 1) + ':' + lines[i].strip()[:100] for i in range(b_i, min(b_i + 15, len(lines))))
    print('::warning::batch124v2 brace scan failed from L' + str(b_i + 1) + ' dump=[' + dump[:600] + ']')
    if helper_lines:
        out = NL.join(lines)
        ml_path.write_text(out, encoding='utf-8')
    print('::notice::batch124v2 DONE (brace scan failed, skipped)')
    sys.exit(0)

block = NL.join(lines[b_i:b_end + 1])
if 'displayName.contains' not in block:
    dump = block[:300]
    print('::warning::batch124v2 block lacks displayName.contains; dump=[' + dump + ']')
    if helper_lines:
        out = NL.join(lines)
        ml_path.write_text(out, encoding='utf-8')
    print('::notice::batch124v2 DONE (block shape unexpected, skipped)')
    sys.exit(0)

d = lines[b_i][:len(lines[b_i]) - len(lines[b_i].lstrip())]
new_block = [
    d + '// ' + MARK + ': 搜索同时匹配 模型名 / 供应商名 / API Key / BaseUrl（原为只匹配模型名）',
    d + 'val searchFilteredModelsByProvider = remember(providers, modelType, searchKeywords) {',
    d + '    val rhQuery = searchKeywords.trim()',
    d + '    providers.associate { provider ->',
    d + '        val rhProviderHit = rhQuery.isNotEmpty() && rhProviderSearchExtras(provider).contains(rhQuery, true)',
    d + '        provider.id to provider.models.fastFilter {',
    d + '            it.matchesPickerType(modelType) && (rhProviderHit || it.displayName.contains(rhQuery, true))',
    d + '        }',
    d + '    }',
    d + '}',
]
lines = lines[:b_i] + new_block + lines[b_end + 1:]

out = NL.join(lines)

# selfchecks
for need in [MARK, 'rhProviderSearchExtras(provider)', 'val rhQuery = searchKeywords.trim()', 'rhProviderHit']:
    if need not in out:
        fail('selfcheck missing: ' + need)
if 'displayName.contains(searchKeywords, true)' in out:
    fail('old search condition still present')
for b in branches:
    if b not in out:
        fail('branch lost during write: ' + b.strip())
if balance(out) != bal0:
    fail('balance mismatch: ' + str(bal0) + ' -> ' + str(balance(out)))

ml_path.write_text(out, encoding='utf-8')

print('::notice::batch124v2 OK helper+block applied')
print('::notice::batch124v2 branches=[' + ' ;; '.join(b.strip() for b in branches) + ']')
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch124 v3: 模型选择器搜索扩展——同时匹配 模型名 / 供应商名 / API Key / BaseUrl

v1 死因: 锚点 'val searchFilteredModelsByProvider = remember(' startswith 匹配不到——
  CI 形态下该行被折行了: 'val searchFilteredModelsByProvider =' 在一行,
  'remember(providers, modelType, searchKeywords) {' 在下一行。
v2(当前版本): 已改为 warn-only(找不到时跳过不阻塞),但锚点没变,仍然匹配不到。

v3 修法(在 warn-only 基础上只改两处):
1. 锚点从 'val searchFilteredModelsByProvider = remember(' 改为
   'val searchFilteredModelsByProvider' —— 去掉 ' = remember(',
   只匹配定义行(不以使用处为锚),兼容折行。
2. brace-scan 加 seen_brace 标志——'val x =' 行没有 {,depth=0,
   不能立刻命中 depth==0,必须先看到 { 才开始算归零。
'''
import re
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhModelSearch'
ML = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ModelList.kt'
PS = 'ai/src/main/java/me/rerere/ai/provider/ProviderSetting.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch124v3 ' + str(msg)
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


# ---- 0. 扫描 ProviderSetting 子类,生成 apiKey/baseUrl 提取分支 ----
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
print('::notice::batch124v3 nested subclasses = ' + str(len(subs)) + ' : ' + ','.join(n for n, _ in subs))

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
    print('::warning::batch124v3 no apiKey/baseUrl branches; fallback to toString()')
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

# ---- 1. 读 ModelList.kt ----
ml_path = ROOT / ML
if not ml_path.exists():
    fail('ModelList.kt not found')
t = ml_path.read_text(encoding='utf-8')

if MARK in t:
    print('batch124v3: already applied')
    sys.exit(0)

bal0 = balance(t)
lines = t.split(NL)

# ---- 2. 在 formatModelContext 之前插入 helper ----
ANCHOR_FMT = 'private fun formatModelContext'
hits = [i for i, ln in enumerate(lines) if ANCHOR_FMT in ln]
if len(hits) != 1:
    print('::warning file=' + ML + '::batch124v3 formatModelContext anchor count=' + str(len(hits)) + ', skipping (model search extension inactive)')
    sys.exit(0)
fmt_i = hits[0]
helper_lines = helper.split(NL)
lines = lines[:fmt_i] + helper_lines + lines[fmt_i:]

# ---- 3. 替换搜索过滤块(v3: startswith('val searchFilteredModelsByProvider') + seen_brace) ----
# v3: 锚点只匹配定义行,不要求同行有 remember(兼容折行)
B_START = 'val searchFilteredModelsByProvider'
hits = [i for i, ln in enumerate(lines) if ln.strip().startswith(B_START)]
if len(hits) == 0:
    print('::warning file=' + ML + '::batch124v3 search block anchor not found (count=0); skipping model search extension (likely modified by another in-chain patch)')
    sys.exit(0)
if len(hits) > 1:
    # 使用处不会以 'val searchFilteredModelsByProvider' 开头——它们都是
    # 'val providerPositions = remember(...)' 或 'currentIndex += ...' 或 'items = ...'
    # 如果还是 >1,dump 出来看
    dump = ' ;; '.join('L' + str(i + 1) + ':' + lines[i].strip()[:100] for i in hits[:10])
    print('::warning file=' + ML + '::batch124v3 search anchor count=' + str(len(hits)) + ' dump=[' + dump[:600] + ']')
    sys.exit(0)
b_i = hits[0]
# v3: brace-scan 加 seen_brace——'val x =' 行可能没有 {,depth=0 不能立刻命中
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
    print('::warning file=' + ML + '::batch124v3 brace scan failed from L' + str(b_i + 1) + ' (warn-only skip)')
    sys.exit(0)
block = NL.join(lines[b_i:b_end + 1])
if 'displayName.contains' not in block:
    print('::warning file=' + ML + '::batch124v3 block lacks displayName.contains; dump=[' + block[:300] + ']')
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

# ---- 4. 自检 ----
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

print('::notice::batch124v3 OK helper+block applied')
print('::notice::batch124v3 branches=[' + ' ;; '.join(b.strip() for b in branches) + ']')
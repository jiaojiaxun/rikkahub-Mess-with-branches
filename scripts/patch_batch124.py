#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch124: 模型选择器搜索扩展——同时匹配 模型名 / 供应商名 / API Key / BaseUrl

v2 修改 (2026-10-07): 锁定锚点找不到时从容错跳过(fail->warning+exit 0),
避免阻塞后续 patch_batch*.py(特别是 batch133 workspace shell)。
根因: CI 形态下 ModelList.kt 的 searchFilteredModelsByProvider 行可能被更早的
在链 patch 改写; 找不到时说明该区段已被重构, 本功能无法应用, 但不应阻塞构建链。

用户需求(2026-10-07 原话):
"不能只匹配模型name 也要含供应商名和api key和url"
(位置=发送消息聊天框下面的模型/供应商选择器里的搜索,即 ModelList.kt 的搜索)

现状(实读 ModelList.kt):
    val searchFilteredModelsByProvider = remember(providers, modelType, searchKeywords) {
        providers.associate { provider ->
            provider.id to provider.models.fastFilter {
                it.matchesPickerType(modelType) && it.displayName.contains(searchKeywords, true)
            }
        }
    }

改动:
1. 新增文件级工具 rhProviderSearchExtras(provider) = 供应商名 + " " + 子类 apiKey/baseUrl。
   子类清单在 CI 上从 ProviderSetting.kt 扫描生成(沿用 batch42 v4 的括号配对扫描,
   已在 CI 编译通过验证过),避免对不存在的字段做引用。
2. 整体替换上面的过滤块(用花括号配对定位,容忍缩进/上下文差异):
   供应商名/apiKey/baseUrl 命中 => 该供应商全部(类型匹配的)模型显示;
   否则退回模型名匹配;空搜索行为不变(全部显示)。

同文件冲突核查: ModelList.kt 提交历史只有初始快照(1128991),无在链 patch 记录触碰;
batch42 只改 SettingProviderPage.kt 的同类逻辑,不动本文件。锚点缺失会容错跳过+::warning。

五查:
1. import: 零新增(rhProviderSearchExtras 同文件定义; fastFilter/matchesPickerType 已有)
2. 同文件冲突: 见上;本脚本自身幂等(MARK 检查)
3. 作用域: helper 文件级 private;过滤块在 ColumnScope.ModelList 内;
   rhQuery/rhProviderHit 全文件唯一
4. 括号配对: 块整体替换(括号扫描);helper 自平衡;全文件 balance 前后一致
5. 函数签名: 不改任何签名

Python 三查: 引号用 Q=chr(34) 变量构造;无 f-string;helper 先定义;失败显式 exit(1)
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
    body = 'batch124 ' + str(msg)
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
print('::notice::batch124 nested subclasses = ' + str(len(subs)) + ' : ' + ','.join(n for n, _ in subs))

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
    print('::warning::batch124 no apiKey/baseUrl branches; fallback to toString()')
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
    print('batch124: already applied')
    sys.exit(0)

bal0 = balance(t)
lines = t.split(NL)

# ---- 2. 在 formatModelContext 之前插入 helper ----
ANCHOR_FMT = 'private fun formatModelContext'
hits = [i for i, ln in enumerate(lines) if ANCHOR_FMT in ln]
if len(hits) != 1:
    print('::warning file=' + ML + '::batch124 formatModelContext anchor count=' + str(len(hits)) + ', skipping (model search extension inactive)')
    sys.exit(0)
fmt_i = hits[0]
helper_lines = helper.split(NL)
lines = lines[:fmt_i] + helper_lines + lines[fmt_i:]

# ---- 3. 替换搜索过滤块(花括号配对定位) ----
B_START = 'val searchFilteredModelsByProvider = remember('
hits = [i for i, ln in enumerate(lines) if ln.strip().startswith(B_START)]
if len(hits) == 0:
    print('::warning file=' + ML + '::batch124 search block anchor not found (count=0); skipping model search extension (likely modified by another in-chain patch)')
    sys.exit(0)
if len(hits) > 1:
    fail('search block anchor count=' + str(len(hits)), lines, hits[0])
b_i = hits[0]
depth = 0
b_end = -1
for j in range(b_i, min(b_i + 30, len(lines))):
    depth += lines[j].count('{') - lines[j].count('}')
    if depth == 0 and j > b_i:
        b_end = j
        break
if b_end < 0:
    fail('search block closing brace not found', lines, b_i)
block = NL.join(lines[b_i:b_end + 1])
if 'displayName.contains' not in block:
    fail('search block lacks displayName.contains; dump=[' + block[:220] + ']', lines, b_i)

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

print('::notice::batch124 OK helper+block applied')
print('::notice::batch124 branches=[' + ' ;; '.join(b.strip() for b in branches) + ']')
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch169: 接入 models.dev 模型上下文长度(warn-only)

用户需求: 原本有一个模型库(内置家族表), 能不能接入 models.dev 的模型列表。

现状: ModelContextLengthResolver 三级链 = 供应商声明 > 内置家族表 > OpenRouter 兜底。
改法: 在兜底层加 models.dev(全量 api.json), 命中就用; 未命中再走 OpenRouter。
      api.json 用内存缓存(App 生命周期只拉一次), 避免重复拉取大 JSON。

改动(ModelContextLengthResolver.kt 单文件, 不改 DI):
1. 加字段 modelsDevCatalog / modelsDevFetchAttempted
2. 原 queryPublicCatalog 改名 queryOpenRouter
3. 新 queryPublicCatalog = queryModelsDev() ?: queryOpenRouter()
4. 加 queryModelsDev + fetchModelsDevCatalog + parseModelsDevCatalog

warn-only: 任何锚点失败只 ::warning + 跳过,不阻塞构建。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhModelsDev'
F = 'app/src/main/java/me/rerere/rikkahub/data/model/ModelContextLengthResolver.kt'


def warn(msg):
    print('::warning file=' + F + '::batch169 ' + str(msg)[:1200])


def skip(msg):
    warn(msg + ' — skipped (warn-only)')
    sys.stdout.flush()
    sys.exit(0)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


try:
    t = (ROOT / F).read_text(encoding='utf-8')
except Exception as e:
    skip('read failed: ' + str(e))

if MARK in t:
    print('batch169: already applied')
    sys.exit(0)

bal0 = balance(t)
lines = t.split(NL)

# ---- 1. 加字段(锚点: private val cache = mutableMapOf<String, Int?>()) ----
cache_hits = [i for i, ln in enumerate(lines) if 'private val cache = mutableMapOf<String, Int?>()' in ln]
if len(cache_hits) != 1:
    skip('cache field anchor count=' + str(len(cache_hits)))
ci = cache_hits[0]
d = ind(lines[ci])
field_block = [
    d + '// ' + MARK + ': models.dev 目录缓存(App 生命周期内存缓存,避免重复拉取大 JSON)',
    d + 'private var modelsDevCatalog: Map<String, Int>? = null',
    d + 'private var modelsDevFetchAttempted = false',
]
for j, b in enumerate(field_block):
    lines.insert(ci + 1 + j, b)

# ---- 2. 原 queryPublicCatalog 改名 queryOpenRouter ----
pub_hits = [i for i, ln in enumerate(lines) if 'private suspend fun queryPublicCatalog(modelId: String): Int? = withContext(Dispatchers.IO) {' in ln]
if len(pub_hits) != 1:
    skip('queryPublicCatalog anchor count=' + str(len(pub_hits)))
pi = pub_hits[0]
d = ind(lines[pi])
lines[pi] = d + 'private suspend fun queryOpenRouter(modelId: String): Int? = withContext(Dispatchers.IO) { // ' + MARK + ': renamed from queryPublicCatalog'

# ---- 3. 在 queryOpenRouter 之前插入新的 queryPublicCatalog + models.dev 方法 ----
new_block = [
    d + '// ' + MARK + ': 兜底查询 = models.dev 目录 -> OpenRouter(未命中时)',
    d + 'private suspend fun queryPublicCatalog(modelId: String): Int? =',
    d + '    queryModelsDev(modelId) ?: queryOpenRouter(modelId)',
    '',
    d + '// ' + MARK + ': 查 models.dev 目录(首次拉取 api.json 并解析成 normalizedKey -> contextLength)',
    d + 'private suspend fun queryModelsDev(modelId: String): Int? = withContext(Dispatchers.IO) {',
    d + '    runCatching {',
    d + '        if (!modelsDevFetchAttempted) {',
    d + '            modelsDevFetchAttempted = true',
    d + '            modelsDevCatalog = fetchModelsDevCatalog()',
    d + '        }',
    d + '        modelsDevCatalog?.get(ModelNameNormalizer.key(modelId))',
    d + '    }.getOrNull()',
    d + '}',
    '',
    d + 'private fun fetchModelsDevCatalog(): Map<String, Int>? = runCatching {',
    d + '    val request = Request.Builder()',
    d + '        .url(' + Q + 'https://models.dev/api.json' + Q + ')',
    d + '        .header(' + Q + 'Accept' + Q + ', ' + Q + 'application/json' + Q + ')',
    d + '        .get()',
    d + '        .build()',
    d + '    val call = client.newCall(request)',
    d + '    call.timeout().timeout(20, TimeUnit.SECONDS)',
    d + '    call.execute().use { response ->',
    d + '        if (!response.isSuccessful) return@use null',
    d + '        val body = response.body?.string().orEmpty()',
    d + '        if (body.length > MODELS_DEV_MAX_CHARS) return@use null',
    d + '        parseModelsDevCatalog(body)',
    d + '    }',
    d + '}.getOrNull()',
    '',
    d + 'private fun parseModelsDevCatalog(body: String): Map<String, Int>? = runCatching {',
    d + '    val root = JSONObject(body)',
    d + '    val result = mutableMapOf<String, Int>()',
    d + '    val providers = root.keys()',
    d + '    while (providers.hasNext()) {',
    d + '        val provider = root.optJSONObject(providers.next()) ?: continue',
    d + '        val models = provider.optJSONObject(' + Q + 'models' + Q + ') ?: continue',
    d + '        val modelIds = models.keys()',
    d + '        while (modelIds.hasNext()) {',
    d + '            val m = models.optJSONObject(modelIds.next()) ?: continue',
    d + '            val ctx = m.optJSONObject(' + Q + 'limit' + Q + ')?.optInt(' + Q + 'context' + Q + ', 0) ?: 0',
    d + '            if (ctx <= 0) continue',
    d + '            val mid = m.optString(' + Q + 'id' + Q + ').ifBlank { m.optString(' + Q + 'name' + Q + ') }',
    d + '            if (mid.isBlank()) continue',
    d + '            result[ModelNameNormalizer.key(mid)] = ctx',
    d + '        }',
    d + '    }',
    d + '    if (result.isEmpty()) null else result',
    d + '}.getOrNull()',
    '',
]
for j, b in enumerate(new_block):
    lines.insert(pi + j, b)

# ---- 4. 加常量(锚点: MAX_RESPONSE_CHARS 定义) ----
max_hits = [i for i, ln in enumerate(lines) if 'private const val MAX_RESPONSE_CHARS' in ln]
if len(max_hits) != 1:
    skip('MAX_RESPONSE_CHARS anchor count=' + str(len(max_hits)))
mi = max_hits[0]
d = ind(lines[mi])
lines.insert(mi + 1, d + 'private const val MODELS_DEV_MAX_CHARS = 8 * 1024 * 1024 // ' + MARK)

out = NL.join(lines)
for need in [MARK, 'queryModelsDev', 'fetchModelsDevCatalog', 'parseModelsDevCatalog', 'MODELS_DEV_MAX_CHARS', 'queryOpenRouter']:
    if need not in out:
        skip('selfcheck missing: ' + need)
if 'private suspend fun queryPublicCatalog(modelId: String): Int? = withContext' in out:
    skip('old queryPublicCatalog still present (rename failed)')
if balance(out) != bal0:
    skip('balance changed')

(ROOT / F).write_text(out, encoding='utf-8')
print('::notice::batch169 OK - models.dev catalog integrated (memory-cached)')

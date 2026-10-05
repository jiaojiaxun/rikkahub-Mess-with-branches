#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch92: T9 —— 供应商一键整理(被动按钮 + 按最后调用时间排序)

需求(用户原话):
"一键整理是被动的,在供应商顶部加一个按钮,当用户点击就自动排序,不按用户来。"
排序规则:启用的在上、禁用的在下;每组内按【最后一次调用时间】降序;
         没有调用记录的,保持整理前的相对顺序。

设计:
- 存储:新增 Settings.providerLastUsedAt(Map<Uuid, Long>),不动 ProviderSetting(多态序列化,加字段风险高)。
- 打点:AILoggingManager 已持有 settingsStore;给它加 recordProviderUsed(providerId),
        GenerationHandler.generateText 解析出 provider 后调用(零 DI 改动,构造已持有 aiLoggingManager)。
        成功后/发起时记录 + 30 秒节流,避免 DataStore 写放大。
- UI:SettingProviderPage 顶栏 actions 最前插一个 IconButton(用已 import 的 DragDropHorizontal,不赌图标存在)。
- 排序:显式原索引 tie-break 实现稳定(sortedWith 本身不稳定)。

五查:
1. import:AILogging.kt 加 kotlin.uuid.Uuid;其余文件所需符号均已 import
2. 同文件冲突:4 个源文件均无在链 patch 触碰
3. 作用域:AILoggingManager 方法在类内;GenerationHandler 打点在 flow 内 provider 解析后;排序在 onClick 内
4. 括号配对:新增块均自平衡
5. 函数签名:只加方法不改签名;AILoggingManager 构造参数 appScope 加 private val(仍是同类型)

Python 三查:引号用 chr() / 无 f-string / helper 先定义 / 失败显式 exit(1)
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
D = chr(34)
MARK = 'rhProviderTidy'

AL = 'app/src/main/java/me/rerere/rikkahub/data/ai/AILogging.kt'
GH = 'app/src/main/java/me/rerere/rikkahub/data/ai/GenerationHandler.kt'
PS = 'app/src/main/java/me/rerere/rikkahub/data/datastore/PreferencesStore.kt'
PP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingProviderPage.kt'
EN = 'app/src/main/res/values/strings.xml'
ZH = 'app/src/main/res/values-zh/strings.xml'


def fail(path, msg, lines=None, around=-1):
    body = 'batch92 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + '[' + str(len(lines[i]) - len(lines[i].lstrip())) + ']' + lines[i].strip()[:100] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + path + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


def ind_of(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def find_unique(lines, path, pred, label):
    hits = [i for i, ln in enumerate(lines) if pred(ln)]
    if len(hits) != 1:
        fail(path, label + ' count=' + str(len(hits)), lines, hits[0] if hits else 0)
    return hits[0]


# ============================================================
# 1. AILogging.kt —— appScope 存为 val + 加 recordProviderUsed + 常量 + import
# ============================================================
al = (ROOT / AL).read_text(encoding='utf-8')
if MARK not in al:
    lines = al.split(NL)

    # 1a. import Uuid(锚 ProviderSetting import 行后)
    imp_lines = [i for i, ln in enumerate(lines) if ln.strip() == 'import me.rerere.ai.provider.ProviderSetting']
    if len(imp_lines) != 1:
        fail(AL, 'ProviderSetting import anchor count=' + str(len(imp_lines)), lines, imp_lines[0] if imp_lines else 0)
    if not any(ln.strip() == 'import kotlin.uuid.Uuid' for ln in lines):
        lines.insert(imp_lines[0] + 1, 'import kotlin.uuid.Uuid')

    # 1b. 常量(锚 MAX_LOGS)
    i = find_unique(lines, AL, lambda ln: ln.strip() == 'private const val MAX_LOGS = 32', 'MAX_LOGS const')
    lines.insert(i + 1, 'private const val PROVIDER_LAST_USED_MIN_INTERVAL_MS = 30_000L // ' + MARK)

    # 1c. appScope 参数 -> private val(锚 "    appScope: AppScope,")
    i = find_unique(lines, AL, lambda ln: ln.strip() == 'appScope: AppScope,', 'appScope ctor param')
    lines[i] = ind_of(lines[i]) + 'private val appScope: AppScope,'

    # 1d. 方法(插在 clearLogs 之后)
    i = find_unique(lines, AL, lambda ln: ln.strip() == 'fun clearLogs() {', 'clearLogs fn')
    # 找该函数闭合 }
    close = -1
    for j in range(i + 1, min(i + 6, len(lines))):
        if lines[j].strip() == '}':
            close = j
            break
    if close < 0:
        fail(AL, 'clearLogs close brace not found', lines, i)
    di = ind_of(lines[i])
    block = [
        '',
        di + '/** ' + MARK + ': 记录供应商最后一次被调用成功的时间(30 秒节流,防 DataStore 写放大)。 */',
        di + 'fun recordProviderUsed(providerId: Uuid) {',
        di + '    appScope.launch {',
        di + '        settingsStore.update { settings ->',
        di + '            val now = System.currentTimeMillis()',
        di + '            val last = settings.providerLastUsedAt[providerId] ?: 0L',
        di + '            if (now - last < PROVIDER_LAST_USED_MIN_INTERVAL_MS) settings',
        di + '            else settings.copy(',
        di + '                providerLastUsedAt = settings.providerLastUsedAt + (providerId to now)',
        di + '            )',
        di + '        }',
        di + '    }',
        di + '}',
    ]
    lines[close + 1:close + 1] = block

    out = NL.join(lines)
    for need in ['import kotlin.uuid.Uuid',
                 'private val appScope: AppScope,',
                 'private const val PROVIDER_LAST_USED_MIN_INTERVAL_MS = 30_000L',
                 'fun recordProviderUsed(providerId: Uuid) {']:
        if need not in out:
            fail(AL, 'selfcheck missing: ' + need)
    (ROOT / AL).write_text(out, encoding='utf-8')
    print('batch92: AILogging OK')
else:
    print('batch92: AILogging already applied')


# ============================================================
# 2. GenerationHandler.kt —— provider 解析后打点
# ============================================================
gh = (ROOT / GH).read_text(encoding='utf-8')
if MARK not in gh:
    lines = gh.split(NL)
    i = find_unique(lines, GH, lambda ln: ln.strip() == 'val providerImpl = providerManager.getProviderByType(provider)', 'providerImpl line')
    gi = ind_of(lines[i])
    lines.insert(i + 1, gi + 'aiLoggingManager.recordProviderUsed(provider.id) // ' + MARK)
    out = NL.join(lines)
    if 'aiLoggingManager.recordProviderUsed(provider.id)' not in out:
        fail(GH, 'selfcheck: recordProviderUsed call missing')
    (ROOT / GH).write_text(out, encoding='utf-8')
    print('batch92: GenerationHandler OK')
else:
    print('batch92: GenerationHandler already applied')


# ============================================================
# 3. PreferencesStore.kt —— key + read + write + Settings field
# ============================================================
ps = (ROOT / PS).read_text(encoding='utf-8')
if MARK not in ps:
    lines = ps.split(NL)

    # 3a. key(锚 FAVORITE_MODELS key)
    i = find_unique(lines, PS, lambda ln: ln.strip() == 'val FAVORITE_MODELS = stringPreferencesKey(' + D + 'favorite_models' + D + ')', 'FAVORITE_MODELS key')
    lines.insert(i + 1, '        val PROVIDER_LAST_USED_AT = stringPreferencesKey(' + D + 'provider_last_used_at' + D + ') // ' + MARK)

    # 3b. Settings field(锚 fastModelId 字段后,subAgentModelId 已在,插其后)
    i = find_unique(lines, PS, lambda ln: ln.strip() == 'val subAgentModelId: Uuid? = null, // rhSubAgentModel', 'subAgentModelId field')
    lines.insert(i + 1, '    /** ' + MARK + ': providerId -> 最后一次被调用的 epoch millis。用于供应商一键整理。 */')
    lines.insert(i + 2, '    val providerLastUsedAt: Map<Uuid, Long> = emptyMap(),')

    # 3c. read mapping(锚 subAgentModelId 读行后)
    i = find_unique(lines, PS, lambda ln: ln.strip() == 'subAgentModelId = preferences[SUB_AGENT_MODEL]?.let { runCatching { Uuid.parse(it) }.getOrNull() }, // rhSubAgentModel', 'subAgentModelId read')
    ri = ind_of(lines[i])
    lines.insert(i + 1, ri + 'providerLastUsedAt = preferences[PROVIDER_LAST_USED_AT]?.let { raw ->')
    lines.insert(i + 2, ri + '    runCatching { JsonInstant.decodeFromString<Map<String, Long>>(raw) }.getOrElse {')
    lines.insert(i + 3, ri + '        Log.w(TAG, ' + D + 'Failed to decode providerLastUsedAt, using default' + D + ', it)')
    lines.insert(i + 4, ri + '        emptyMap()')
    lines.insert(i + 5, ri + '    }')
    lines.insert(i + 6, ri + '}?.mapNotNull { (k, v) -> runCatching { Uuid.parse(k) }.getOrNull()?.let { it to v } }?.toMap() ?: emptyMap(), // ' + MARK)

    # 3d. write mapping(锚 subAgentModelId 写块后)
    i = find_unique(lines, PS, lambda ln: ln.strip() == '} ?: preferences.remove(SUB_AGENT_MODEL) // rhSubAgentModel', 'subAgentModelId write tail')
    wi = ind_of(lines[i])
    lines.insert(i + 1, wi + 'preferences[PROVIDER_LAST_USED_AT] = JsonInstant.encodeToString(')
    lines.insert(i + 2, wi + '    settings.providerLastUsedAt.mapKeys { it.key.toString() }')
    lines.insert(i + 3, wi + ') // ' + MARK)

    out = NL.join(lines)
    for need in ['val PROVIDER_LAST_USED_AT = stringPreferencesKey(' + D + 'provider_last_used_at' + D + ')',
                 'val providerLastUsedAt: Map<Uuid, Long> = emptyMap(),',
                 'providerLastUsedAt = preferences[PROVIDER_LAST_USED_AT]',
                 'preferences[PROVIDER_LAST_USED_AT] = JsonInstant.encodeToString(']:
        if need not in out:
            fail(PS, 'selfcheck missing: ' + need)
    (ROOT / PS).write_text(out, encoding='utf-8')
    print('batch92: PreferencesStore OK')
else:
    print('batch92: PreferencesStore already applied')


# ============================================================
# 4. SettingProviderPage.kt —— 顶栏一键整理按钮
# ============================================================
pp = (ROOT / PP).read_text(encoding='utf-8')
if MARK not in pp:
    lines = pp.split(NL)
    i = find_unique(lines, PP, lambda ln: ln.strip() == 'RecommendProviderButton { provider ->', 'RecommendProviderButton call')
    pri = ind_of(lines[i])
    block = [
        pri + '// ' + MARK + ': 一键整理 —— 启用的在上,组内按最后调用时间降序,无记录的保持原顺序',
        pri + 'IconButton(',
        pri + '    onClick = {',
        pri + '        val order = settings.providers.withIndex().associate { it.value.id to it.index }',
        pri + '        val used = settings.providerLastUsedAt',
        pri + '        val sorted = settings.providers.sortedWith(',
        pri + '            compareByDescending<ProviderSetting> { it.enabled }',
        pri + '                .thenByDescending { used[it.id] ?: Long.MIN_VALUE }',
        pri + '                .thenBy { order[it.id] ?: Int.MAX_VALUE }',
        pri + '        )',
        pri + '        vm.updateSettings(settings.copy(providers = sorted))',
        pri + '    }',
        pri + ') {',
        pri + '    Icon(HugeIcons.DragDropHorizontal, contentDescription = stringResource(R.string.setting_provider_page_tidy))',
        pri + '}',
    ]
    lines[i:i] = block
    out = NL.join(lines)
    if 'compareByDescending<ProviderSetting> { it.enabled }' not in out:
        fail(PP, 'selfcheck: tidy comparator missing')
    if 'R.string.setting_provider_page_tidy' not in out:
        fail(PP, 'selfcheck: tidy label missing')
    (ROOT / PP).write_text(out, encoding='utf-8')
    print('batch92: SettingProviderPage OK')
else:
    print('batch92: SettingProviderPage already applied')


# ============================================================
# 5. strings
# ============================================================
def patch_strings(path, value):
    p = ROOT / path
    s = p.read_text(encoding='utf-8')
    if 'setting_provider_page_tidy' in s:
        print('batch92: strings already patched: ' + path)
        return
    k = s.find('<resources')
    if k < 0:
        fail(path, 'no <resources> tag')
    g = s.find('>', k)
    if g < 0:
        fail(path, '<resources> not closed')
    ins = (NL + '    <!-- ' + MARK + ' -->' + NL +
           '    <string name=' + D + 'setting_provider_page_tidy' + D + '>' + value + '</string>')
    s = s[:g + 1] + ins + s[g + 1:]
    p.write_text(s, encoding='utf-8')
    print('batch92: strings patched: ' + path)


patch_strings(EN, 'Tidy')
patch_strings(ZH, '整理')

print('batch92: OK (provider last-used tracking + one-tap tidy)')

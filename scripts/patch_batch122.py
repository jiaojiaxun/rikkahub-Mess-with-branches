#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch122 v2: B3 —— 新建供应商自动查重 + 合并询问

v1 必挂: `?.trimEnd("/")` —— Kotlin trimEnd 无 String 重载,只有
vararg Char 与 predicate。v2 用 SQ=chr(39) 生成 `?.trimEnd('/')`。

需求(用户 2026-10-06):
"每次新建一个供应商的时候 自动在后台搜索有没有相同url的供应商已经存在了
或者相同的api密钥...如果有相同的 那么就弹窗提醒 问是否合并...如果选择
确定就新增一个输入口,然后把新增的密钥放到新增的位置"

实现:
- SettingProviderPage.kt 6 处改动:
  1) providerToDelete 状态后加 pendingProviderMerge + rhAddOrMergeProvider lambda
  2-4) 三个新建入口(推荐/扫码/手动)统一走该 lambda 触发查重
  5) providerToDelete 对话框后加合并询问 AlertDialog
  6) 文件尾追加 4 个私有工具函数
- strings.xml(en/zh) 各 4 条新字符串

判定规则(安全约束):
- 仅当新供应商至少有一个 Key 时才检查(无 Key 直接放行,如推荐模板)
- 仅同类型供应商比较(避免跨类型误合并)
- 命中条件:归一化 baseUrl 相同 OR 存在相同 Key
- Key 切分与 KeyRoulette 一致:Regex("[\\s,]+")

五查:
1. import:已有 AlertDialog/TextButton/Text/stringResource/mutableStateOf/remember
2. 同文件冲突:避开 batch42(filteredProviders)与 batch92(tidy button)锚点
3. 作用域:状态与 lambda 在 SettingProviderPage 内;工具函数文件级 private
4. 括号配对:全部插入块自平衡;注释内无括号,不干扰 balance 校验
5. 函数签名:不改任何签名

Python 三查:引号用 BS/D/SQ 变量;无 f-string;helper 先定义;失败显式 exit(1)
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
D = chr(34)
SQ = chr(39)
BS = chr(92)
MARK = 'rhKeyMerge'

PP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingProviderPage.kt'
EN = 'app/src/main/res/values/strings.xml'
ZH = 'app/src/main/res/values-zh/strings.xml'

def fail(path, msg, lines=None, around=-1):
    body = 'batch122v2 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + path + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)

def balance(t):
    return (t.count('(') - t.count(')')) + (t.count('{') - t.count('}'))

def patch_strings(path, entries):
    s = (ROOT / path).read_text(encoding='utf-8')
    if 'setting_provider_merge_title' in s:
        print('batch122v2: strings already patched: ' + path)
        return
    i = s.find('<resources')
    if i < 0:
        fail(path, 'no <resources> tag')
    j = s.find('>', i)
    if j < 0:
        fail(path, 'resources tag not closed')
    ins = NL + '    <!-- ' + MARK + ' -->'
    for name, value in entries:
        ins = ins + NL + '    <string name=' + D + name + D + '>' + value + '</string>'
    s = s[:j + 1] + ins + s[j + 1:]
    (ROOT / path).write_text(s, encoding='utf-8')
    print('batch122v2: strings OK: ' + path)

def main():
    patch_strings(EN, [
        ('setting_provider_merge_title', 'Duplicate provider found'),
        ('setting_provider_merge_message', '%1$s already uses the same URL or API Key. Merge the new keys into it?'),
        ('setting_provider_merge_confirm', 'Merge'),
        ('setting_provider_merge_keep', 'Create anyway')
    ])
    patch_strings(ZH, [
        ('setting_provider_merge_title', '发现重复供应商'),
        ('setting_provider_merge_message', '「%1$s」已使用相同的 URL 或 API Key。是否将新的密钥合并到该供应商？'),
        ('setting_provider_merge_confirm', '合并'),
        ('setting_provider_merge_keep', '仍然新建')
    ])

    t = (ROOT / PP).read_text(encoding='utf-8')
    if MARK in t:
        print('batch122v2: ' + PP + ' already patched')
        return

    bal_before = balance(t)
    lines = t.split(NL)

    # 1. state + unified entry lambda, inserted after providerToDelete
    anchor = 'var providerToDelete by remember { mutableStateOf<ProviderSetting?>(null) }'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == anchor]
    if len(hits) != 1:
        fail(PP, 'providerToDelete state count=' + str(len(hits)), lines, hits[0] if hits else 0)
    idx_state = hits[0]

    state_insert = [
        '',
        '    // ' + MARK + ': 新建供应商时自动查重,相同 URL 或 API Key 命中时询问是否合并',
        '    var pendingProviderMerge by remember { mutableStateOf<Pair<ProviderSetting, ProviderSetting>?>(null) }',
        '    val rhAddOrMergeProvider: (ProviderSetting) -> Unit = { rhCandidate ->',
        '        val rhDuplicate = rhFindDuplicateProvider(rhCandidate, settings.providers)',
        '        if (rhDuplicate != null) {',
        '            pendingProviderMerge = rhCandidate to rhDuplicate',
        '        } else {',
        '            vm.updateSettings(settings.copy(providers = listOf(rhCandidate) + settings.providers))',
        '        }',
        '    }'
    ]
    lines = lines[:idx_state + 1] + state_insert + lines[idx_state + 1:]

    # 2-4. route all three creation paths through the unified lambda
    def replace_call_site(block_patterns, replacement_lines, label):
        global_lines = lines
        start_strip = block_patterns[0]
        hit_list = [i for i, ln in enumerate(global_lines) if ln.strip() == start_strip]
        if len(hit_list) != 1:
            fail(PP, label + ' start count=' + str(len(hit_list)), global_lines, hit_list[0] if hit_list else 0)
        idx = hit_list[0]
        for k in range(1, len(block_patterns)):
            if idx + k >= len(global_lines) or global_lines[idx + k].strip() != block_patterns[k]:
                fail(PP, label + ' pattern[' + str(k) + '] mismatch', global_lines, idx)
        ind = global_lines[idx][:len(global_lines[idx]) - len(global_lines[idx].lstrip())]
        new_block = []
        for ln in replacement_lines:
            if ln == '':
                new_block.append('')
            else:
                new_block.append(ind + ln)
        return global_lines[:idx] + new_block + global_lines[idx + len(block_patterns):]

    lines = replace_call_site(
        ['RecommendProviderButton { provider ->',
         'vm.updateSettings(',
         'settings.copy(',
         'providers = listOf(provider.copyProvider(Uuid.random())) + settings.providers',
         ')',
         ')',
         '}'],
        ['RecommendProviderButton { provider ->',
         '    rhAddOrMergeProvider(provider.copyProvider(Uuid.random()))',
         '}'],
        'Recommend'
    )

    lines = replace_call_site(
        ['ImportProviderButton {',
         'vm.updateSettings(',
         'settings.copy(',
         'providers = listOf(it.copyProvider(Uuid.random())) + settings.providers',
         ')',
         ')',
         '}'],
        ['ImportProviderButton {',
         '    rhAddOrMergeProvider(it.copyProvider(Uuid.random()))',
         '}'],
        'Import'
    )

    lines = replace_call_site(
        ['AddButton {',
         'vm.updateSettings(',
         'settings.copy(',
         'providers = listOf(it) + settings.providers',
         ')',
         ')',
         '}'],
        ['AddButton {',
         '    rhAddOrMergeProvider(it)',
         '}'],
        'Add'
    )

    # 5. merge prompt dialog, inserted right after the delete dialog let-block
    cancel_line = 'Text(stringResource(R.string.setting_provider_delete_cancel))'
    hits = [i for i, ln in enumerate(lines) if cancel_line in ln]
    if len(hits) != 1:
        fail(PP, 'delete cancel count=' + str(len(hits)), lines, hits[0] if hits else 0)
    idx_cancel = hits[0]

    tail_expected = ['}', '},', ')', '}']
    for k in range(1, len(tail_expected) + 1):
        if idx_cancel + k >= len(lines) or lines[idx_cancel + k].strip() != tail_expected[k - 1]:
            fail(PP, 'delete dialog tail[' + str(k) + '] mismatch', lines, idx_cancel)

    dialog_insert = [
        '',
        '        // ' + MARK + ': 合并询问,确认则将新密钥并入已有供应商',
        '        pendingProviderMerge?.let { rhPrompt ->',
        '            val rhNewProvider = rhPrompt.first',
        '            val rhExistingProvider = rhPrompt.second',
        '            AlertDialog(',
        '                onDismissRequest = {',
        '                    vm.updateSettings(settings.copy(providers = listOf(rhNewProvider) + settings.providers))',
        '                    pendingProviderMerge = null',
        '                },',
        '                title = { Text(stringResource(R.string.setting_provider_merge_title)) },',
        '                text = { Text(stringResource(R.string.setting_provider_merge_message, rhExistingProvider.name)) },',
        '                confirmButton = {',
        '                    TextButton(',
        '                        onClick = {',
        '                            vm.updateSettings(',
        '                                settings.copy(',
        '                                    providers = settings.providers.map { rhProvider ->',
        '                                        if (rhProvider.id == rhExistingProvider.id) rhMergeProviderKeys(rhProvider, rhNewProvider)',
        '                                        else rhProvider',
        '                                    }',
        '                                )',
        '                            )',
        '                            pendingProviderMerge = null',
        '                        }',
        '                    ) {',
        '                        Text(stringResource(R.string.setting_provider_merge_confirm))',
        '                    }',
        '                },',
        '                dismissButton = {',
        '                    TextButton(',
        '                        onClick = {',
        '                            vm.updateSettings(settings.copy(providers = listOf(rhNewProvider) + settings.providers))',
        '                            pendingProviderMerge = null',
        '                        }',
        '                    ) {',
        '                        Text(stringResource(R.string.setting_provider_merge_keep))',
        '                    }',
        '                },',
        '            )',
        '        }'
    ]
    lines = lines[:idx_cancel + 5] + dialog_insert + lines[idx_cancel + 5:]

    # 6. file-private helpers appended at end of file
    KNL = BS + 'n'
    helpers = [
        '',
        '// ' + MARK + ': 重复供应商检测与密钥合并工具',
        'private fun ProviderSetting.rhMergeKeyList(): List<String> = when (this) {',
        '    is ProviderSetting.OpenAI -> apiKey',
        '    is ProviderSetting.Google -> apiKey',
        '    is ProviderSetting.Claude -> apiKey',
        '    else -> ' + D + D,
        '}.split(Regex(' + D + '[' + BS + BS + 's,]+' + D + ')).map { it.trim() }.filter { it.isNotEmpty() }',
        '',
        'private fun ProviderSetting.rhMergeBaseUrl(): String? = when (this) {',
        '    is ProviderSetting.OpenAI -> baseUrl',
        '    is ProviderSetting.Google -> baseUrl',
        '    is ProviderSetting.Claude -> baseUrl',
        '    else -> null',
        '}?.trim()?.trimEnd(' + SQ + '/' + SQ + ')?.lowercase()?.takeIf { it.isNotEmpty() }',
        '',
        'private fun rhFindDuplicateProvider(',
        '    candidate: ProviderSetting,',
        '    existing: List<ProviderSetting>,',
        '): ProviderSetting? {',
        '    val candidateKeys = candidate.rhMergeKeyList()',
        '    if (candidateKeys.isEmpty()) return null',
        '    val candidateKeySet = candidateKeys.toSet()',
        '    val candidateUrl = candidate.rhMergeBaseUrl()',
        '    return existing.firstOrNull { other ->',
        '        other.javaClass == candidate.javaClass && (',
        '            other.rhMergeKeyList().any { it in candidateKeySet } ||',
        '                (candidateUrl != null && other.rhMergeBaseUrl() == candidateUrl)',
        '        )',
        '    }',
        '}',
        '',
        'private fun rhMergeProviderKeys(target: ProviderSetting, source: ProviderSetting): ProviderSetting {',
        '    val targetKeys = target.rhMergeKeyList()',
        '    val added = source.rhMergeKeyList().filter { it !in targetKeys }',
        '    if (added.isEmpty()) return target',
        '    val mergedKeyText = (targetKeys + added).joinToString(' + D + KNL + D + ')',
        '    return when (target) {',
        '        is ProviderSetting.OpenAI -> target.copy(apiKey = mergedKeyText)',
        '        is ProviderSetting.Google -> target.copy(apiKey = mergedKeyText)',
        '        is ProviderSetting.Claude -> target.copy(apiKey = mergedKeyText)',
        '        else -> target',
        '    }',
        '}'
    ]

    t_new = NL.join(lines).rstrip() + NL + NL + NL.join(helpers) + NL

    bal_after = balance(t_new)
    if bal_before != bal_after:
        fail(PP, 'balance mismatch: before=' + str(bal_before) + ' after=' + str(bal_after))

    for need in [MARK, 'rhFindDuplicateProvider', 'rhMergeProviderKeys',
                 'rhAddOrMergeProvider(it)', 'pendingProviderMerge',
                 'trimEnd(' + SQ + '/' + SQ + ')']:
        if need not in t_new:
            fail(PP, 'selfcheck missing: ' + need)

    (ROOT / PP).write_text(t_new, encoding='utf-8')
    print('::notice::batch122v2 OK - state+lambda+3 call sites+dialog+4 helpers')

if __name__ == '__main__':
    main()

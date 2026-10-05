#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch91: T7 —— 子代理模型选择(settings.subAgentModelId)

需求:子代理当前用父助手的 chatModelId。要允许用户为子代理单独指定一个模型。
钩子已存在:resolveSubAgentExecutionProfile(... assistantDefaultModelId ...) 已支持该参数,
只是 SubAgentEngine 硬编码传 null。本批把它接到 settings.subAgentModelId。

改动 5 处(全在仓库形态冷门文件,无在链 patch 碰过):
 A PreferencesStore.kt: +prefs key SUB_AGENT_MODEL / +读取映射 / +写回 / +Settings 字段
 B SubAgentEngine.kt: 计算 effectiveSubAgentModelId(不在可用集则回落 null)并接线
 C SettingModelPage.kt: 在 fast model 项后加一个设置项(onSelect + onClear)
 D strings.xml(en) / E strings-zh.xml: 两项文案

设计要点(防"配置指向已停用模型"导致 dispatch 整体被拒):
  resolveSubAgentExecutionProfile 在 effectiveModelId !in availableModelIds 时直接 Rejected。
  若用户选了某模型后其供应商被禁用,子代理会彻底失败。故引擎侧先
  `settings.subAgentModelId?.takeIf { it in availableModelIds }`,不可用则回落父模型,不 Reject。

五查:
1. import 清单:无新增 import(三文件所需符号均已 import)
2. 同文件冲突:三源文件均无在链 patch 触碰;锚点唯一
3. 作用域:字段/映射在各自既有块内;引擎改动在 dispatch 内
4. 括号配对:插入块均自平衡
5. 函数签名:不改任何签名;SubAgentExecutionProfile 字段不动

Python 三查:无 f-string / 无未定义引用 / helper 先定义 / 引号用 chr()
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
D = chr(34)
MARK = 'rhSubAgentModel'

PS = 'app/src/main/java/me/rerere/rikkahub/data/datastore/PreferencesStore.kt'
SE = 'app/src/main/java/me/rerere/rikkahub/subagent/SubAgentEngine.kt'
MP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingModelPage.kt'
EN = 'app/src/main/res/values/strings.xml'
ZH = 'app/src/main/res/values-zh/strings.xml'


def fail(path, msg, lines=None, around=-1):
    body = 'batch91 ' + str(msg)
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
# A. PreferencesStore.kt
# ============================================================
ps = (ROOT / PS).read_text(encoding='utf-8')
if MARK not in ps:
    lines = ps.split(NL)

    # A1: prefs key
    i = find_unique(lines, PS, lambda ln: ln.strip() == 'val FAST_MODEL = stringPreferencesKey(' + D + 'fast_model' + D + ')', 'FAST_MODEL key')
    lines.insert(i + 1, '        val SUB_AGENT_MODEL = stringPreferencesKey(' + D + 'sub_agent_model' + D + ') // ' + MARK)

    # A2: read mapping(after the two-line fastModelId assignment)
    i = find_unique(lines, PS, lambda ln: ln.strip() == 'fastModelId = preferences[FAST_MODEL]?.let { runCatching { Uuid.parse(it) }.getOrNull() }', 'fastModelId read')
    if lines[i + 1].strip() != '?: DEFAULT_AUTO_MODEL_ID,':
        fail(PS, 'fastModelId read continuation not as expected', lines, i + 1)
    lines.insert(i + 2, '                subAgentModelId = preferences[SUB_AGENT_MODEL]?.let { runCatching { Uuid.parse(it) }.getOrNull() }, // ' + MARK)

    # A3: write mapping
    i = find_unique(lines, PS, lambda ln: ln.strip() == 'preferences[FAST_MODEL] = settings.fastModelId.toString()', 'FAST_MODEL write')
    wi = ind_of(lines[i])
    lines.insert(i + 1, wi + 'settings.subAgentModelId?.let {')
    lines.insert(i + 2, wi + '    preferences[SUB_AGENT_MODEL] = it.toString()')
    lines.insert(i + 3, wi + '} ?: preferences.remove(SUB_AGENT_MODEL) // ' + MARK)

    # A4: Settings data class field
    i = find_unique(lines, PS, lambda ln: ln.strip() == 'val fastModelId: Uuid = Uuid.random(),', 'Settings.fastModelId field')
    lines.insert(i + 1, '    val subAgentModelId: Uuid? = null, // ' + MARK)

    out = NL.join(lines)
    for need in ['val SUB_AGENT_MODEL = stringPreferencesKey(' + D + 'sub_agent_model' + D + ')',
                 'subAgentModelId = preferences[SUB_AGENT_MODEL]',
                 'preferences[SUB_AGENT_MODEL] = it.toString()',
                 'val subAgentModelId: Uuid? = null,']:
        if need not in out:
            fail(PS, 'selfcheck missing: ' + need)
    (ROOT / PS).write_text(out, encoding='utf-8')
    print('batch91: PreferencesStore OK')
else:
    print('batch91: PreferencesStore already applied')

# ============================================================
# B. SubAgentEngine.kt
# ============================================================
se = (ROOT / SE).read_text(encoding='utf-8')
if MARK not in se:
    lines = se.split(NL)
    i = find_unique(lines, SE, lambda ln: ln.strip() == 'val availableModelIds = settings.providers', 'availableModelIds decl')
    end = -1
    for j in range(i, min(i + 12, len(lines))):
        if lines[j].strip() == '.toSet()':
            end = j
            break
    if end < 0:
        fail(SE, 'availableModelIds .toSet() not found', lines, i)
    ai = ind_of(lines[i])
    lines.insert(end + 1, '')
    lines.insert(end + 2, ai + '// ' + MARK + ': 用户为子代理指定的专用模型;缺失或已不可用时回落父助手模型。')
    lines.insert(end + 3, ai + 'val effectiveSubAgentModelId = settings.subAgentModelId?.takeIf { it in availableModelIds }')

    j = find_unique(lines, SE, lambda ln: ln.strip() == 'assistantDefaultModelId = null,', 'assistantDefaultModelId null arg')
    lines[j] = ind_of(lines[j]) + 'assistantDefaultModelId = effectiveSubAgentModelId, // ' + MARK

    out = NL.join(lines)
    if 'val effectiveSubAgentModelId = settings.subAgentModelId?.takeIf { it in availableModelIds }' not in out:
        fail(SE, 'engine: effectiveSubAgentModelId missing')
    if 'assistantDefaultModelId = effectiveSubAgentModelId,' not in out:
        fail(SE, 'engine: wiring missing')
    if 'assistantDefaultModelId = null,' in out:
        fail(SE, 'engine: stale null arg remains')
    (ROOT / SE).write_text(out, encoding='utf-8')
    print('batch91: SubAgentEngine OK')
else:
    print('batch91: SubAgentEngine already applied')

# ============================================================
# C. SettingModelPage.kt
# ============================================================
mp = (ROOT / MP).read_text(encoding='utf-8')
if MARK not in mp:
    lines = mp.split(NL)
    i = find_unique(lines, MP, lambda ln: ln.strip() == 'onSelect = { vm.updateSettings(settings.copy(fastModelId = it.id)) },', 'fastModelId item onSelect')
    # 该 item 的闭合 "}" 在下方 3 行内
    close = -1
    for j in range(i + 1, min(i + 5, len(lines))):
        if lines[j].strip() == '}':
            close = j
            break
    if close < 0:
        fail(MP, 'fastModelId item close brace not found', lines, i)
    ci = ind_of(lines[close - 1]) if close > 0 else '        '
    item_ind = '        '
    block = [
        item_ind + 'item { // ' + MARK,
        item_ind + '    ModelSettingItem(',
        item_ind + '        title = stringResource(R.string.setting_model_page_sub_agent_model),',
        item_ind + '        description = stringResource(R.string.setting_model_page_sub_agent_model_desc),',
        item_ind + '        modelId = settings.subAgentModelId,',
        item_ind + '        providers = settings.providers,',
        item_ind + '        onSelect = { vm.updateSettings(settings.copy(subAgentModelId = it.id)) },',
        item_ind + '        onClear = { vm.updateSettings(settings.copy(subAgentModelId = null)) },',
        item_ind + '    )',
        item_ind + '}',
    ]
    lines[close + 1:close + 1] = block
    out = NL.join(lines)
    if 'settings.copy(subAgentModelId = it.id)' not in out:
        fail(MP, 'page: sub-agent item missing')
    (ROOT / MP).write_text(out, encoding='utf-8')
    print('batch91: SettingModelPage OK')
else:
    print('batch91: SettingModelPage already applied')


# ============================================================
# D/E. strings
# ============================================================
def patch_strings(path, title, desc):
    p = ROOT / path
    s = p.read_text(encoding='utf-8')
    if 'setting_model_page_sub_agent_model' in s:
        print('batch91: strings already patched: ' + path)
        return
    k = s.find('<resources')
    if k < 0:
        fail(path, 'no <resources> tag')
    g = s.find('>', k)
    if g < 0:
        fail(path, '<resources> not closed')
    ins = (NL + '    <!-- ' + MARK + ': sub-agent model -->' + NL +
           '    <string name=' + D + 'setting_model_page_sub_agent_model' + D + '>' + title + '</string>' + NL +
           '    <string name=' + D + 'setting_model_page_sub_agent_model_desc' + D + '>' + desc + '</string>')
    s = s[:g + 1] + ins + s[g + 1:]
    p.write_text(s, encoding='utf-8')
    print('batch91: strings patched: ' + path)


patch_strings(EN, 'Sub-agent model', 'Model used by dispatched sub-agents. Leave unset to reuse the parent assistant model.')
patch_strings(ZH, '子代理模型', '分派给子代理使用的模型。未设置时复用父助手的模型。')

print('batch91: OK (sub-agent model selection wired end-to-end)')

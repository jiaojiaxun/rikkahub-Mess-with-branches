#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# batch225: 版本查看工具挂开关 + 本地工具页搜索框
#
# 需求1: get_app_version 常驻注册(batch132)不挂开关、本地工具列表看不到。
#   → LocalToolOption 枚举 +AppVersion; ChatService 两处 batch132 注入行改门控;
#     助手本地工具页加开关行; 新助手默认值 +AppVersion。
# 需求2: 本地工具页 60+ 行硬编码开关没有搜索。
#   → 页面加搜索框 + rhToolItem 包装函数自动包裹全部 item 块(query 非空时按名称/desc 过滤)。
#     CardGroup.item() 只是收集记录(每次重组全量执行), 包装过滤不改变块内逻辑;
#     通用组件 CardGroup.kt 零改动; 原行内容一字不改(未来在链 patch 的锚点零影响)。
#
# warn-only(近期惯例): 任何锚点失败只记录 skipped + 末尾借 ::error 空通道汇总(batch221 先例), 不 exit(0)。
# 门控链(防编译引用缺失): 枚举失败 → ChatService/Assistant/开关行全跳过;
#   搜索框需 state+OutlinedTextField/fillMaxWidth import 成功;
#   包裹需 state + rhToolItem 定义 + CardGroupScope import 成功。
#
# 五查:
# 1. import: 页面 +3 行(各自锚现有 import 精确行, 逐个独立幂等); 其余文件全限定名零 import
# 2. 同文件冲突: 枚举锚 AppControl 行(chat_ui_tools 注入区尾部, b87 锚 Toast/b213 锚 Notification 不重叠);
#    ChatService 锚 batch132 注入行(buildList 区, 另一会话 batch224 改 sendMessage 尾部不重叠);
#    页面锚 js 引擎标题回溯/section 注释/Column/PermissionedSwitch 前
# 3. 作用域: state 在 AssistantLocalToolContent 内 Column 前(remember 合法位置);
#    开关行在 CardGroup scope 内(toggleLocalTool/assistant 可见); CS 门控行在 buildList 内 assistant 可见
# 4. 括号配对: 全部改动净差值=0(逐处核算), 全文断言 balance 不变, 不过不写
# 5. 函数签名: 不改任何现有签名; 新增 private fun CardGroupScope.rhToolItem(query, key, block)
# Python 三查: Q/BS/NL 变量构造; concat_lines 手写禁 join; helper 先定义后用; 无 f-string/walrus/docstring
from pathlib import Path
import re
import sys

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
BS = chr(92)

applied = []
skipped = []


def note(msg):
    applied.append(msg)


def skip(msg):
    skipped.append(msg)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def concat_lines(lines):
    out = ''
    first = True
    for ln in lines:
        if not first:
            out += NL
        out += ln
        first = False
    return out


def load_strings(path):
    m = {}
    try:
        t = (ROOT / path).read_text(encoding='utf-8')
        rgx = re.compile('<string name=' + Q + '([^' + Q + ']+)' + Q + '[^>]*>([^<]*)</string>')
        for name, val in rgx.findall(t):
            m[name] = val
    except Exception:
        pass
    return m


# ============================================================
# 1. LocalTools.kt —— LocalToolOption 枚举 +AppVersion
# ============================================================
LT = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/LocalTools.kt'
enum_ok = False
try:
    p = ROOT / LT
    t = p.read_text(encoding='utf-8')
    if Q + 'app_version' + Q in t:
        enum_ok = True
        note('enum already')
    else:
        lines = t.split(NL)
        bal0 = balance(t)
        idx = -1
        for i, ln in enumerate(lines):
            s = ln.strip()
            if s.startswith('@Serializable @SerialName(' + Q + 'app_control' + Q + ')') and 'data object AppControl' in s:
                idx = i
        if idx < 0:
            for i, ln in enumerate(lines):
                s = ln.strip()
                if s.startswith('@Serializable @SerialName(' + Q + 'archive' + Q + ')') and 'data object Archive' in s:
                    idx = i
        if idx < 0:
            skip('enum: anchor miss (app_control/archive)')
        else:
            newln = ind(lines[idx]) + '@Serializable @SerialName(' + Q + 'app_version' + Q + ')        data object AppVersion            : LocalToolOption() // rhAppVersionGate225'
            lines.insert(idx + 1, newln)
            out = concat_lines(lines)
            if balance(out) != bal0:
                skip('enum: balance changed')
            elif 'data object AppVersion' not in out:
                skip('enum: readback miss')
            else:
                p.write_text(out, encoding='utf-8')
                enum_ok = True
                note('enum')
except Exception as e:
    skip('enum ex: ' + str(e)[:150])

# ============================================================
# 2. ChatService.kt —— batch132 两处常驻注册改门控
# ============================================================
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
OLD_ADD = 'add(me.rerere.rikkahub.data.ai.tools.local.appVersionTool(context))'
NEW_ADD = 'if (assistant.localTools.contains(me.rerere.rikkahub.data.ai.tools.LocalToolOption.AppVersion)) { add(me.rerere.rikkahub.data.ai.tools.local.appVersionTool(context)) } // rhAppVersionGate225'
OLD_CMT = '// rhAppVersion: ' + chr(0x5e38) + chr(0x9a7b)  # 占位防误匹配, 实际锚见下
OLD_CMT_REAL = '// rhAppVersion: 常驻版本查询工具(零副作用,不挂开关)'
NEW_CMT = '// rhAppVersion: version gate (batch225 AppVersion switch)'
if not enum_ok:
    skip('chatservice: gated on enum')
else:
    try:
        p = ROOT / CS
        t = p.read_text(encoding='utf-8')
        if 'rhAppVersionGate225' in t:
            note('chatservice already')
        elif OLD_ADD not in t:
            skip('chatservice: batch132 add line absent')
        else:
            bal0 = balance(t)
            lines = t.split(NL)
            cnt = 0
            for i, ln in enumerate(lines):
                s = ln.strip()
                if s == OLD_ADD:
                    lines[i] = ind(ln) + NEW_ADD
                    cnt += 1
                elif s == OLD_CMT_REAL:
                    lines[i] = ind(ln) + NEW_CMT
            if cnt != 2:
                skip('chatservice: add count=' + str(cnt) + ' (expect 2), NOT writing')
            else:
                out = concat_lines(lines)
                if balance(out) != bal0:
                    skip('chatservice: balance changed ' + str(bal0) + ' -> ' + str(balance(out)))
                elif out.count('rhAppVersionGate225') != 2:
                    skip('chatservice: marker count != 2')
                else:
                    p.write_text(out, encoding='utf-8')
                    note('chatservice x2')
    except Exception as e:
        skip('chatservice ex: ' + str(e)[:150])

# ============================================================
# 3. Assistant.kt —— 新助手默认开版本工具
# ============================================================
AS = 'app/src/main/java/me/rerere/rikkahub/data/model/Assistant.kt'
OLD_DEF = 'val localTools: List<LocalToolOption> = listOf(LocalToolOption.TimeInfo),'
NEW_DEF = 'val localTools: List<LocalToolOption> = listOf(LocalToolOption.TimeInfo, LocalToolOption.AppVersion), // rhAppVersionGate225'
if not enum_ok:
    skip('assistant: gated on enum')
else:
    try:
        p = ROOT / AS
        t = p.read_text(encoding='utf-8')
        if 'TimeInfo, LocalToolOption.AppVersion' in t:
            note('assistant already')
        else:
            lines = t.split(NL)
            hits = []
            for i, ln in enumerate(lines):
                if ln.strip() == OLD_DEF:
                    hits.append(i)
            if len(hits) != 1:
                skip('assistant: anchor count=' + str(len(hits)))
            else:
                bal0 = balance(t)
                lines[hits[0]] = ind(lines[hits[0]]) + NEW_DEF
                out = concat_lines(lines)
                if balance(out) != bal0:
                    skip('assistant: balance changed')
                else:
                    p.write_text(out, encoding='utf-8')
                    note('assistant default')
    except Exception as e:
        skip('assistant ex: ' + str(e)[:150])

# ============================================================
# 4. AssistantLocalToolPage.kt —— 开关行 + 搜索框 + 全量包裹
# ============================================================
AP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/assistant/detail/AssistantLocalToolPage.kt'
STR_EN = 'app/src/main/res/values/strings.xml'
STR_ZH = 'app/src/main/res/values-zh/strings.xml'
try:
    p = ROOT / AP
    t = p.read_text(encoding='utf-8')
    lines = t.split(NL)
    bal0 = balance(t)
    changed = False

    # 4a. imports(逐个独立幂等, 精确 strip 匹配现有 import 行)
    imp_ok = {}
    imp_rules = [
        ('import androidx.compose.foundation.layout.fillMaxWidth',
         'import androidx.compose.foundation.layout.fillMaxSize'),
        ('import androidx.compose.material3.OutlinedTextField',
         'import androidx.compose.material3.MaterialTheme'),
        ('import me.rerere.rikkahub.ui.components.ui.CardGroupScope',
         'import me.rerere.rikkahub.ui.components.ui.CardGroup'),
    ]
    for new_imp, anchor_imp in imp_rules:
        short = new_imp.split('.')[-1]
        if new_imp in t:
            imp_ok[short] = True
            continue
        hits = []
        for i, ln in enumerate(lines):
            if ln.strip() == anchor_imp:
                hits.append(i)
        if len(hits) != 1:
            skip('page import ' + short + ': anchor count=' + str(len(hits)))
            imp_ok[short] = False
            continue
        lines.insert(hits[0] + 1, new_imp)
        imp_ok[short] = True
        changed = True
        note('import ' + short)

    cur = concat_lines(lines)

    # 4b. state(锚: strip()==Column( 且下一行含 modifier = modifier)
    state_ok = ('var rhToolQuery' in cur)
    if not state_ok:
        col_idx = -1
        for i, ln in enumerate(lines):
            if ln.strip() == 'Column(' and i + 1 < len(lines) and 'modifier = modifier' in lines[i + 1]:
                col_idx = i
                break
        if col_idx < 0:
            skip('page state: Column anchor miss')
        else:
            lines.insert(col_idx, ind(lines[col_idx]) + 'var rhToolQuery by remember { mutableStateOf(' + Q + Q + ') } // rhToolSearch225')
            changed = True
            state_ok = True
            note('state')

    # 4c. 搜索框(需 state + 两个 import; 锚: // Built-in tools section 注释行)
    have_box = ('rhToolSearchBox225' in cur)
    if state_ok and imp_ok.get('OutlinedTextField') and imp_ok.get('fillMaxWidth') and not have_box:
        box_idx = -1
        for i, ln in enumerate(lines):
            if ln.strip() == '// Built-in tools section':
                box_idx = i
                break
        if box_idx < 0:
            skip('page box: section comment miss')
        else:
            d = ind(lines[box_idx])
            box = [
                d + 'OutlinedTextField( // rhToolSearchBox225',
                d + '    value = rhToolQuery,',
                d + '    onValueChange = { rhToolQuery = it },',
                d + '    modifier = Modifier.fillMaxWidth(),',
                d + '    placeholder = { Text(' + Q + '搜索工具名称' + Q + ') },',
                d + '    singleLine = true,',
                d + ')',
            ]
            lines[box_idx:box_idx] = box
            changed = True
            note('search box')
    elif not have_box:
        skip('page box: gated on state/imports')

    # 4d. 版本开关行(需枚举; 锚: js 引擎标题行回溯 item()
    have_switch = ('rhAppVersionSwitch225' in cur)
    if enum_ok and not have_switch:
        js_row = -1
        for i, ln in enumerate(lines):
            if 'assistant_page_local_tools_javascript_engine_title' in ln:
                js_row = i
                break
        item_idx = -1
        if js_row >= 0:
            for j in range(js_row, max(js_row - 8, -1), -1):
                if lines[j].strip().startswith('item('):
                    item_idx = j
                    break
        if item_idx < 0:
            skip('page switch: js engine anchor miss')
        else:
            d = ind(lines[item_idx])
            row = [
                d + 'item( // rhAppVersionSwitch225',
                d + '    headlineContent = { Text(' + Q + '版本查看' + Q + ') },',
                d + '    supportingContent = { Text(' + Q + '允许 AI 查看当前 App 版本号与 CI 构建号' + Q + ') },',
                d + '    trailingContent = {',
                d + '        Switch(',
                d + '            checked = assistant.localTools.contains(LocalToolOption.AppVersion),',
                d + '            onCheckedChange = { toggleLocalTool(LocalToolOption.AppVersion, it) }',
                d + '        )',
                d + '    }',
                d + ')',
            ]
            lines[item_idx:item_idx] = row
            changed = True
            note('version switch row')
    elif not enum_ok:
        skip('page switch: gated on enum')

    # 4e. rhToolItem 定义(需 CardGroupScope import; 锚: PermissionedSwitch 的 @Composable 前)
    def_ok = ('fun CardGroupScope.rhToolItem' in cur)
    if imp_ok.get('CardGroupScope') and not def_ok:
        ps_idx = -1
        for i, ln in enumerate(lines):
            if ln.strip() == 'private fun PermissionedSwitch(':
                ps_idx = i
                break
        if ps_idx < 0:
            skip('page def: PermissionedSwitch anchor miss')
        else:
            ins = ps_idx
            if ins > 0 and lines[ins - 1].strip() == '@Composable':
                ins = ins - 1
            defb = [
                '// [batch225] rhToolSearch225: 搜索过滤行包装。query 为空显示全部;',
                '// 否则只显示名称或描述 key 命中的行。包装不改变块内任何逻辑。',
                'private fun CardGroupScope.rhToolItem(query: String, key: String, block: CardGroupScope.() -> Unit) {',
                '    if (query.isBlank() || key.contains(query.trim(), ignoreCase = true)) {',
                '        block()',
                '    }',
                '}',
                '',
            ]
            lines[ins:ins] = defb
            changed = True
            def_ok = True
            note('rhToolItem def')
    elif not def_ok:
        skip('page def: gated on CardGroupScope import')

    # 4f. 全量包裹(需 state+def; key 从硬编码 Text + strings.xml 中英双解提取)
    cur = concat_lines(lines)
    wrapped_already = ('rhToolItem(rhToolQuery' in cur)
    if state_ok and def_ok and not wrapped_already:
        sm_en = load_strings(STR_EN)
        sm_zh = load_strings(STR_ZH)
        re_text = re.compile('Text' + BS + '(' + Q + '([^' + Q + ']*)' + Q + BS + ')')
        re_res = re.compile('stringResource' + BS + '(' + 'R' + BS + '.' + 'string' + BS + '.' + '([A-Za-z0-9_]+)' + BS + ')')
        blocks = []
        i = 0
        n = len(lines)
        while i < n:
            s = lines[i].strip()
            if s.startswith('item('):
                depth = 0
                j = i
                ok = False
                while j < n:
                    depth += lines[j].count('(') - lines[j].count(')')
                    if depth == 0:
                        ok = True
                        break
                    if depth < 0:
                        break
                    j += 1
                if ok:
                    keys = []
                    for k in range(i, j + 1):
                        for m in re_text.findall(lines[k]):
                            if m not in keys:
                                keys.append(m)
                        for name in re_res.findall(lines[k]):
                            if name in sm_en and sm_en[name] not in keys:
                                keys.append(sm_en[name])
                            if name in sm_zh and sm_zh[name] not in keys:
                                keys.append(sm_zh[name])
                    key = ' '.join(keys)
                    key = key.replace(BS, BS + BS)
                    key = key.replace(Q, BS + Q)
                    for ch in '(){}':
                        key = key.replace(ch, ' ')
                    key = ' '.join(key.split())
                    blocks.append((i, j, key))
                    i = j + 1
                    continue
            i += 1
        wcnt = 0
        for bi in range(len(blocks) - 1, -1, -1):
            s0, e0, key = blocks[bi]
            d = ind(lines[s0])
            lines.insert(e0 + 1, d + '} // rhToolSearch225')
            lines.insert(s0, d + 'rhToolItem(rhToolQuery, ' + Q + key + Q + ') { // rhToolSearch225')
            wcnt += 1
        if wcnt > 0:
            changed = True
            note('wrap x' + str(wcnt))
        else:
            skip('page wrap: no item blocks found')
    elif not wrapped_already:
        skip('page wrap: gated on state/def')

    # 4g. 事务写回 + 自检(配平不变是硬门槛)
    if changed:
        out = concat_lines(lines)
        if balance(out) != bal0:
            skip('page: balance ' + str(bal0) + ' -> ' + str(balance(out)) + ', NOT writing')
        else:
            okc = True
            if 'fun CardGroupScope.rhToolItem' in out:
                if out.count('rhToolItem(rhToolQuery') < 1:
                    okc = False
                    skip('page: def exists but wrap count 0')
            if enum_ok and 'rhAppVersionSwitch225' in out:
                if out.count('LocalToolOption.AppVersion') != 2:
                    okc = False
                    skip('page: AppVersion refs != 2')
            if okc:
                p.write_text(out, encoding='utf-8')
                note('page written')
    else:
        note('page no-op')
except Exception as e:
    skip('page ex: ' + str(e)[:150])

# ============================================================
# 汇总(借 ::error 空通道露出; 非错误, batch221 先例)
# ============================================================
summary = 'batch225: applied[' + ','.join(applied) + '] skipped[' + ','.join(skipped) + ']'
print('::error::' + summary[:900])
print(summary)
sys.exit(0)

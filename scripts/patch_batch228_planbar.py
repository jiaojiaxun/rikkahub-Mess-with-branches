#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# batch228: YuiHub PlanBar 移植 —— 既有文件接线(4 个新文件由同一提交直接入库)
#
# 接线内容:
#  A ChatService.kt     在两个工具装配点(buildToolsForRerun + handleMessageComplete)
#                        注册 createTodoTool()(锚=batch132 验证过的 localTools addAll 行)
#  B ToolUI.kt          ToolUIRegistry.renderers 注册 TodoToolUI(思考链一行摘要)
#  C PreferencesStore.kt DisplaySetting 加 showPlanBar 字段(默认 true,锚=batch137 的 rpStyleRules 行)
#  D SettingPreferencesUIPage.kt 显示设置加开关行(锚=batch3 的折叠开关 item 块)
#  E ChatPage.kt        hazeState 后计算 rhPlanTodos(setting.displaySetting.showPlanBar 门控)
#                        + bottomBar Column 内挂 PlanBar(优先 quotePreview 前,回退 ChatInput( 前)
#  F strings.xml en+zh  7 条文案(插入 </resources> 前,batch3/91/130 同款)
#
# warn-only(近期惯例): 任何锚点失败只记录 skipped + 末尾借 ::error 空通道汇总,不 exit(1)。
# 注意: strings 若失败会导致新文件引用缺失编译红,汇总里会显式标出。
#
# 五查:
# 1. import 清单: 对既有文件全部全限定名零 import;新文件自带 import 已逐一对照
#    ToolUI.kt/SubAgentTools.kt 已证可用清单
# 2. 同文件冲突: ChatService 锚 addAll 行=batch132/225 插入点上方(不动它们的行);
#    ChatPage 锚 hazeState/quotePreview 与 batch80/119/patch_chat_page_html 区域不相交;
#    ToolUI/PreferencesStore/SettingPreferencesUIPage 的锚分别是注册表/batch137/batch3 的稳定行
# 3. 作用域: hazeState 与 bottomBar 同在 ChatPageContent 内,setting/conversation 是其参数
#    (ChatPage 调用点 setting = setting / conversation = conversation 已证实)
# 4. 括号配对: 插入块全部自平衡;逐文件断言 balance 不变,变了不写
# 5. 函数签名: 不改任何现有签名(数据在函数体内计算,零参数透传)
# Python 三查: Q 变量构造全部引号字面量;NL 手写 concat 禁 join/f-string/walrus;
# helper 先定义后用;锚失只 skip;注释不带半角括号
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhPlanBar228'

applied = []
skipped = []


def note(m):
    applied.append(m)


def skip(m):
    skipped.append(m)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(t):
    return (t.count('(') - t.count(')')) + (t.count('{') - t.count('}'))


def concat_lines(lines):
    out = ''
    first = True
    for ln in lines:
        if not first:
            out += NL
        out += ln
        first = False
    return out


# ============================================================
# A. ChatService.kt —— 两个装配点注册 createTodoTool()
# ============================================================
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
ANCHOR_ADDALL = 'addAll(localTools.getTools(assistant.localTools, invocationCtx))'
try:
    p = ROOT / CS
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        note('chatservice already')
    else:
        lines = t.split(NL)
        bal0 = balance(t)
        hits = []
        for i, ln in enumerate(lines):
            if ln.strip() == ANCHOR_ADDALL:
                hits.append(i)
        if len(hits) != 2:
            skip('chatservice: anchor count=' + str(len(hits)))
        else:
            for i in reversed(hits):
                d = ind(lines[i])
                lines.insert(i + 1, d + '// ' + MARK + ': todo_write 计划工具,无副作用仅校验归一化,UI 从消息历史派生计划栏')
                lines.insert(i + 2, d + 'add(me.rerere.rikkahub.data.ai.tools.createTodoTool())')
            out = concat_lines(lines)
            if balance(out) != bal0:
                skip('chatservice: balance changed')
            elif out.count('createTodoTool()') != 2:
                skip('chatservice: readback count != 2')
            else:
                p.write_text(out, encoding='utf-8')
                note('chatservice x2')
except Exception as e:
    skip('chatservice ex: ' + str(e)[:150])

# ============================================================
# B. ToolUI.kt —— 注册 TodoToolUI
# ============================================================
TUI = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/tools/ToolUI.kt'
try:
    p = ROOT / TUI
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        note('toolui already')
    else:
        lines = t.split(NL)
        bal0 = balance(t)
        hits = []
        for i, ln in enumerate(lines):
            if ln.strip() == 'ContextCompactionToolUI,':
                hits.append(i)
        if len(hits) != 1:
            skip('toolui: anchor count=' + str(len(hits)))
        else:
            d = ind(lines[hits[0]])
            lines.insert(hits[0] + 1, d + 'TodoToolUI, // ' + MARK)
            out = concat_lines(lines)
            if balance(out) != bal0:
                skip('toolui: balance changed')
            elif 'TodoToolUI,' not in out:
                skip('toolui: readback miss')
            else:
                p.write_text(out, encoding='utf-8')
                note('toolui')
except Exception as e:
    skip('toolui ex: ' + str(e)[:150])

# ============================================================
# C. PreferencesStore.kt —— DisplaySetting.showPlanBar
# ============================================================
PS = 'app/src/main/java/me/rerere/rikkahub/data/datastore/PreferencesStore.kt'
try:
    p = ROOT / PS
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        note('prefs already')
    else:
        lines = t.split(NL)
        bal0 = balance(t)
        hits = []
        for i, ln in enumerate(lines):
            if ln.strip().startswith('val rpStyleRules: List<RpStyleRule> = emptyList(),'):
                hits.append(i)
        if len(hits) != 1:
            skip('prefs: rpStyleRules anchor count=' + str(len(hits)))
        else:
            d = ind(lines[hits[0]])
            lines.insert(hits[0] + 1, d + 'val showPlanBar: Boolean = true, // ' + MARK)
            out = concat_lines(lines)
            if balance(out) != bal0:
                skip('prefs: balance changed')
            elif 'val showPlanBar: Boolean = true,' not in out:
                skip('prefs: readback miss')
            else:
                p.write_text(out, encoding='utf-8')
                note('prefs')
except Exception as e:
    skip('prefs ex: ' + str(e)[:150])

# ============================================================
# D. SettingPreferencesUIPage.kt —— 显示设置开关行
# ============================================================
UP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPreferencesUIPage.kt'
try:
    p = ROOT / UP
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        note('uipage already')
    else:
        lines = t.split(NL)
        bal0 = balance(t)
        sw = -1
        for i, ln in enumerate(lines):
            if 'updateDisplaySetting(displaySetting.copy(collapseLongUserMessage = it))' in ln:
                sw = i
                break
        if sw < 0:
            skip('uipage: collapse switch anchor miss')
        else:
            it0 = -1
            for j in range(sw, max(sw - 8, -1), -1):
                if lines[j].strip().startswith('item('):
                    it0 = j
                    break
            if it0 < 0:
                skip('uipage: item backscan miss')
            else:
                depth = 0
                it1 = -1
                for j in range(it0, len(lines)):
                    depth += lines[j].count('(') - lines[j].count(')')
                    if depth == 0:
                        it1 = j
                        break
                    if depth < 0:
                        break
                if it1 < 0:
                    skip('uipage: item close miss')
                else:
                    d = ind(lines[it0])
                    block = [
                        d + '// ' + MARK + ': 计划细条显示开关',
                        d + 'item(',
                        d + '    headlineContent = { Text(stringResource(R.string.setting_display_page_plan_bar_title)) },',
                        d + '    supportingContent = { Text(stringResource(R.string.setting_display_page_plan_bar_desc)) },',
                        d + '    trailingContent = {',
                        d + '        Switch(',
                        d + '            checked = displaySetting.showPlanBar,',
                        d + '            onCheckedChange = { updateDisplaySetting(displaySetting.copy(showPlanBar = it)) }',
                        d + '        )',
                        d + '    }',
                        d + ')',
                    ]
                    lines[it1 + 1:it1 + 1] = block
                    out = concat_lines(lines)
                    if balance(out) != bal0:
                        skip('uipage: balance changed')
                    elif 'showPlanBar = it' not in out:
                        skip('uipage: readback miss')
                    else:
                        p.write_text(out, encoding='utf-8')
                        note('uipage')
except Exception as e:
    skip('uipage ex: ' + str(e)[:150])

# ============================================================
# E. ChatPage.kt —— rhPlanTodos 计算 + PlanBar 挂载
# ============================================================
CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
try:
    p = ROOT / CP
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        note('chatpage already')
    else:
        if 'setting' not in t:
            skip('chatpage: setting symbol absent')
        elif 'conversation' not in t:
            skip('chatpage: conversation symbol absent')
        else:
            lines = t.split(NL)
            bal0 = balance(t)
            hz = []
            for i, ln in enumerate(lines):
                if ln.strip() == 'val hazeState = rememberHazeState()':
                    hz.append(i)
            if len(hz) != 1:
                skip('chatpage: hazeState anchor count=' + str(len(hz)))
            else:
                d = ind(lines[hz[0]])
                blk = [
                    d + '// ' + MARK + ': 计划细条数据,取最新一次已执行的 todo_write,开关关闭时置空隐藏',
                    d + 'val rhPlanTodos = if (setting.displaySetting.showPlanBar) {',
                    d + '    remember(conversation.currentMessages) {',
                    d + '        me.rerere.rikkahub.ui.components.message.findActivePlan(conversation.currentMessages)',
                    d + '    }',
                    d + '} else {',
                    d + '    emptyList()',
                    d + '}',
                ]
                for j, b in enumerate(blk):
                    lines.insert(hz[0] + 1 + j, b)
                mounted = False
                qi = -1
                for i, ln in enumerate(lines):
                    if ln.strip() == 'val quotePreview = quotingMessage':
                        qi = i
                        break
                if qi >= 0:
                    d2 = ind(lines[qi])
                    lines.insert(qi, d2 + '// ' + MARK + ': 计划细条,常驻输入框正上方,收起一行,点击展开完整清单')
                    lines.insert(qi + 1, d2 + 'me.rerere.rikkahub.ui.components.message.PlanBar(todos = rhPlanTodos)')
                    mounted = True
                else:
                    ci = -1
                    for i, ln in enumerate(lines):
                        if ln.strip() == 'ChatInput(':
                            ci = i
                            break
                    if ci >= 0:
                        d2 = ind(lines[ci])
                        lines.insert(ci, d2 + '// ' + MARK + ': 计划细条,常驻输入框正上方')
                        lines.insert(ci + 1, d2 + 'me.rerere.rikkahub.ui.components.message.PlanBar(todos = rhPlanTodos)')
                        mounted = True
                if not mounted:
                    skip('chatpage: mount anchor miss')
                else:
                    out = concat_lines(lines)
                    if balance(out) != bal0:
                        skip('chatpage: balance changed')
                    elif 'PlanBar(todos = rhPlanTodos)' not in out:
                        skip('chatpage: readback miss')
                    elif 'val rhPlanTodos' not in out:
                        skip('chatpage: readback miss2')
                    else:
                        p.write_text(out, encoding='utf-8')
                        note('chatpage')
except Exception as e:
    skip('chatpage ex: ' + str(e)[:150])

# ============================================================
# F. strings.xml en + zh
# ============================================================
EN = 'app/src/main/res/values/strings.xml'
ZH = 'app/src/main/res/values-zh/strings.xml'

EN_BLOCK = [
    '    <string name=' + Q + 'chat_message_todo_title' + Q + '>Plan</string> <!-- ' + MARK + ' -->',
    '    <string name=' + Q + 'chat_message_todo_all_done' + Q + '>All steps completed</string>',
    '    <string name=' + Q + 'chat_message_todo_count_hint' + Q + ' formatted=' + Q + 'true' + Q + '>%1$d of %2$d completed</string>',
    '    <string name=' + Q + 'chat_message_todo_collapse' + Q + '>Collapse</string>',
    '    <string name=' + Q + 'plan_bar_expand' + Q + '>Expand plan</string>',
    '    <string name=' + Q + 'setting_display_page_plan_bar_title' + Q + '>Show plan bar</string>',
    '    <string name=' + Q + 'setting_display_page_plan_bar_desc' + Q + '>Pin the AI task plan above the input box, powered by the todo_write tool</string>',
]
ZH_BLOCK = [
    '    <string name=' + Q + 'chat_message_todo_title' + Q + '>计划</string> <!-- ' + MARK + ' -->',
    '    <string name=' + Q + 'chat_message_todo_all_done' + Q + '>全部步骤已完成</string>',
    '    <string name=' + Q + 'chat_message_todo_count_hint' + Q + ' formatted=' + Q + 'true' + Q + '>已完成 %1$d / %2$d</string>',
    '    <string name=' + Q + 'chat_message_todo_collapse' + Q + '>收起</string>',
    '    <string name=' + Q + 'plan_bar_expand' + Q + '>展开计划</string>',
    '    <string name=' + Q + 'setting_display_page_plan_bar_title' + Q + '>显示计划进度条</string>',
    '    <string name=' + Q + 'setting_display_page_plan_bar_desc' + Q + '>在输入框上方常驻显示 AI 的任务计划清单,由 todo_write 工具驱动</string>',
]


def add_strings(path, block):
    p = ROOT / path
    s = p.read_text(encoding='utf-8')
    if 'plan_bar_expand' in s:
        note('strings already: ' + path)
        return
    lines = s.split(NL)
    ri = -1
    for i, ln in enumerate(lines):
        if ln.strip() == '</resources>':
            ri = i
            break
    if ri < 0:
        skip('strings: no resources close in ' + path)
        return
    for j, b in enumerate(block):
        lines.insert(ri + j, b)
    p.write_text(concat_lines(lines), encoding='utf-8')
    note('strings ' + path)


try:
    add_strings(EN, EN_BLOCK)
except Exception as e:
    skip('strings en ex: ' + str(e)[:150])
try:
    add_strings(ZH, ZH_BLOCK)
except Exception as e:
    skip('strings zh ex: ' + str(e)[:150])

# ============================================================
# 汇总(借 ::error 空通道露出; 非错误, batch221/225 先例)
# ============================================================
summary = 'batch228: applied[' + ','.join(applied) + '] skipped[' + ','.join(skipped) + ']'
print('::error::' + summary[:900])
print(summary)
sys.exit(0)

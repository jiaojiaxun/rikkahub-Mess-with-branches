#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch197: 中文文案加可爱语气（第一批示范，25 条）

用户需求: "加一点颜文字和语气在给用户看到的中文文字里(比如设置里的每个字)"。
方案: strings.xml 按 key 整行替换 value（不依赖旧值,天然幂等,重跑自动跳过）。
风格原则: 以句尾语气词(呀/哦/吧/~)为主，颜文字克制；按钮(确定/取消)不动；错误文案不动。

本批范围: 助手/设置页的描述文案、空状态文案、删除对话框文案（25 条）。
效果满意后可扩展下一批（其他页面）。

warn-only: 找不到 key 只 ::warning + 跳过，不阻塞构建（多会话协作，strings.xml 可能被其他 patch 改动）。

五查:
1. import 清单: 仅 sys/pathlib
2. 同文件冲突: strings.xml 被多个 patch 碰过——本脚本用「按 key 整行替换」不受旧值影响，
   sort -V 下 197 最后跑，覆盖顺序安全
3. 作用域: 逐行替换,不动其他行
4. 括号配对: XML 行整体替换（key + 新值 + 闭合标签），自平衡
5. 函数签名: N/A

Python 三查: 引号=chr构造(Q/SQ)；NL 手写 concat；helper 先定义；失败显式 exit(1)
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SQ = chr(39)
MARK = 'rhCuteText197'
ZF = 'app/src/main/res/values-zh/strings.xml'

# (key, 新中文值) —— 只加语气词/微调，不改变原意；按钮与错误文案不列入。
MAPPING = [
    ('assistant_detail_basic_desc', '配置名称、头像、模型和参数呀'),
    ('assistant_detail_extensions_desc', '管理提示词注入、世界书和技能等扩展~'),
    ('assistant_detail_local_tools_desc', '启用本地工具（如 JavaScript 引擎）哦'),
    ('assistant_detail_mcp_desc', '为助手配置 MCP 服务器工具呀'),
    ('assistant_detail_memory_desc', '管理助手记忆和最近的聊天引用~'),
    ('assistant_detail_prompt_desc', '设置系统提示、消息模板和正则规则哦'),
    ('assistant_detail_request_desc', '配置自定义请求头和正文参数~'),
    ('assistant_extensions_page_empty_lorebooks', '还没有世界书哦，去提示词管理建一个吧'),
    ('assistant_extensions_page_empty_mode_injections', '还没有模式注入哦，去提示词管理建一个吧'),
    ('assistant_extensions_page_empty_quick_messages', '还没有快捷消息哦，去扩展里建一个吧'),
    ('assistant_extensions_page_empty_skills', '还没有可用的 Skill 哦，去扩展管理装一个吧'),
    ('assistant_page_background_opacity_desc', '调整聊天背景图的显示透明度~'),
    ('assistant_page_chat_background_desc', '设置助手聊天页面的背景图片呀'),
    ('assistant_page_chat_model_desc', '设置助手的默认聊天模型，不设置就用全局默认的哦'),
    ('assistant_page_allow_conversation_system_prompt_desc', '允许每个对话单独设置系统提示词~'),
    ('assistant_page_allow_conversation_prompt_injection_desc', '允许每个对话单独绑定提示词注入和世界书哦'),
    ('assistant_page_global_memory_desc', '使用全局共享记忆代替助手隔离记忆；开启后所有助手共享同一份哦'),
    ('assistant_page_max_tokens_desc', '最大生成 Token 数量，留空就是不限制哦'),
    ('assistant_page_local_tools_ask_user_desc', '允许 AI 向你提问来获取更多信息哦'),
    ('assistant_page_local_tools_clipboard_desc', '读取或写入设备剪贴板中的纯文本呀'),
    ('assistant_page_local_tools_javascript_engine_desc', '用 QuickJS 引擎执行 JavaScript 代码，做计算和脚本处理哦'),
    ('assistant_page_local_tools_time_info_desc', '从设备获取当前日期、星期、时间和时区信息呀'),
    ('assistant_page_local_tools_tts_desc', '让 AI 用你选的 TTS 服务朗读文本哦'),
    ('assistant_page_memory_desc', '启用记忆后，模型会尝试记住你的信息并在后续对话里使用；这个功能需要模型支持工具调用才能正常工作哦'),
    ('assistant_page_delete_dialog_text', '确定要删除这个助手吗？删了就回不来了哦。'),
]


def warn(msg):
    print('::warning file=' + ZF + '::batch197 ' + str(msg)[:400])


t = (ROOT / ZF).read_text(encoding='utf-8')
lines = t.split(NL)
applied = []
missing = []
skipped = []

changed = False
for key, new_value in MAPPING:
    prefix = '<string name=' + Q + key + Q + '>'
    hits = [i for i, ln in enumerate(lines) if ln.strip().startswith(prefix)]
    if len(hits) != 1:
        missing.append(key)
        continue
    i = hits[0]
    indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    new_line = indent + prefix + new_value + '</string>'
    if lines[i] == new_line:
        skipped.append(key)
        continue
    lines[i] = new_line
    applied.append(key)
    changed = True

out = NL.join(lines)
if applied:
    (ROOT / ZF).write_text(out, encoding='utf-8')

print('batch197: applied=' + str(len(applied)) + ' skipped=' + str(len(skipped)) + ' missing=' + str(len(missing)))
if missing:
    warn('keys not found (skipped): ' + ','.join(missing))
if applied:
    print('batch197: OK (' + ','.join(applied[:8]) + '...)')
else:
    print('batch197: no change needed')

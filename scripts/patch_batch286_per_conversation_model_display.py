#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch286: 关闭总开关时，输入栏要显示"会话所属助手"的模型，而不是全局当前助手

【问题（snapshot 实读，非推断）】
batch285 关闭总开关后，ChatPage 传 conversationChatModelId = null。
ChatInput 内部的 Elvis 链是：
    conversationChatModelId ?: assistant.chatModelId ?: settings.chatModelId
而 ChatInput 里的 assistant 来自 settings.getCurrentAssistant()（全局当前助手，不是会话所属助手）。
=> 会话属于助手 B、当前选中助手 A 时，关闭开关后输入栏会显示 A 的模型，实际请求走 B 的模型
   （getChatModelOf 用的是 getStoredAssistantOf(conversation)）。

【修法（只改一行，纯标准库，零新增 import）】
ChatPage 关闭分支传会话所属助手自己的 chatModelId：
    setting.assistants.firstOrNull { it.id == conversation.assistantId }?.chatModelId
找不到（助手被删）返回 null -> ChatInput 回退 assistant.chatModelId（getStoredAssistantOf 的 fallback
也是 getCurrentAssistant，语义一致）。

【为什么不用 getStoredAssistantOf】
ChatPage 未 import 该扩展函数；firstOrNull 写法零 import、零签名变化，风险最小。

五查:
 1. import: 零新增
 2. 同文件冲突: 锚点是 batch285 刚写入的唯一行（带 rhPerConvModel285 行尾注释），本批批号更大、串行在后
 3. 作用域: setting: Settings 与 conversation 都在 ChatPage 同一 composable 参数内（285 的同段代码已用）
 4. 括号配对: 新增 if(...){} 的 lambda 1 对花括号 + firstOrNull 1 对圆括号 -> 自配平，balance 差值不变
 5. 函数签名: 零改动

Python 三查: Q 未使用；NL 显式 concat；helper 先定义后用；失败写 diag 不抛异常
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch286'
MARK = 'rhPerConvModel286'
OLD_MARK = 'rhPerConvModel285'
DIAG = 'ci_diag_batch286.txt'
PAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'

report = []


def note(msg):
    report.append(str(msg)[:900])


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def lines_to_text(lines):
    out = ''
    for idx, line in enumerate(lines):
        if idx > 0:
            out += NL
        out += line
    return out


def ind_of(line):
    s = line.lstrip()
    return line[:len(line) - len(s)]


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::' + BATCH + ' diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::' + BATCH + ' diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    p = ROOT / PAGE
    if not p.exists():
        note('ABORT ChatPage.kt missing')
        write_diag()
        return
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        note('already applied')
        write_diag()
        return
    bal0 = balance(t)
    lines = t.split(NL)

    hits = [i for i, ln in enumerate(lines) if OLD_MARK in ln and 'conversationChatModelId' in ln]
    if len(hits) != 1:
        note('ABORT 285 line count=' + str(len(hits)))
        write_diag()
        return
    i = hits[0]
    ind = ind_of(lines[i])
    lines[i] = (ind
                + 'conversationChatModelId = if (setting.displaySetting.perConversationModel) '
                + 'conversation.config?.chatModelId else '
                + 'setting.assistants.firstOrNull { it.id == conversation.assistantId }?.chatModelId, // '
                + MARK)
    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT balance ' + str(bal0) + ' -> ' + str(balance(t2)))
        write_diag()
        return
    for need in [
        'setting.assistants.firstOrNull { it.id == conversation.assistantId }?.chatModelId',
        'conversation.config?.chatModelId',
        MARK,
    ]:
        if need not in t2:
            note('ABORT selfcheck missing: ' + need)
            write_diag()
            return
    if t2.count('conversationChatModelId =') != 1:
        note('ABORT conversationChatModelId count=' + str(t2.count('conversationChatModelId =')))
        write_diag()
        return
    p.write_text(t2, encoding='utf-8')
    note('page OK: switch off -> conversation owner assistant model id')
    write_diag()
    for line in report:
        print('::error::' + BATCH + ' ' + str(line)[:800])


main()
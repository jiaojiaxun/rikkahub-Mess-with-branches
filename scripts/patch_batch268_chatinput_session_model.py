#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch268: ChatInput 两处能力判断改读会话模型（T-M5d）

【现象（snapshot 实读）】ChatInput.kt 里 SearchPickerButton 与 ReasoningButton 的可用性判断
仍读全局模型：
    val chatModel = settings.getCurrentChatModel()   // 喂给 SearchPickerButton 的 model= 实参
    val model = settings.getCurrentChatModel()       // ReasoningButton 的 if 门控（abilities 检查）
会话里换模型（A3/A4 已把写入改成会话级）后，这两个按钮仍按「全局当前模型」判断。
ModelSelector 已在 batch255 改成会话级（rhConvModel255），这两个按钮是漏网之鱼。

【修法】与 ModelSelector 完全相同的 Elvis 链：
    settings.findModelById(conversationChatModelId ?: assistant.chatModelId ?: settings.chatModelId)
语义：会话级 id 优先；老会话无 config 则回退助手模型；再回退全局。
与 ConversationConfig.getChatModelOf 的语义一致（会话优先 + 逐级回退）。

【为什么不用 getChatModelOf(conversation)】
ChatInput 只接收 conversationChatModelId（String?），没有整个 conversation 对象；
与 rhConvModel255 已实读的写法逐字一致，风险最小。

五查:
 1. import: 零新增。findModelById 是 Settings 的成员函数（getCurrentChatModel 内部就是它）；
    conversationChatModelId / assistant 在同一作用域（rhConvModel255 行已用）
 2. 同文件冲突: ChatInput.kt 被 batch255/130 等改过；锚点是两行 strip 全等，与 255 的
    modelId 行不重叠
 3. 作用域: 两处都在 SearchPicker/Reasoning 的同一 lambda 内，conversationChatModelId 可见
 4. 括号: 旧行 1 对 -> 新行 1 对 => 全局 balance 不变（断言）
 5. 签名: 零改动
Python 三查: Q 构造引号; NL 显式 concat; helper 先定义后用; 失败即中止不写盘

【前置自证】settings.getCurrentChatModel() 在 ChatInput.kt 必须恰为 2 处；
若 != 2 => ABORT + dump 每处行号，不写盘。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
DIAG = 'ci_diag_batch268.txt'
TARGET = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/ChatInput.kt'

MARK = 'rhConvModel268'
A_OLD = 'val chatModel = settings.getCurrentChatModel()'
B_OLD = 'val model = settings.getCurrentChatModel()'
ELVIS = 'conversationChatModelId ?: assistant.chatModelId ?: settings.chatModelId'
A_NEW = 'val chatModel = settings.findModelById(' + ELVIS + ') // ' + MARK
B_NEW = 'val model = settings.findModelById(' + ELVIS + ') // ' + MARK
SUB = 'settings.getCurrentChatModel()'

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


class Abort(Exception):
    pass


def unique(lines, needle, label):
    hits = [i for i, ln in enumerate(lines) if ln.strip() == needle]
    if len(hits) != 1:
        note('ABORT ' + label + ': count=' + str(len(hits)) + ' (need 1) -> ' + repr(needle))
        raise Abort(label)
    return hits[0]


def patch():
    p = ROOT / TARGET
    if not p.exists():
        note('ABORT missing ChatInput.kt')
        return
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        note('already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    all_hits = [i for i, ln in enumerate(lines) if SUB in ln]
    if len(all_hits) != 2:
        note('ABORT getCurrentChatModel count=' + str(len(all_hits)) + ' (need 2)')
        for i in all_hits:
            note('  L' + str(i + 1) + ': ' + repr(lines[i].strip()))
        raise Abort('count')

    a = unique(lines, A_OLD, 'chatModel line')
    lines[a] = ind_of(lines[a]) + A_NEW
    b = unique(lines, B_OLD, 'model line')
    lines[b] = ind_of(lines[b]) + B_NEW

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        raise Abort('balance')

    ls2 = t2.split(NL)
    for need in [A_NEW, B_NEW]:
        if len([i for i, ln in enumerate(ls2) if ln.strip() == need]) != 1:
            note('ABORT selfcheck missing ' + need)
            raise Abort('selfcheck')
    if [i for i, ln in enumerate(ls2) if SUB in ln]:
        note('ABORT getCurrentChatModel still present')
        raise Abort('stale')
    if t2.count(MARK) != 2:
        note('ABORT marker count=' + str(t2.count(MARK)) + ' (need 2)')
        raise Abort('marker')

    p.write_text(t2, encoding='utf-8')
    note('ChatInput OK: both capability checks read session model (same Elvis chain as rhConvModel255)')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch268 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch268 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    try:
        patch()
        note('1 chatinput session model DONE')
    except Abort as e:
        note('1 chatinput session model ABORTED (no file written): ' + str(e))
    except Exception as e:
        note('1 chatinput session model EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::batch268 part: chatinput session model')
    sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch268 ' + str(line)[:800])
    print('::error::batch268 END lines=' + str(len(report)))


main()

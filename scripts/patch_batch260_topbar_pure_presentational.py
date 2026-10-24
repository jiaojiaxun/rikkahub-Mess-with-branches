#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch260 v2: 顶部数据源统一（T-M5e）—— 去掉全局 balance 预判，改逐处括号断言

【为什么要 v2】
batch260 与 batch260b 在 CI 上都是 ABORT balance delta unexpected: 0（预期 -1 / -3），
两批都**没有写盘** => T-M5e 至今零落地（ci_diag_batch260.txt / ci_diag_batch260b.txt 实证）。
全局 delta 是个猜谜题：五处改动里只有三处动括号（-1 / -1 / -1），但实测整文件 delta 恒为 0，
说明我对「全局括号净变化」的建模与真实文件不符。

【本批】
不再断言全局 delta，改成**逐处局部断言**：每替换一行，断言该行圆括号净变化等于预期
（0 / -1 / -1 / -1）；插入的每一行断言自身括号平衡。局部断言可证伪、可解释，
不依赖全文其他部分。全局 delta 只记录进 diag 供以后核对。

【改动（5 处，单文件 ChatPage.kt）】
1 ChatPageContent: val assistant = setting.getCurrentAssistant()
                  -> val assistant = setting.getAssistantOf(conversation)
2 ChatPageContent: setting.getCurrentChatModel()?.findProvider(...) is ProviderSetting.Google
                  -> currentChatModel?.findProvider(...) is ProviderSetting.Google
3 TopBar 签名：settings: Settings, 之后插 assistant: Assistant, 与 currentChatModel: Model?
4 TopBar 内部：删掉自己算的两行（改为直接用参数；model 行改成 val model = currentChatModel）
5 TopBar 调用点：settings = setting, 之后补 assistant = assistant, 与 currentChatModel = currentChatModel,

五查:
 1. import 清单: 零新增。ChatPage.kt 已有 me.rerere.ai.provider.Model、
    me.rerere.rikkahub.data.model.Assistant、getAssistantOf、getChatModelOf（batch259 加）
 2. 同文件冲突: 锚点 5 处与 batch228/237/238/255/259 落点不重叠（259 只动 TopBar 内那两行）
 3. 作用域: assistant 与 currentChatModel 都在 ChatPageContent 内；TopBar 新参数与使用点同函数
 4. 括号配对: 逐处断言 0 / -1 / -1 / -1，插入行各自平衡
 5. 函数签名: 仅 TopBar 增加两个参数，唯一调用点同步补实参；ChatPageContent 签名不变
Python 三查: 引号用 Q 构造; NL 显式 concat; helper 先定义后用; 失败即中止不写盘
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
DIAG = 'ci_diag_batch260.txt'

PAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'

MARK = 'rhTopModel260'
A_OLD = 'val assistant = setting.getCurrentAssistant()'
A_NEW = 'val assistant = setting.getAssistantOf(conversation) // ' + MARK
B_OLD = 'setting.getCurrentChatModel()?.findProvider(setting.providers) is ProviderSetting.Google'
B_NEW = 'currentChatModel?.findProvider(setting.providers) is ProviderSetting.Google // ' + MARK
SIG = 'private fun TopBar('
CALL = 'TopBar('
D_OLD = 'val assistant = settings.getAssistantOf(conversation) // rhTopModel259'
D_NEW = '// ' + MARK + ': 直接用参数, 不再重复计算'
E_OLD = 'val model = settings.getChatModelOf(conversation) // rhTopModel259'
E_NEW = 'val model = currentChatModel'
SIG_ADD_1 = 'assistant: Assistant, // ' + MARK
SIG_ADD_2 = 'currentChatModel: Model?, // ' + MARK
CALL_ADD_1 = 'assistant = assistant, // ' + MARK
CALL_ADD_2 = 'currentChatModel = currentChatModel, // ' + MARK

report = []


def note(msg):
    report.append(str(msg)[:900])


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def parens(text):
    return text.count('(') - text.count(')')


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


def set_line(lines, idx, new_line, want_diff, label):
    got = parens(new_line) - parens(lines[idx])
    if got != want_diff:
        note('ABORT ' + label + ': paren diff=' + str(got) + ' (want ' + str(want_diff) + ')')
        note('  old=' + repr(lines[idx].strip()))
        note('  new=' + repr(new_line.strip()))
        raise Abort(label)
    lines[idx] = new_line


def insert_lines(lines, idx, new_lines, label):
    for ln in new_lines:
        if parens(ln) != 0:
            note('ABORT ' + label + ': inserted line not balanced -> ' + repr(ln.strip()))
            raise Abort(label)
    lines[idx:idx] = new_lines


def patch():
    p = ROOT / PAGE
    if not p.exists():
        note('ABORT missing ChatPage.kt')
        return
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        note('already applied')
        return
    if 'rhTopModel259' not in t:
        note('ABORT prerequisite missing: batch259 (rhTopModel259) not applied')
        return

    bal0 = balance(t)
    lines = t.split(NL)

    a = unique(lines, A_OLD, 'content assistant line')
    set_line(lines, a, ind_of(lines[a]) + A_NEW, 0, 'content assistant')

    b = unique(lines, B_OLD, 'allowAudioVideoAttachments')
    set_line(lines, b, ind_of(lines[b]) + B_NEW, -1, 'allowAudioVideoAttachments')

    c = unique(lines, SIG, 'TopBar signature')
    if c + 2 >= len(lines):
        note('ABORT TopBar signature near end of file')
        raise Abort('signature shape')
    if lines[c + 1].strip() != 'hazeState: HazeState,' or lines[c + 2].strip() != 'settings: Settings,':
        note('ABORT TopBar signature shape unexpected: ' + repr(lines[c + 1].strip()) + ' / ' + repr(lines[c + 2].strip()))
        raise Abort('signature shape')
    si = ind_of(lines[c + 2])
    insert_lines(lines, c + 3, [
        si + SIG_ADD_1,
        si + SIG_ADD_2,
    ], 'signature insert')

    d = unique(lines, D_OLD, 'topbar assistant line')
    set_line(lines, d, ind_of(lines[d]) + D_NEW, -1, 'topbar assistant')

    e = unique(lines, E_OLD, 'topbar model line')
    set_line(lines, e, ind_of(lines[e]) + E_NEW, -1, 'topbar model')

    f = unique(lines, CALL, 'TopBar call')
    if f + 2 >= len(lines):
        note('ABORT TopBar call near end of file')
        raise Abort('call shape')
    if lines[f + 1].strip() != 'hazeState = hazeState,' or lines[f + 2].strip() != 'settings = setting,':
        note('ABORT TopBar call shape unexpected: ' + repr(lines[f + 1].strip()) + ' / ' + repr(lines[f + 2].strip()))
        raise Abort('call shape')
    ci = ind_of(lines[f + 2])
    insert_lines(lines, f + 3, [
        ci + CALL_ADD_1,
        ci + CALL_ADD_2,
    ], 'call insert')

    t2 = lines_to_text(lines)
    note('INFO global balance delta=' + str(balance(t2) - bal0) + ' (informational, not asserted)')

    ls2 = t2.split(NL)

    for need in [A_NEW, B_NEW, SIG_ADD_1, SIG_ADD_2, E_NEW, CALL_ADD_1, CALL_ADD_2]:
        if len([i for i, ln in enumerate(ls2) if ln.strip() == need]) < 1:
            note('ABORT selfcheck missing line: ' + need)
            raise Abort('selfcheck')

    if t2.count(MARK) < 7:
        note('ABORT marker count=' + str(t2.count(MARK)) + ' (need >= 7)')
        raise Abort('marker')

    for bad in [A_OLD, B_OLD, D_OLD, E_OLD]:
        if len([i for i, ln in enumerate(ls2) if ln.strip() == bad]) > 0:
            note('ABORT stale line still present: ' + bad)
            raise Abort('stale')

    p.write_text(t2, encoding='utf-8')
    note('ChatPage OK: TopBar pure-presentational, single source of truth')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch260 v2 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch260 v2 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    try:
        patch()
        note('1 topbar pure presentational DONE')
    except Abort as e:
        note('1 topbar pure presentational ABORTED (no file written): ' + str(e))
    except Exception as e:
        note('1 topbar pure presentational EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::batch260 v2 part: topbar pure presentational')
    sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch260 v2 ' + str(line)[:800])
    print('::error::batch260 v2 END lines=' + str(len(report)))


main()

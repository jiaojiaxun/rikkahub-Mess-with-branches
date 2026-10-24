#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch260 v3: 顶部数据源统一（T-M5e）—— 逐处断言「左括号减少数」

【v2 的错（推送后静态自查立刻发现，run#489 前修的）】
v2 用的是 parens(new) - parens(old)，而 parens = 左括号数 - 右括号数。
对一行配平代码，这个值恒为 0（不管删没删括号）=> 所有 -1 预期必定 ABORT。
正确的量是「左括号个数减少了几只」：old.count('(') - new.count('(')。

【v1/v2 为什么都不行】
v1 与 v1b 断言全局 balance（v1 预期 -1、v1b 预期 -3），CI 实测都是 0 => 双双 ABORT，
T-M5e 零落地（ci_diag_batch260.txt / ci_diag_batch260b.txt 实证）。
本批不再用全局 delta，逐行断言左/右括号各减少 want 只，可证伪、与全文其余部分无关。

【改动（5 处，单文件 ChatPage.kt）】
1 ChatPageContent: val assistant = setting.getCurrentAssistant()
                  -> val assistant = setting.getAssistantOf(conversation)           减 0 只
2 ChatPageContent: setting.getCurrentChatModel()?.findProvider(...) is ProviderSetting.Google
                  -> currentChatModel?.findProvider(...) is ProviderSetting.Google   减 1 只
3 TopBar 签名：settings: Settings, 之后插 assistant: Assistant, 与 currentChatModel: Model?
4 TopBar 内部：assistant 那行改注释；model 行改成 val model = currentChatModel             各减 1 只
5 TopBar 调用点：settings = setting, 之后补 assistant = assistant, 与 currentChatModel = currentChatModel,

五查:
 1. import 清单: 零新增（snapshot 实读确认 ChatPage.kt 已有 Model / Assistant /
    getAssistantOf / getChatModelOf）
 2. 同文件冲突: 五处锚点与 batch228/237/238/255/259 不重叠
 3. 作用域: assistant 与 currentChatModel 均在 ChatPageContent；TopBar 新参数与使用点同函数
 4. 括号配对: 逐处断言左右各减 0/1/1/1；插入行断言左右相等
 5. 函数签名: 仅 TopBar 加两个参数，唯一调用点同步补实参
Python 三查: 引号用 Q 构造; NL 显式 concat; helper 先定义后用; 失败即中止不写盘
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
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


def set_line(lines, idx, new_line, want_removed, label):
    old = lines[idx]
    ro = old.count('(') - new_line.count('(')
    rc = old.count(')') - new_line.count(')')
    if ro != want_removed or rc != want_removed:
        note('ABORT ' + label + ': parens removed left=' + str(ro) + ' right=' + str(rc) + ' (want ' + str(want_removed) + ' each)')
        note('  old=' + repr(old.strip()))
        note('  new=' + repr(new_line.strip()))
        raise Abort(label)
    lines[idx] = new_line


def insert_lines(lines, idx, new_lines, label):
    for ln in new_lines:
        if ln.count('(') != ln.count(')'):
            note('ABORT ' + label + ': inserted line unbalanced -> ' + repr(ln.strip()))
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
    set_line(lines, b, ind_of(lines[b]) + B_NEW, 1, 'allowAudioVideoAttachments')

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
    set_line(lines, d, ind_of(lines[d]) + D_NEW, 1, 'topbar assistant')

    e = unique(lines, E_OLD, 'topbar model line')
    set_line(lines, e, ind_of(lines[e]) + E_NEW, 1, 'topbar model')

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
        print('::error::batch260 v3 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch260 v3 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    try:
        patch()
        note('1 topbar pure presentational DONE')
    except Abort as e:
        note('1 topbar pure presentational ABORTED (no file written): ' + str(e))
    except Exception as e:
        note('1 topbar pure presentational EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::batch260 v3 part: topbar pure presentational')
    sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch260 v3 ' + str(line)[:800])
    print('::error::batch260 v3 END lines=' + str(len(report)))


main()

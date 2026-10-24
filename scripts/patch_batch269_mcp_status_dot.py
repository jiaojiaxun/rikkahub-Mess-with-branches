#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch269: MCP 状态点区分 Idle / Connecting / Authorizing / Error（T-N1d）

【现状（snapshot 实读，batch264 之后）】
SettingMcpPage.McpServerItem 有头像分支的右下角状态点：
    val avatarStatusColor = when (status) {
        McpStatus.Connected -> MaterialTheme.extendColors.green6
        is McpStatus.Error, McpStatus.NeedsAuthorization -> MaterialTheme.colorScheme.error
        else -> MaterialTheme.colorScheme.outline
    }
=> Idle / Connecting / Authorizing 全落成灰色 outline，分不出「闲置」「连接中」「授权中」。

【修法】4 行 when 扩成 8 行（新增三个分支，其余不动）：
    Connected                        -> green6（不变）
    Authorizing                      -> tertiary（授权中）
    Connecting, is Reconnecting      -> secondary（连接中/重连中）
    is Error, NeedsAuthorization     -> error（不变）
    Idle                             -> outline（闲置，显式写出）
    else                             -> outline（兜底，防御未来新增状态）

【只改 SettingMcpPage】McpPicker 是助手编辑页的只读列表，不在本批范围（如要同步请说一声）。

五查:
 1. import: 零新增。colorScheme.tertiary / secondary 是 Material3 标准色；extendColors.green6
    与 colorScheme.error / outline 已在原块使用
 2. 同文件冲突: SettingMcpPage.kt 被 253/262/264/264b 改过；锚点是 rhMcpAvatar253 区域内的
    avatarStatusColor 四行块，264 的 if/else 包裹只在外层，不动内部
 3. 作用域: status / MaterialTheme 均在作用域
 4. 括号: 新块无圆括号变化 => 全局 balance 不变（断言）
 5. 签名: 零改动
Python 三查: Q 构造引号; NL 显式 concat; helper 先定义后用; 失败即中止不写盘

【失败保护】四行块形状不符 => ABORT + dump 附近五行，不写盘。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
DIAG = 'ci_diag_batch269.txt'
TARGET = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingMcpPage.kt'

MARK = 'rhMcpDot269'
HEAD = 'val avatarStatusColor = when (status) {'
L_CONNECTED = 'McpStatus.Connected -> MaterialTheme.extendColors.green6'
L_ERR = 'is McpStatus.Error, McpStatus.NeedsAuthorization -> MaterialTheme.colorScheme.error'
L_ELSE = 'else -> MaterialTheme.colorScheme.outline'
L_AUTH = 'McpStatus.Authorizing -> MaterialTheme.colorScheme.tertiary // ' + MARK
L_CONN = 'McpStatus.Connecting, is McpStatus.Reconnecting -> MaterialTheme.colorScheme.secondary // ' + MARK
L_IDLE = 'McpStatus.Idle -> MaterialTheme.colorScheme.outline // ' + MARK

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
        note('ABORT missing SettingMcpPage.kt')
        return
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        note('already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    a = unique(lines, HEAD, 'status dot when')
    if a + 4 >= len(lines):
        note('ABORT when block runs past end of file')
        raise Abort('eof')
    if lines[a + 1].strip() != L_CONNECTED or lines[a + 2].strip() != L_ERR \
            or lines[a + 3].strip() != L_ELSE or lines[a + 4].strip() != '}':
        note('ABORT status dot block shape unexpected')
        for i in range(a, min(a + 6, len(lines))):
            note('  L' + str(i + 1) + ': ' + repr(lines[i].strip()))
        raise Abort('shape')

    hi = ind_of(lines[a])
    new_block = [
        hi + HEAD,
        hi + '    ' + L_CONNECTED,
        hi + '    ' + L_AUTH,
        hi + '    ' + L_CONN,
        hi + '    ' + L_ERR,
        hi + '    ' + L_IDLE,
        hi + '    ' + L_ELSE + ' // ' + MARK,
        hi + '}',
    ]
    lines[a:a + 5] = new_block

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        raise Abort('balance')

    ls2 = t2.split(NL)
    for need in [L_AUTH, L_CONN, L_IDLE]:
        if len([i for i, ln in enumerate(ls2) if ln.strip() == need]) != 1:
            note('ABORT selfcheck missing ' + need)
            raise Abort('selfcheck')
    if t2.count(MARK) != 4:
        note('ABORT marker count=' + str(t2.count(MARK)) + ' (need 4)')
        raise Abort('marker')

    p.write_text(t2, encoding='utf-8')
    note('SettingMcpPage OK: status dot distinguishes Idle / Connecting / Authorizing / Error')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch269 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch269 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    try:
        patch()
        note('1 mcp status dot DONE')
    except Abort as e:
        note('1 mcp status dot ABORTED (no file written): ' + str(e))
    except Exception as e:
        note('1 mcp status dot EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::batch269 part: mcp status dot')
    sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch269 ' + str(line)[:800])
    print('::error::batch269 END lines=' + str(len(report)))


main()

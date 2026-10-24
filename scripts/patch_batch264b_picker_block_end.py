#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch264b: 修 batch264 的 McpPicker Abort（box_end 用错了结束符）

【batch264 结果】
- SettingMcpPage: ✅ `avatar replaces default icon when configured`（Box 块有 `{`，缩进匹配对）
- McpPicker: ❌ `ABORT picker: when_end(322) <= box_end(322)` —— 我的 block_end 找的是 `}`，
  但 McpPicker 里头像块是 `UIAvatar(...)`（函数调用，结束是 `)` 不是 `}`），
  于是 box_end 和 when_end 都落到了 when 块的 `}`（同一行 322）=> 顺序检查失败 => Abort。

【本批修正】
block_end 按"块开始行是否含 `{`"决定结束符：
  · 含 `{` → 结束符 `}`（SettingMcpPage 的 Box 块）
  · 不含 `{` → 结束符 `)`（McpPicker 的 UIAvatar(...) 调用）
其余不变。

五查: 零新增 import；只改 block_end 的结束符选择；SettingMcpPage 已在 batch264 成功（不动）；
括号配平: if/else 外层 1 对 {} => balance 不变（断言）；零签名改动。
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败即中止不写盘
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch264b.txt'

PICKER = 'app/src/main/java/me/rerere/rikkahub/ui/components/ai/McpPicker.kt'

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


def block_end(lines, start, label):
    """块结束 = 向下找第一个「缩进 = 块开始缩进 且内容 = 结束符」的行。
    结束符: 块开始行含 `{` -> `}`（代码块），否则 -> `)`（函数调用）。"""
    indent_len = len(ind_of(lines[start]))
    end_char = '}' if '{' in lines[start] else ')'
    for i in range(start + 1, len(lines)):
        s = lines[i]
        if s.strip() == end_char and len(s) - len(s.lstrip()) == indent_len:
            return i
    note('ABORT ' + label + ': block end not found from line ' + str(start))
    raise Abort(label + ' end')


def patch():
    p = ROOT / PICKER
    if not p.exists():
        note('ABORT missing McpPicker.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhMcpAvatar264' in t:
        note('picker already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    comment = unique(lines, '// rhMcpAvatar253: 只读展示服务器头像（编辑入口在设置页）', 'picker avatar comment')
    box_start = comment + 1
    if lines[box_start].strip() != 'UIAvatar(':
        note('ABORT picker: expected UIAvatar after comment, got ' + repr(lines[box_start]))
        raise Abort('picker box')

    box_end = block_end(lines, box_start, 'picker box')
    when_idx = unique(lines, 'when (status) {', 'picker when status')
    if when_idx <= box_end:
        note('ABORT picker: when_idx(' + str(when_idx) + ') <= box_end(' + str(box_end) + ')')
        raise Abort('picker order')
    when_end = block_end(lines, when_idx, 'picker when')

    ind = ind_of(lines[box_start])
    out = lines[:comment]
    out += [
        ind + '// rhMcpAvatar264: 配了头像才显示（顶替默认图标）；没配则走原状态图标',
        ind + 'if (server.commonOptions.avatar != me.rerere.rikkahub.data.model.Avatar.Dummy) {',
    ]
    out += lines[comment:box_end + 1]
    out += [ind + '} else {']
    out += lines[box_end + 1:when_end + 1]
    out += [ind + '}']
    out += lines[when_end + 1:]

    t2 = lines_to_text(out)
    if balance(t2) != bal0:
        note('ABORT picker balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        raise Abort('picker balance')
    if 'rhMcpAvatar264' not in t2:
        note('ABORT picker marker missing')
        raise Abort('picker marker')
    if t2.count('when (status) {') != 1:
        note('ABORT picker: status-when count should stay 1, got ' + str(t2.count('when (status) {')))
        raise Abort('picker when count')
    p.write_text(t2, encoding='utf-8')
    note('McpPicker OK: avatar replaces default icon when configured')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch264b diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch264b diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    try:
        patch()
        note('1 picker fix DONE')
    except Abort as e:
        note('1 picker fix ABORTED (no file written): ' + str(e))
    except Exception as e:
        note('1 picker fix EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::batch264b part: picker fix')
    sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch264b ' + str(line)[:800])
    print('::error::batch264b END lines=' + str(len(report)))


main()
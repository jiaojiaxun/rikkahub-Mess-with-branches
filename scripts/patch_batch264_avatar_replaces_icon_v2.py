#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch264: MCP 头像顶替默认图标 —— batch262 修正版（我上一批的自检写错了）

【batch262 为什么中止了（诚实复盘）】
ci_diag_batch262.txt 两处 Abort：
  1. SettingMcpPage: `status-when count changed`
     —— 我断言 `when (status) {` 只能有 1 个，但 batch253 加的
        `val avatarStatusColor = when (status) { ... }` 本身就是另一个
        ⇒ 原文件就有 2 个，我的断言写错了（写的是 != 1）。
  2. McpPicker: `when-block end (blank line before Column) not found`
     —— 我用"空行 + Column("定位 when 块结束，但 McpPicker 里 when 块后面
        没有空行，直接是 Column。
两处都是**我的脚本缺陷**，失败保护生效（没写盘、构建绿），但功能没生效。

【本批修正】
1. 定位算法改为"缩进匹配"：块结束 = 向下找第一个「缩进 = 块开始缩进 且内容只有 }」的行，
   对 Box 块与 when 块都成立（它们内部嵌套的 } 缩进都更大）。
2. SettingMcpPage 的断言改为「改动后 when (status) { 仍为 2 个」（原始值就是 2）。
3. McpPicker 不再有"必须有空行"的前提。

【逻辑本身与 batch262 相同】
if (avatar != Avatar.Dummy) { 头像块 } else { 原 when(status) 块 }
· 有头像 → 顶替默认图标；没头像 → 与 batch253 之前完全一致。

五查:
 1. import 清单: 零新增（`Avatar.Dummy` 全限定）
 2. 同文件冲突: 两处都是 batch253 自己插入的块，锚点带 `rhMcpAvatar253` 注释
 3. 作用域: item/server/commonOptions/avatar 均在作用域
 4. 括号配对: 只在外层加 1 对 `{}`，内部块原样 => balance 不变（断言）
 5. 函数签名: 零改动
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败即中止不写盘
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch264.txt'

SETTING = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingMcpPage.kt'
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
    """块结束 = 向下找第一个「缩进 = 块开始缩进 且 strip() == '}'」的行。"""
    indent_len = len(ind_of(lines[start]))
    for i in range(start + 1, len(lines)):
        s = lines[i]
        if s.strip() == '}' and len(s) - len(s.lstrip()) == indent_len:
            return i
    note('ABORT ' + label + ': block end not found from line ' + str(start))
    raise Abort(label + ' end')


def wrap_if_else(lines, comment_idx, box_start, when_idx, avatar_expr, label):
    """Box 块与 when 块包进 if/else。"""
    box_end = block_end(lines, box_start, label + ' box')
    when_end = block_end(lines, when_idx, label + ' when')
    if when_end <= box_end:
        note('ABORT ' + label + ': when_end(' + str(when_end) + ') <= box_end(' + str(box_end) + ')')
        raise Abort(label + ' order')
    ind = ind_of(lines[box_start])
    out = lines[:comment_idx]
    out += [
        ind + '// rhMcpAvatar264: 配了头像才显示（顶替默认图标）；没配则走原状态图标',
        ind + 'if (' + avatar_expr + ') {',
    ]
    out += lines[comment_idx:box_end + 1]
    out += [ind + '} else {']
    out += lines[box_end + 1:when_end + 1]
    out += [ind + '}']
    out += lines[when_end + 1:]
    return out


def patch_setting():
    p = ROOT / SETTING
    if not p.exists():
        note('ABORT missing SettingMcpPage.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhMcpAvatar264' in t:
        note('setting already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)
    comment = unique(lines, '// rhMcpAvatar253: 服务器头像（点击可换图片/表情/链接，复用 UIAvatar 自带面板）',
                     'setting avatar comment')
    box_start = comment + 1
    if lines[box_start].strip() != 'Box(contentAlignment = Alignment.BottomEnd) {':
        note('ABORT setting: expected Box after comment, got ' + repr(lines[box_start]))
        raise Abort('setting box')
    when_idx = unique(lines, 'when (status) {', 'setting when status')
    lines = wrap_if_else(lines, comment, box_start, when_idx,
                         'item.commonOptions.avatar != me.rerere.rikkahub.data.model.Avatar.Dummy', 'setting')
    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT setting balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        raise Abort('setting balance')
    if 'rhMcpAvatar264' not in t2:
        note('ABORT setting marker missing')
        raise Abort('setting marker')
    if t2.count('when (status) {') != 2:
        note('ABORT setting: status-when count should stay 2, got ' + str(t2.count('when (status) {')))
        raise Abort('setting when count')
    p.write_text(t2, encoding='utf-8')
    note('SettingMcpPage OK: avatar replaces default icon when configured')


def patch_picker():
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
    when_idx = unique(lines, 'when (status) {', 'picker when status')
    lines = wrap_if_else(lines, comment, box_start, when_idx,
                         'server.commonOptions.avatar != me.rerere.rikkahub.data.model.Avatar.Dummy', 'picker')
    t2 = lines_to_text(lines)
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
        print('::error::batch264 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch264 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    for name, fn in [
        ('1 SettingMcpPage', patch_setting),
        ('2 McpPicker', patch_picker),
    ]:
        try:
            fn()
            note(name + ' DONE')
        except Abort as e:
            note(name + ' ABORTED (no file written): ' + str(e))
        except Exception as e:
            note(name + ' EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
        print('::error::batch264 part: ' + name)
        sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch264 ' + str(line)[:800])
    print('::error::batch264 END lines=' + str(len(report)))


main()
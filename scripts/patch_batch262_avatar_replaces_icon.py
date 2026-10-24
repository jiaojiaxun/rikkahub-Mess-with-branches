#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch262: MCP 头像顶替默认图标 —— batch253 叠加出来的 UI 冗余（用户指正）

【用户指正（承认是设计失误）】
batch253 给头像做对了，但**没把原来的 MCP 通用图标删掉**，现在界面变成
    [头像] [原 HugeIcons.McpServer 图标] [名称] [设置按钮]
头像和原图标并存，看着累赘。正确做法是：**配了头像就顶替默认图标；没配头像保持原样**。

【当前形态（实读 snapshot，batch253 后）】
SettingMcpPage.McpServerItem:
    Box(contentAlignment = Alignment.BottomEnd) { UIAvatar(...) + 状态点 }
    when (status) { Idle/Connecting/Connected/Error/... -> 原 Icon(...) }
McpPicker.McpPicker:
    UIAvatar(...)
    when (status) { ... -> 原 Icon(...) }

【修法（两个文件同款：if/else 包裹，不动缩进与内部）】
if (avatar != Avatar.Dummy) {
    // 原头像块（含状态点），原样保留
} else {
    // 原 when(status) 块，原样保留
}
· 有头像 → 只显示头像（顶替默认图标），状态点照常表达 Connected/Error
· 没头像 → 行为与 batch253 之前完全一致
· 只在最外层加 if/else/} 三行，内部一行不动 => 风险最小

五查:
 1. import 清单: 零新增（`Avatar.Dummy` 用全限定 `me.rerere.rikkahub.data.model.Avatar.Dummy`）
 2. 同文件冲突: 两处都是 batch253 自己插入的块，锚点带 `rhMcpAvatar253` 注释，与其它批次不重叠
 3. 作用域: item/commonOptions/avatar 在 McpServerItem 内；server/commonOptions/avatar 在 McpPicker 内
 4. 括号配对: 只在外层加 1 对 `{` `}`，内部块自身配平 => 整文件 balance 不变（断言）
 5. 函数签名: 零改动
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败即中止不写盘
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch262.txt'

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


def wrap_with_condition(lines, comment_line, box_start, when_start, avatar_expr, label):
    """把「头像 Box 块」与「when(status) 块」包进 if/else。返回修改后的行列表。"""
    ci = ind_of(lines[box_start])
    out = lines[:comment_line] + [
        ci + '// rhMcpAvatar262: 配了头像才显示（顶替默认图标）；没配则走原状态图标',
        ci + 'if (' + avatar_expr + ') {',
    ] + lines[comment_line:when_start + 1]

    # when_start 是 `when (status) {` 那一行；在它前面加 } else {
    out = out + [ind_of(lines[when_start]) + '} else {']
    # 再把 when 块（到它自己的 } 结束）原样放上
    # when 块结束行 = when_start 之后第一个 `                }`（16 空格）……但可能与 Box 块缩进相同。
    # 用"找到 when 块结束后紧跟的空行 + Column" 来定位。
    end = -1
    for i in range(when_start + 1, min(when_start + 22, len(lines))):
        if lines[i].strip() == '' and i + 1 < len(lines) and lines[i + 1].strip().startswith('Column('):
            end = i  # 空行
            break
    if end < 0:
        note('ABORT ' + label + ': when-block end (blank line before Column) not found')
        raise Abort(label + ' end')
    # when 块最后一个 } 在 end-1
    if lines[end - 1].strip() != '}':
        note('ABORT ' + label + ': when-block last line before blank is not }: ' + repr(lines[end - 1]))
        raise Abort(label + ' close')
    out = out + lines[when_start + 1:end] + [ind_of(lines[when_start]) + '}']
    return out + lines[end:]


def patch_setting():
    p = ROOT / SETTING
    if not p.exists():
        note('ABORT missing SettingMcpPage.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhMcpAvatar262' in t:
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

    when_start = unique(lines, 'when (status) {', 'setting when status')

    lines = wrap_with_condition(
        lines, comment, box_start, when_start,
        'item.commonOptions.avatar != me.rerere.rikkahub.data.model.Avatar.Dummy',
        'setting',
    )

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT setting balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        raise Abort('setting balance')
    if 'rhMcpAvatar262' not in t2:
        note('ABORT setting selfcheck missing marker')
        raise Abort('setting selfcheck')
    if t2.count('when (status) {') != 1:
        note('ABORT setting: status-when count changed')
        raise Abort('setting when count')
    p.write_text(t2, encoding='utf-8')
    note('SettingMcpPage OK: avatar replaces default icon when configured')


def patch_picker():
    p = ROOT / PICKER
    if not p.exists():
        note('ABORT missing McpPicker.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhMcpAvatar262' in t:
        note('picker already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    comment = unique(lines, '// rhMcpAvatar253: 只读展示服务器头像（编辑入口在设置页）', 'picker avatar comment')
    box_start = comment + 1
    if lines[box_start].strip() != 'UIAvatar(':
        note('ABORT picker: expected UIAvatar after comment, got ' + repr(lines[box_start]))
        raise Abort('picker box')

    when_start = unique(lines, 'when (status) {', 'picker when status')

    lines = wrap_with_condition(
        lines, comment, box_start, when_start,
        'server.commonOptions.avatar != me.rerere.rikkahub.data.model.Avatar.Dummy',
        'picker',
    )

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT picker balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        raise Abort('picker balance')
    if 'rhMcpAvatar262' not in t2:
        note('ABORT picker selfcheck missing marker')
        raise Abort('picker selfcheck')
    if t2.count('when (status) {') != 1:
        note('ABORT picker: status-when count changed')
        raise Abort('picker when count')
    p.write_text(t2, encoding='utf-8')
    note('McpPicker OK: avatar replaces default icon when configured')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch262 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch262 diag write FAILED ' + str(e)[:200])
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
        print('::error::batch262 part: ' + name)
        sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch262 ' + str(line)[:800])
    print('::error::batch262 END lines=' + str(len(report)))


main()
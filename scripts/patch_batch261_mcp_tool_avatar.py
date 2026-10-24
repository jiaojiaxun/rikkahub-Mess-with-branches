#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch261 v2: 聊天工具行显示 MCP 服务器头像（T-N1b）—— 修三处缺陷

【为什么重写（诚实复盘）】
ci_diag_batch261.txt 只有一行：
    1 mcp tool avatar EXCEPTION NameError name 'SQ' is not defined
⇒ 上一版在拼 Kotlin 的字符字面量 substringAfter('_') 时用了未定义的 SQ，
  整个 patch() 在写盘前抛异常 ⇒ **零落地**，功能从未生效过。
而且就算加上 SQ，原逻辑也是错的（下一段），所以必须重写而不是补一行。

【三处缺陷】
1. SQ 未定义（NameError）—— 已改为完全不用字符字面量，改字符串前缀匹配。
2. 取错段：原写 `val sid = parts[1].substringAfter('_')` 再去匹配 `it.id.toString()`。
   实证来源 ToolUI.kt（snapshot 实读）：
       // rhToolDisplay (batch229): MCP 工具名美化 mcp__<id>_<server>__<tool>
       val server = parts[1].substringAfter('_')      // ← 这里取的是 server 名
   即 parts[1] = `<id>_<server>`，substringAfter('_') 拿到的是服务器名，
   拿它去比 server.id（UUID）永远不相等 ⇒ 即使不报错也不会显示头像。
   本版改用前缀匹配：chain.startsWith(server.id.toString())
   —— 不依赖分隔符，服务器名里带下划线也安全。
3. 末尾缺外层括号：原 new_block 最后一行是 16 缩进的 `}`（只关了内层 if/else），
   而原块最后一个字符是 12 缩进的 `}`（关 if (loading) { … } else { … }）。
   缺这一行会让整个 ControlledChainOfThoughtStep 的 icon lambda 不闭合 ——
   原版的 balance 断言会抓到，但它从未跑到那里。本版末尾补上。

【修法（不改接口、不改签名，只在 ChatMessageToolStep 的 icon 处加分支）】
是 mcp__ 工具且该服务器配了头像（非 Dummy）=> UIAvatar(16dp, 只读)
否则 => 仍走 renderer.icon(context)，行为完全不变。

【本轮实读确认的四个事实（避免又一轮红）】
1. ui/context/LocalSettings.kt 存在 => `me.rerere.rikkahub.ui.context.LocalSettings` 正确
2. ui/components/ui/UIAvatar.kt 的签名：
      fun UIAvatar(name: String, value: Avatar, modifier: Modifier = Modifier,
                   loading: Boolean = false, onUpdate: ((Avatar) -> Unit)? = null,
                   onClick: (() -> Unit)? = null, showEditBadge: Boolean = true)
   => 本版传 name / value / modifier / showEditBadge 均合法
3. ToolUI.kt 的 rhPrettifyToolName 佐证 toolName 形如 mcp__<id>_<server>__<tool>
4. ChatMessageTools.kt 的 icon 块真实形状（snapshot 实读）：
      } else {
          Icon(
              imageVector = renderer.icon(context),
              contentDescription = null,
              modifier = Modifier.size(16.dp),
              tint = LocalContentColor.current.copy(alpha = 0.7f)
          )
      }
   => lines[a-1] == 'Icon('，lines[a+1] == 'contentDescription = null,'，
      `} else {` 在 a-2，Icon 收尾 `)` 在 a+4，块尾 `}` 在 a+5

五查:
 1. import 清单: 零新增（LocalSettings / Avatar / UIAvatar 均用全限定名）
 2. 同文件冲突: ChatMessageTools.kt 只被 batch249（expanded/onClick）改过，锚点不重叠
 3. 作用域: icon lambda 是 @Composable 上下文，remember / LocalSettings.current 可用；
    rhMcpAvatar 是 val => if 内可智能转换为非空 Avatar
 4. 括号配对: 新块替换原块（含末尾外层 }），全局 balance 不变（断言）
 5. 函数签名: 零改动
Python 三查: 引号用 Q 变量构造; NL 显式 concat; helper 先定义后用; 失败即中止不写盘

【失败保护】锚点不唯一 / 形状不符 / 越界 / balance 变化 / 自检缺项 => Abort 且不写文件，
并把锚点附近三行 dump 进 diag（下次一轮就能定位）。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
DIAG = 'ci_diag_batch261.txt'

TOOLS = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageTools.kt'

MARK = 'rhMcpToolAvatar261'
SERVER_LINE = 'val rhMcpServers = me.rerere.rikkahub.ui.context.LocalSettings.current.mcpServers'
AVATAR_DECL = 'val rhMcpAvatar: me.rerere.rikkahub.data.model.Avatar? = remember(tool.toolName, rhMcpServers) {'
CHAIN_LINE = 'val chain = parts[1]'
MATCH_LINE = 'rhMcpServers.firstOrNull { server -> chain.startsWith(server.id.toString()) }'
DUMMY_CHECK = 'if (rhMcpAvatar != null && rhMcpAvatar != me.rerere.rikkahub.data.model.Avatar.Dummy) {'
UIAVATAR_LINE = 'me.rerere.rikkahub.ui.components.ui.UIAvatar('

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


def dump_around(lines, idx, label):
    lo = idx - 3
    if lo < 0:
        lo = 0
    hi = idx + 4
    for i in range(lo, hi):
        if i < len(lines):
            note('DUMP ' + label + ' L' + str(i) + ': ' + repr(lines[i]))


def patch():
    p = ROOT / TOOLS
    if not p.exists():
        note('ABORT missing ChatMessageTools.kt')
        return
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        note('already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    a = unique(lines, 'imageVector = renderer.icon(context),', 'renderer.icon line')
    if a < 1:
        note('ABORT renderer.icon line at file head, cannot look back')
        raise Abort('head')
    if lines[a - 1].strip() != 'Icon(':
        note('ABORT icon block head unexpected: ' + repr(lines[a - 1].strip()))
        dump_around(lines, a, 'icon-head')
        raise Abort('icon block head')
    if lines[a + 1].strip() != 'contentDescription = null,':
        note('ABORT icon block arg2 unexpected: ' + repr(lines[a + 1].strip()))
        dump_around(lines, a, 'icon-arg2')
        raise Abort('icon block arg2')

    else_idx = -1
    lo = a - 1
    if lo < 0:
        lo = 0
    for i in range(lo, max(-1, a - 8), -1):
        if lines[i].strip() == '} else {':
            else_idx = i
            break
    if else_idx < 0:
        note('ABORT else block not found above icon line')
        dump_around(lines, a, 'else-missing')
        raise Abort('else missing')

    end = a + 4
    if end + 1 >= len(lines):
        note('ABORT icon block runs past end of file')
        raise Abort('eof')
    if lines[end].strip() != ')':
        note('ABORT icon close not at expected line: ' + repr(lines[end].strip()))
        dump_around(lines, end, 'icon-close')
        raise Abort('icon close')
    if lines[end + 1].strip() != '}':
        note('ABORT icon block end not at expected line: ' + repr(lines[end + 1].strip()))
        dump_around(lines, end, 'icon-end')
        raise Abort('icon end')

    ei = ind_of(lines[else_idx])
    new_block = [
        ei + '} else {',
        ei + '    // ' + MARK + ': MCP 工具行优先显示服务器头像（有的话）',
        ei + '    ' + SERVER_LINE,
        ei + '    ' + AVATAR_DECL,
        ei + '        if (!tool.toolName.startsWith(' + Q + 'mcp__' + Q + ')) {',
        ei + '            null',
        ei + '        } else {',
        ei + '            val parts = tool.toolName.split(' + Q + '__' + Q + ')',
        ei + '            if (parts.size < 3) {',
        ei + '                null',
        ei + '            } else {',
        ei + '                ' + CHAIN_LINE,
        ei + '                ' + MATCH_LINE,
        ei + '                    ?.commonOptions?.avatar',
        ei + '            }',
        ei + '        }',
        ei + '    }',
        ei + '    ' + DUMMY_CHECK,
        ei + '        ' + UIAVATAR_LINE,
        ei + '            name = ' + Q + Q + ',',
        ei + '            value = rhMcpAvatar,',
        ei + '            modifier = Modifier.size(16.dp),',
        ei + '            showEditBadge = false,',
        ei + '        )',
        ei + '    } else {',
        ei + '        Icon(',
        ei + '            imageVector = renderer.icon(context),',
        ei + '            contentDescription = null,',
        ei + '            modifier = Modifier.size(16.dp),',
        ei + '            tint = LocalContentColor.current.copy(alpha = 0.7f),',
        ei + '        )',
        ei + '    }',
        ei + '}',
    ]

    lines = lines[:else_idx] + new_block + lines[end + 2:]

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        raise Abort('balance')

    ls2 = t2.split(NL)

    for need in [SERVER_LINE, AVATAR_DECL, CHAIN_LINE, MATCH_LINE, DUMMY_CHECK, UIAVATAR_LINE, MARK]:
        hits = [i for i, ln in enumerate(ls2) if ln.strip() == need]
        if len(hits) != 1:
            if need == MARK:
                continue
            note('ABORT selfcheck count=' + str(len(hits)) + ' for: ' + need)
            raise Abort('selfcheck')

    if t2.count(DUMMY_CHECK) != 1:
        note('ABORT dummy check count=' + str(t2.count(DUMMY_CHECK)))
        raise Abort('dummy')

    keep = [i for i, ln in enumerate(ls2) if ln.strip() == 'imageVector = renderer.icon(context),']
    if len(keep) != 1:
        note('ABORT default icon path count=' + str(len(keep)) + ' (need 1 fallback)')
        raise Abort('fallback')

    p.write_text(t2, encoding='utf-8')
    note('ChatMessageTools OK: MCP tool row shows server avatar when configured (fallback intact)')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch261 v2 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch261 v2 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    try:
        patch()
        note('1 mcp tool avatar DONE')
    except Abort as e:
        note('1 mcp tool avatar ABORTED (no file written): ' + str(e))
    except Exception as e:
        note('1 mcp tool avatar EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::batch261 v2 part: mcp tool avatar')
    sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch261 v2 ' + str(line)[:800])
    print('::error::batch261 v2 END lines=' + str(len(report)))


main()

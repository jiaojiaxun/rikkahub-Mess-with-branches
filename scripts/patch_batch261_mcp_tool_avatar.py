#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch261: 聊天工具行显示 MCP 服务器头像（T-N1b）

【用户需求】MCP 头像不只显示在设置页，也要出现在"聊天里调用 MCP 工具"的那一行。

【实读确认的设计】
- toolName 格式 `mcp__<uuid>_<server>__<tool>`（ToolUI.kt 的 rhPrettifyToolName 已这么解析）
- 图标渲染在 ChatMessageTools.kt 的 ChatMessageToolStep 里:
      icon = {
          if (loading) DotLoading(...)
          else Icon(imageVector = renderer.icon(context), ...)
      }
- `renderer.icon(context)` 返回 ImageVector（HugeIcons），装不下自定义头像
- Avatar 是 sealed class（Dummy / Emoji / Image），需要 UI 组件渲染 —— 不能直接塞进 ImageVector

【修法：不改 ToolUI 接口，只在 ChatMessageToolStep 的 icon 处加一个分支】
if 是 mcp__ 工具且该服务器配了头像（非 Dummy）=> 显示 UIAvatar(16.dp, 只读)
否则 => 仍走原来的 renderer.icon(context)（HugeIcons），行为完全不变
解析与查询全部用**全限定名**，零新增 import：
  · me.rerere.rikkahub.ui.context.LocalSettings.current.mcpServers
  · me.rerere.rikkahub.data.model.Avatar
  · me.rerere.rikkahub.ui.components.ui.UIAvatar
remember 的 key 含 (tool.toolName, mcpServers) => 设置里换头像会立即生效。

五查:
 1. import 清单: 零新增（全限定名）
 2. 同文件冲突: ChatMessageTools.kt 被 batch249(展开) 改过；本批锚点是
    `imageVector = renderer.icon(context),` 一行，与 249 的 expanded/onClick 落点不重叠
 3. 作用域: icon lambda 是 @Composable 上下文，可安全读 LocalSettings.current 与 remember
 4. 括号配对: 新块自身配平 => 整文件 balance 不变（断言）
 5. 函数签名: 零改动（不改 ToolUIRenderer 接口、不改 ChatMessageToolStep 签名）
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败即中止不写盘

【失败保护】锚点不唯一 / balance 变化 / 自检缺项 => Abort 且不写文件。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch261.txt'

TOOLS = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageTools.kt'

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
    p = ROOT / TOOLS
    if not p.exists():
        note('ABORT missing ChatMessageTools.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhMcpToolAvatar261' in t:
        note('already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    # 唯一锚点：renderer.icon(context) 这一行（只在 ChatMessageToolStep 的 else 分支出现）
    a = unique(lines, 'imageVector = renderer.icon(context),', 'renderer.icon line')
    ai = ind_of(lines[a])
    # 校验：上一行是 Icon(，下一行是 contentDescription = null,
    if lines[a - 1].strip() != 'Icon(' or lines[a + 1].strip() != 'contentDescription = null,':
        note('ABORT icon block shape unexpected: ' + repr(lines[a - 1]) + ' / ' + repr(lines[a + 1]))
        raise Abort('icon block shape')

    # 找 else { 的起始行（在 icon 块上方）
    else_idx = -1
    for i in range(a - 1, max(0, a - 12), -1):
        if lines[i].strip() == '} else {':
            else_idx = i
            break
    if else_idx < 0:
        note('ABORT else block not found above icon line')
        raise Abort('else missing')

    ei = ind_of(lines[else_idx])
    new_block = [
        ei + '} else {',
        ei + '    // rhMcpToolAvatar261: MCP 工具行优先显示服务器头像（有的话）',
        ei + '    val rhMcpServers = me.rerere.rikkahub.ui.context.LocalSettings.current.mcpServers',
        ei + '    val rhMcpAvatar = remember(tool.toolName, rhMcpServers) {',
        ei + '        if (!tool.toolName.startsWith("mcp__")) {',
        ei + '            null',
        ei + '        } else {',
        ei + '            val parts = tool.toolName.split("__")',
        ei + '            if (parts.size < 3) {',
        ei + '                null',
        ei + '            } else {',
        ei + '                val sid = parts[1].substringAfter(' + SQ + '_' + SQ + ')',
        ei + '                rhMcpServers.firstOrNull { it.id.toString() == sid }',
        ei + '                    ?.commonOptions?.avatar',
        ei + '            }',
        ei + '        }',
        ei + '    }',
        ei + '    if (rhMcpAvatar != null && rhMcpAvatar != me.rerere.rikkahub.data.model.Avatar.Dummy) {',
        ei + '        me.rerere.rikkahub.ui.components.ui.UIAvatar(',
        ei + '            name = "",',
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
    ]
    # 原来的 else 块（Icon(...)）共 6 行：} else { + Icon( + imageVector=... + contentDescription=... + modifier=... + tint=... + ) + }
    old_count = 1 + 1 + 5 + 1  # else { + Icon( + 4 参数行 + ) + }
    # 从 else_idx 到 a 之后 4 行（Icon 的收尾）
    # 计算：else_idx 到 (a + 4) 是 Icon 块结束
    end = a + 4
    if lines[end].strip() != ')':
        note('ABORT icon close not at expected line: ' + repr(lines[end]))
        raise Abort('icon close')
    if lines[end + 1].strip() != '}':
        note('ABORT icon block end not at expected line: ' + repr(lines[end + 1]))
        raise Abort('icon end')

    lines = lines[:else_idx] + new_block + lines[end + 2:]

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        raise Abort('balance')

    for need in ['rhMcpToolAvatar261', 'val rhMcpServers = me.rerere.rikkahub.ui.context.LocalSettings.current.mcpServers',
                 'me.rerere.rikkahub.ui.components.ui.UIAvatar(', 'rhMcpAvatar != me.rerere.rikkahub.data.model.Avatar.Dummy',
                 'imageVector = renderer.icon(context),']:
        if need not in t2:
            note('ABORT selfcheck missing ' + need)
            raise Abort('selfcheck')

    if t2.count('rhMcpToolAvatar261') < 1:
        note('ABORT marker missing')
        raise Abort('marker')

    p.write_text(t2, encoding='utf-8')
    note('ChatMessageTools OK: MCP tool row shows server avatar when configured')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch261 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch261 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    try:
        patch()
        note('1 mcp tool avatar DONE')
    except Abort as e:
        note('1 mcp tool avatar ABORTED (no file written): ' + str(e))
    except Exception as e:
        note('1 mcp tool avatar EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::batch261 part: mcp tool avatar')
    sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch261 ' + str(line)[:800])
    print('::error::batch261 END lines=' + str(len(report)))


main()
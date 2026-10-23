#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch253: MCP 服务器头像（数据层 + 设置页可换头像 + 助手 MCP 选择器只读显示）

用户需求: 给 MCP 加头像；在设置里能像助手头像那样点一下弹出「选择图片/选择表情/输入链接/重置」；
头像出现在设置页与其它会出现 MCP 的地方。

【关键发现：不需要新写弹窗】
UIAvatar.kt 的签名就是:
    fun UIAvatar(name: String, value: Avatar, modifier, loading, onUpdate: ((Avatar) -> Unit)? = null,
                 onClick: (() -> Unit)? = null, showEditBadge: Boolean = true)
内部已含 showPickOption / showEmojiPicker / showUrlInput + 裁剪 launcher + AlertDialog，
即用户截图里那个「更换头像」面板。传 onUpdate 就会出现可编辑菜单，不传则纯展示。

【三处落点（全部实读确认）】
1. McpConfig.kt 的 McpCommonOptions —— 两个 transport 都共用，加一处即全生效:
       val enable/name/headers/tools/oauth = ...
   +   val avatar: Avatar = Avatar.Dummy,
   @Serializable 且带默认值 => 旧配置反序列化不会因缺字段失败。
2. SettingMcpPage.kt 的 McpServerItem —— 在状态图标 when(status) 之前插入头像块；
   头像的 onUpdate 走新增的 onUpdate(item.clone(commonOptions = commonOptions.copy(avatar = ...)))，
   直接写 settings.mcpServers（而不是打开编辑弹窗——那是 onEdit 的职责）。
   状态仍由原来的 when(status) 图标表达，头像旁再加一个状态色点。
3. McpPicker.kt 的 McpPicker（助手 MCP 页的列表）—— 只读展示头像（showEditBadge = false），
   编辑入口仍只在设置页；状态文字本来就在下面一行，因此保留原状态图标。

【为什么这样做而不是"全部替换成头像"】
状态图标（Idle/Connecting/Connected/Error/NeedsAuthorization）是运维信息，
直接换掉会让"MCP 连不上"变得不可见；所以是「头像 + 状态」并存，不是二选一。

【未做（下一批）】
聊天里的 MCP 工具调用行（ChatMessageTools 的 mcp_ 分支）也要显示服务器头像，
但那里只有 toolName（形如 mcp__server__tool），需要先解析 serverId 再查 settings.mcpServers，
且 icon 走 ToolUIRegistry，改动面比设置页大。本批先把数据与两个列表页做完，下一批接聊天行。

五查:
 1. import 清单:
    · McpConfig.kt: + me.rerere.rikkahub.data.model.Avatar（插在 me.rerere.ai.core.InputSchema 之后）
    · SettingMcpPage.kt: + me.rerere.rikkahub.ui.components.ui.UIAvatar（该文件已用 CustomColors/Switch/Tag 等 ui.components.ui 成员）
    · McpPicker.kt: + me.rerere.rikkahub.ui.components.ui.UIAvatar
    · 状态色点用已有的 drawWithContent + drawCircle（SettingMcpPage 里 dotColor 已这么写），零新增
 2. 同文件冲突: McpConfig.kt / McpPicker.kt 在链上未被他批改动；
    SettingMcpPage.kt 被 batch213(自定义工具入口)/225(搜索框) 改过，但本批锚点在 McpServerItem 内，不重叠
 3. 作用域: SettingMcpPage 的 onUpdate 是 McpServerItem 新增参数，唯一调用点同步补实参；
    McpPicker 里 servers 与 assistant 都在作用域
 4. 括号配对: 三处均为「纯插入」块，新块自身配平 => 整文件 balance 前后相等（脚本断言）
 5. 函数签名: 只给 private fun McpServerItem 增加一个参数（同文件唯一调用点同步更新），
    其余签名（McpPicker / McpPickerListItem / UIAvatar）零改动
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败记录并继续
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SQ = chr(39)
DIAG = 'ci_diag_batch253.txt'

MCPCONFIG = 'app/src/main/java/me/rerere/rikkahub/data/ai/mcp/McpConfig.kt'
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


def find_idx(lines, needle, label):
    hits = [i for i, ln in enumerate(lines) if ln.strip() == needle]
    if len(hits) == 0:
        note('ANCHOR-MISS ' + label + ' -> ' + repr(needle))
        raise RuntimeError('anchor miss ' + label)
    if len(hits) != 1:
        note('ANCHOR-DUP ' + label + ' count=' + str(len(hits)))
        raise RuntimeError('anchor dup ' + label)
    return hits[0]


def patch_mcpconfig():
    p = ROOT / MCPCONFIG
    if not p.exists():
        note('MISSING McpConfig.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhMcpAvatar253' in t:
        note('mcpconfig already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    # import
    if 'import me.rerere.rikkahub.data.model.Avatar' not in t:
        i = find_idx(lines, 'import me.rerere.ai.core.InputSchema', 'McpConfig import anchor')
        lines = lines[:i + 1] + ['import me.rerere.rikkahub.data.model.Avatar // rhMcpAvatar253'] + lines[i + 1:]

    # 字段
    j = find_idx(lines, 'val oauth: McpOAuthState? = null,', 'McpCommonOptions oauth field')
    ji = ind_of(lines[j])
    lines = lines[:j + 1] + [ji + 'val avatar: Avatar = Avatar.Dummy, // rhMcpAvatar253'] + lines[j + 1:]

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('mcpconfig balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        return
    for need in ['import me.rerere.rikkahub.data.model.Avatar',
                 'val avatar: Avatar = Avatar.Dummy, // rhMcpAvatar253']:
        if need not in t2:
            note('mcpconfig selfcheck missing ' + need)
            return
    p.write_text(t2, encoding='utf-8')
    note('mcpconfig OK: McpCommonOptions.avatar added')


def patch_setting_page():
    p = ROOT / SETTING
    if not p.exists():
        note('MISSING SettingMcpPage.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhMcpAvatar253' in t:
        note('setting page already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    # 1. import UIAvatar
    if 'import me.rerere.rikkahub.ui.components.ui.UIAvatar' not in t:
        i = find_idx(lines, 'import me.rerere.rikkahub.ui.components.ui.TagType', 'SettingMcpPage TagType import')
        lines = lines[:i + 1] + ['import me.rerere.rikkahub.ui.components.ui.UIAvatar // rhMcpAvatar253'] + lines[i + 1:]

    # 2. McpServerItem 增加 onUpdate 参数
    a = find_idx(lines, 'onEdit: (McpServerConfig) -> Unit,', 'McpServerItem onEdit param')
    ai = ind_of(lines[a])
    lines = lines[:a + 1] + [ai + 'onUpdate: (McpServerConfig) -> Unit, // rhMcpAvatar253'] + lines[a + 1:]

    # 3. 调用点补实参
    b = find_idx(lines, 'onEdit = {', 'McpServerItem onEdit call site')
    bidx = -1
    for k in range(b + 1, min(b + 6, len(lines))):
        if lines[k].strip() == '},':
            bidx = k
            break
    if bidx < 0:
        note('setting page call-site onEdit body not closed')
        return
    b_ind = ind_of(lines[b])
    extra = [
        b_ind + 'onUpdate = { updated -> // rhMcpAvatar253: 头像改动直接写库，不走编辑弹窗',
        b_ind + '    vm.updateSettings(',
        b_ind + '        settings.copy(',
        b_ind + '            mcpServers = mcpConfigs.map { c ->',
        b_ind + '                if (c.id == updated.id) updated else c',
        b_ind + '            }',
        b_ind + '        )',
        b_ind + '    )',
        b_ind + '},',
    ]
    lines = lines[:bidx + 1] + extra + lines[bidx + 1:]

    # 4. 头像块（插在状态图标 when(status) 之前）
    c = find_idx(lines, 'McpStatus.Idle -> Icon(HugeIcons.MessageBlocked, null)', 'setting status when idle')
    cw = c - 1
    if lines[cw].strip() != 'when (status) {':
        note('setting page unexpected line before status when')
        return
    cw_ind = ind_of(lines[cw])
    avatar_block = [
        cw_ind + '// rhMcpAvatar253: 服务器头像（点击可换图片/表情/链接，复用 UIAvatar 自带面板）',
        cw_ind + 'Box(contentAlignment = Alignment.BottomEnd) {',
        cw_ind + '    UIAvatar(',
        cw_ind + '        name = item.commonOptions.name.ifBlank { "MCP" },',
        cw_ind + '        value = item.commonOptions.avatar,',
        cw_ind + '        onUpdate = { newAvatar ->',
        cw_ind + '            onUpdate(',
        cw_ind + '                item.clone(',
        cw_ind + '                    commonOptions = item.commonOptions.copy(avatar = newAvatar)',
        cw_ind + '                )',
        cw_ind + '            )',
        cw_ind + '        },',
        cw_ind + '    )',
        cw_ind + '    val avatarStatusColor = when (status) {',
        cw_ind + '        McpStatus.Connected -> MaterialTheme.extendColors.green6',
        cw_ind + '        is McpStatus.Error, McpStatus.NeedsAuthorization -> MaterialTheme.colorScheme.error',
        cw_ind + '        else -> MaterialTheme.colorScheme.outline',
        cw_ind + '    }',
        cw_ind + '    Box(',
        cw_ind + '        modifier = Modifier',
        cw_ind + '            .size(10.dp)',
        cw_ind + '            .drawWithContent { drawCircle(color = avatarStatusColor) }',
        cw_ind + '    )',
        cw_ind + '}',
    ]
    lines = lines[:cw] + avatar_block + lines[cw:]

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('setting page balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        return
    for need in ['import me.rerere.rikkahub.ui.components.ui.UIAvatar',
                 'onUpdate: (McpServerConfig) -> Unit,',
                 'onUpdate = { updated ->',
                 'value = item.commonOptions.avatar,']:
        if need not in t2:
            note('setting page selfcheck missing ' + need)
            return
    p.write_text(t2, encoding='utf-8')
    note('setting page OK: avatar + onClick edit + status dot')


def patch_picker():
    p = ROOT / PICKER
    if not p.exists():
        note('MISSING McpPicker.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhMcpAvatar253' in t:
        note('picker already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    if 'import me.rerere.rikkahub.ui.components.ui.UIAvatar' not in t:
        i = find_idx(lines, 'import me.rerere.rikkahub.ui.components.ui.Tag', 'McpPicker Tag import')
        lines = lines[:i + 1] + ['import me.rerere.rikkahub.ui.components.ui.UIAvatar // rhMcpAvatar253'] + lines[i + 1:]

    c = find_idx(lines, 'McpStatus.Idle -> Icon(HugeIcons.Icon1stBracket, null)', 'picker status when idle')
    cw = c - 1
    if lines[cw].strip() != 'when (status) {':
        note('picker unexpected line before status when')
        return
    cw_ind = ind_of(lines[cw])
    block = [
        cw_ind + '// rhMcpAvatar253: 只读展示服务器头像（编辑入口在设置页）',
        cw_ind + 'UIAvatar(',
        cw_ind + '    name = server.commonOptions.name.ifBlank { "MCP" },',
        cw_ind + '    value = server.commonOptions.avatar,',
        cw_ind + '    showEditBadge = false,',
        cw_ind + ')',
    ]
    lines = lines[:cw] + block + lines[cw:]

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('picker balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        return
    for need in ['import me.rerere.rikkahub.ui.components.ui.UIAvatar',
                 'value = server.commonOptions.avatar,',
                 'showEditBadge = false,']:
        if need not in t2:
            note('picker selfcheck missing ' + need)
            return
    p.write_text(t2, encoding='utf-8')
    note('picker OK: read-only avatar in assistant MCP list')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch253 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch253 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    for name, fn in [
        ('1 McpCommonOptions.avatar', patch_mcpconfig),
        ('2 SettingMcpPage avatar (editable)', patch_setting_page),
        ('3 McpPicker avatar (read-only)', patch_picker),
    ]:
        try:
            fn()
            note(name + ' DONE')
        except Exception as e:
            note(name + ' EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
        print('::error::batch253 part: ' + name)
        sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch253 ' + str(line)[:800])
    print('::error::batch253 END lines=' + str(len(report)))


main()
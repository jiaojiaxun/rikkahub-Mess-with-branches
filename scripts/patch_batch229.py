#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch229: 工具调用行 AI 文案(rhToolDisplay)

需求: 工具调用行不再裸显示 mcp__94c8051f_github__get_file_con... 这种内部名,
折叠步骤标题优先展示 AI 调用时生成的人话描述(如「用 GitHub 修改了仓库 README」)。

机制:
 1. ToolDisplayLabel.kt(仓库直提, 本脚本不创建): Tool.withRhDisplayLabel() 给
    schema 注入可选参数 _display 引导模型填写; execute 包装层执行前剥离该字段,
    本地工具与 MCP server 零感知。
 2. 本脚本接线两处:
    GenerationHandler.kt  toolsInternal 的 addAll(tools) → addAll(tools.map { ... })
                          (一处覆盖主链全部工具+记忆工具; ChatService 零改动)
    ToolUI.kt             默认 title 优先读 _display; 兜底 MCP 名称美化;
                          详情弹窗 JSON 剔除 _display 内部字段
 3. 已注册自定义渲染器的 23 个内置工具不受影响(它们的 title 已是人话)。

锚点全部取自 snapshot 分支(CI 真形态)逐字核对:
 TU 与仓库态 SHA 相同(在链无触碰); GH 的 import/addAll 行来自 snapshot 直读。
ChatService 不在本批(压缩区正被另一会话施工, 零交集)。

五查:
 1. import: TU 补 JsonObject + RH_DISPLAY_PARAM; GH 补 withRhDisplayLabel
    (锚=buildMemoryTools import 行后, 字母序相邻)
 2. 同文件冲突: TU snapshot SHA 同仓库态=干净; GH 锚点按 snapshot 形态; CS 不碰
 3. 作用域: 扩展函数 top-level; addAll 在 buildList lambda 内 it:Tool
 4. 括号配对: 每文件 balance 差值断言
 5. 函数签名: title(context) 签名不动; execute 包装类型一致

Python 三查: r 三引号整块内嵌; 无 f-string/walrus; helper 先定义后用; 计数!=1 即 fail
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhToolDisplay'

TU = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/tools/ToolUI.kt'
GH = 'app/src/main/java/me/rerere/rikkahub/data/ai/GenerationHandler.kt'


def fail(path, msg, lines=None, around=-1):
    body = 'batch229 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:100] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + path + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(0)


def ind_of(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def find_one(lines, path, needle, label):
    hits = [i for i, ln in enumerate(lines) if ln.strip() == needle]
    if len(hits) != 1:
        fail(path, label + ' count=' + str(len(hits)), lines, hits[0] if hits else 0)
    return hits[0]


# ==================== ToolUI.kt ====================
tu = (ROOT / TU).read_text(encoding='utf-8')
if MARK not in tu:
    lines = tu.split(NL)
    bal0 = balance(tu)

    # T1: import JsonObject
    if 'import kotlinx.serialization.json.JsonObject' not in tu:
        i = find_one(lines, TU, 'import kotlinx.serialization.json.JsonElement', 'import JsonElement')
        lines.insert(i + 1, 'import kotlinx.serialization.json.JsonObject')

    # T2: import RH_DISPLAY_PARAM(插在 me.rerere.rikkahub.R 行前)
    i = find_one(lines, TU, 'import me.rerere.rikkahub.R', 'import R')
    lines.insert(i, 'import me.rerere.rikkahub.data.ai.tools.RH_DISPLAY_PARAM')

    # T3: 默认 title —— _display 优先, 兜底美化工具名
    t = find_one(lines, TU,
                 'stringResource(R.string.chat_message_tool_call_generic, context.tool.toolName)',
                 'title generic')
    ind = ind_of(lines[t])
    lines[t:t + 1] = [
        ind + 'context.arguments.getStringContent(RH_DISPLAY_PARAM)?.takeIf { it.isNotBlank() }',
        ind + '    ?: stringResource(R.string.chat_message_tool_call_generic, rhPrettifyToolName(context.tool.toolName))',
    ]

    # T4: helpers(插在 getStringContent 定义前)
    g = find_one(lines, TU,
                 'internal fun JsonElement?.getStringContent(key: String): String? =',
                 'getStringContent decl')
    helper = r'''
// rhToolDisplay (batch229): MCP 工具名美化 mcp__<id>_<server>__<tool> -> Server · tool
private fun rhPrettifyToolName(name: String): String {
    if (!name.startsWith("mcp__")) return name
    val parts = name.split("__")
    if (parts.size < 3) return name
    val server = parts[1].substringAfter('_')
    val tool = parts.drop(2).joinToString("__")
    return server.replaceFirstChar { it.uppercase() } + " · " + tool
}

// rhToolDisplay (batch229): 详情 JSON 展示前剔除内部展示参数
private fun JsonElement.rhStrippedDisplay(): JsonElement =
    (this as? JsonObject)?.let { obj ->
        if (obj.containsKey(RH_DISPLAY_PARAM)) JsonObject(obj - RH_DISPLAY_PARAM) else obj
    } ?: this
'''.strip(NL)
    lines[g:g] = helper.split(NL) + ['']

    # T5: 详情弹窗 JSON 剔除 _display
    p = find_one(lines, TU,
                 'code = JsonInstantPretty.encodeToString(context.arguments),',
                 'preview encode')
    lines[p] = ind_of(lines[p]) + 'code = JsonInstantPretty.encodeToString(context.arguments.rhStrippedDisplay()),'

    out = NL.join(lines)
    for need in [
        'import kotlinx.serialization.json.JsonObject',
        'import me.rerere.rikkahub.data.ai.tools.RH_DISPLAY_PARAM',
        'getStringContent(RH_DISPLAY_PARAM)',
        'private fun rhPrettifyToolName(name: String): String {',
        'private fun JsonElement.rhStrippedDisplay(): JsonElement =',
        'context.arguments.rhStrippedDisplay()',
        MARK,
    ]:
        if need not in out:
            fail(TU, 'selfcheck missing: ' + need, lines, 0)
    if balance(out) != bal0:
        fail(TU, 'balance changed', lines, 0)
    (ROOT / TU).write_text(out, encoding='utf-8')
    print('batch229: ToolUI OK')
else:
    print('batch229: ToolUI already applied')


# ==================== GenerationHandler.kt ====================
gh = (ROOT / GH).read_text(encoding='utf-8')
if MARK not in gh:
    lines = gh.split(NL)
    bal0 = balance(gh)

    # G1: import(锚=buildMemoryTools import 行后, 字母序相邻)
    i = find_one(lines, GH,
                 'import me.rerere.rikkahub.data.ai.tools.buildMemoryTools',
                 'import buildMemoryTools')
    lines.insert(i + 1, 'import me.rerere.rikkahub.data.ai.tools.withRhDisplayLabel')

    # G2: toolsInternal 汇入点注入(仅认 16 空格缩进的 addAll(tools), 防误伤)
    hits = [j for j, ln in enumerate(lines)
            if ln.strip() == 'addAll(tools)' and ind_of(ln) == ' ' * 16]
    if len(hits) != 1:
        fail(GH, 'addAll(tools)@16sp count=' + str(len(hits)), lines, hits[0] if hits else 0)
    a = hits[0]
    lines[a] = ind_of(lines[a]) + 'addAll(tools.map { it.withRhDisplayLabel() }) // ' + MARK + ': 注入 AI 展示文案参数'

    out = NL.join(lines)
    for need in [
        'import me.rerere.rikkahub.data.ai.tools.withRhDisplayLabel',
        'addAll(tools.map { it.withRhDisplayLabel() })',
    ]:
        if need not in out:
            fail(GH, 'selfcheck missing: ' + need, lines, 0)
    if balance(out) != bal0:
        fail(GH, 'balance changed', lines, 0)
    (ROOT / GH).write_text(out, encoding='utf-8')
    print('batch229: GenerationHandler OK')
else:
    print('batch229: GenerationHandler already applied')

print('batch229: ALL OK')

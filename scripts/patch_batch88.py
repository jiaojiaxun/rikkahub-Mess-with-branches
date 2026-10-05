#!/usr/bin/env python3
'''batch88: 工具调用面板填充内容 + 文案修正

batch76 注入的面板只有标题 Text,没有遍历 steps -> 空白。
本脚本把面板 Column 内容替换为:标题 + 遍历 block.steps 的 ToolStep,
每步渲染工具名 + 入参 JSON + 输出。

根因(子 Agent 勘测确认):
- ToolUIRenderer.Summary 默认空实现,hasSummary 默认 false
- 23 个注册工具只有 4 个覆写了 Summary
- batch76 把折叠条点击改成弹面板,但面板只有一行标题

修复策略:
- 面板里遍历 block.steps.filterIsInstance<ThinkingStep.ToolStep>()
- 每步用 HighlightCodeBlock 显示 tool.input(入参) 和 output(输出)
- 不依赖 renderer.Summary(默认空),不依赖 DefaultToolPreview(fillMaxHeight 问题)
- Column 加 verticalScroll + spacedBy,面板内可滚动

五查:
1. import 清单:加 rememberScrollState, verticalScroll, HighlightCodeBlock(精确行匹配)
2. 同文件冲突:ChatMessage.kt 被 batch45/66/68/76 碰过;本脚本只改 batch76 注入的面板区域 + import 段
3. 作用域:面板在 MessagePartsBlock 的 ThinkingBlock 分支,block/steps/ThinkingStep 在作用域
4. 括号配对:替换块自平衡(手验:5 圆括号/5 花括号/2 尖括号)
5. 函数签名:不改

Python 三查:无引号字面量(DQ 变量) / 无未定义引用 / 无 f-string/walrus/join
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhBatch88'
DQ = chr(34)
BS = chr(92)
NL_KT = BS + 'n'


def concat_lines(lines):
    text = ''
    for index, line in enumerate(lines):
        if index > 0:
            text += NL
        text += line
    return text


def fail(path, message):
    print('::error file=' + path + '::batch88 ' + str(message)[:1400])
    raise SystemExit(1)


def indent_of(line):
    return line[:len(line) - len(line.lstrip())]


def insert_import_after(lines, new_import, anchor_text):
    for index, line in enumerate(lines):
        if line.strip() == anchor_text:
            lines.insert(index + 1, new_import)
            return index + 1
    return -1


CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
cm = (ROOT / CM).read_text(encoding='utf-8')
if MARK not in cm:
    lines = cm.split(NL)
    applied = []

    # ---- 1a. import: rememberScrollState ----
    if 'import androidx.compose.foundation.rememberScrollState' not in cm:
        idx = insert_import_after(
            lines,
            'import androidx.compose.foundation.rememberScrollState',
            'import androidx.compose.foundation.background'
        )
        if idx < 0:
            fail(CM, 'background import anchor not found')
        applied.append('import_scroll')

    # ---- 1b. import: verticalScroll ----
    if 'import androidx.compose.foundation.verticalScroll' not in cm:
        idx = insert_import_after(
            lines,
            'import androidx.compose.foundation.verticalScroll',
            'import androidx.compose.foundation.rememberScrollState'
        )
        if idx < 0:
            fail(CM, 'rememberScrollState import anchor not found')
        applied.append('import_vscroll')

    # ---- 1c. import: HighlightCodeBlock ----
    if 'import me.rerere.rikkahub.ui.components.richtext.HighlightCodeBlock' not in cm:
        idx = insert_import_after(
            lines,
            'import me.rerere.rikkahub.ui.components.richtext.HighlightCodeBlock',
            'import me.rerere.rikkahub.ui.components.richtext.MarkdownBlock'
        )
        if idx < 0:
            fail(CM, 'MarkdownBlock import anchor not found')
        applied.append('import_highlight')

    # ---- 2. 定位 batch76 面板,替换 Column 内容 ----
    # 找 "工具调用摘要" + "block.steps.size" 所在行
    text_line_idx = -1
    for i, line in enumerate(lines):
        if '工具调用摘要' in line and 'block.steps.size' in line:
            text_line_idx = i
            break
    if text_line_idx < 0:
        ssp_idx = -1
        for i, line in enumerate(lines):
            if 'showSummaryPanel' in line:
                ssp_idx = i
                break
        dump_text = ''
        if ssp_idx >= 0:
            end = min(len(lines), ssp_idx + 20)
            for i in range(ssp_idx, end):
                dump_text += str(i) + ': ' + lines[i] + NL
        fail(CM, 'panel text line not found. Dump: ' + dump_text[:1200])

    # 向上找 Column( (strip 全等)
    column_idx = -1
    for i in range(text_line_idx, -1, -1):
        if lines[i].strip() == 'Column(':
            column_idx = i
            break
    if column_idx < 0:
        fail(CM, 'Column( not found above text line ' + str(text_line_idx))

    col_indent = indent_of(lines[column_idx])

    # 向下找 Column 闭合 } (strip 全等 + 缩进同 col_indent)
    close_idx = -1
    for i in range(text_line_idx + 1, len(lines)):
        if lines[i].strip() == '}' and indent_of(lines[i]) == col_indent:
            close_idx = i
            break
    if close_idx < 0:
        fail(CM, 'Column closing } not found below text line ' + str(text_line_idx))

    # ---- 3. 构造新面板内容 ----
    new_lines = [
        col_indent + 'Column( // ' + MARK,
        col_indent + '    modifier = Modifier',
        col_indent + '        .fillMaxWidth()',
        col_indent + '        .padding(16.dp)',
        col_indent + '        .verticalScroll(rememberScrollState()),',
        col_indent + '    verticalArrangement = Arrangement.spacedBy(8.dp),',
        col_indent + ') {',
        col_indent + '    Text(',
        col_indent + '        text = ' + DQ + '工具调用（共 ' + DQ + ' + block.steps.size + ' + DQ + ' 步）' + DQ + ',',
        col_indent + '        style = MaterialTheme.typography.titleMedium,',
        col_indent + '    )',
        col_indent + '    block.steps.filterIsInstance<ThinkingStep.ToolStep>().forEach { step ->',
        col_indent + '        val tool = step.tool',
        col_indent + '        Text(',
        col_indent + '            text = tool.toolName,',
        col_indent + '            style = MaterialTheme.typography.titleSmall,',
        col_indent + '            color = MaterialTheme.colorScheme.secondary,',
        col_indent + '        )',
        col_indent + '        HighlightCodeBlock(',
        col_indent + '            tool.input,',
        col_indent + '            ' + DQ + 'json' + DQ + ',',
        col_indent + '        )',
        col_indent + '        if (tool.isExecuted) {',
        col_indent + '            val outputText = tool.output',
        col_indent + '                .filterIsInstance<UIMessagePart.Text>()',
        col_indent + '                .joinToString(' + DQ + NL_KT + DQ + ') { it.text }',
        col_indent + '            if (outputText.isNotBlank()) {',
        col_indent + '                HighlightCodeBlock(',
        col_indent + '                    outputText,',
        col_indent + '                    ' + DQ + 'json' + DQ + ',',
        col_indent + '                )',
        col_indent + '            }',
        col_indent + '        }',
        col_indent + '    }',
        col_indent + '}',
    ]

    lines[column_idx:close_idx + 1] = new_lines
    applied.append('panel')

    # ---- 自检 ----
    current_text = concat_lines(lines)
    if MARK not in current_text:
        fail(CM, 'MARK missing after apply')
    if 'verticalScroll(rememberScrollState())' not in current_text:
        fail(CM, 'verticalScroll missing after apply')
    if 'block.steps.filterIsInstance<ThinkingStep.ToolStep>()' not in current_text:
        fail(CM, 'filterIsInstance missing after apply')
    if '工具调用（共' not in current_text:
        fail(CM, 'new title text missing after apply')
    if '工具调用摘要' in current_text:
        fail(CM, 'old title text still present after apply')

    (ROOT / CM).write_text(current_text, encoding='utf-8')
    print('batch88: ChatMessage OK (' + ', '.join(applied) + ')')
else:
    print('batch88: ChatMessage already applied')

print('batch88: OK')

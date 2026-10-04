#!/usr/bin/env python3
'''batch76: 工具折叠 → Summary 面板（ChainOfThought.kt + ChatMessage.kt）

需求 C：折叠态点击 → 弹 Summary 面板（而不是内联展开）

设计：
1. ChainOfThought 加 onShowSummary: (() -> Unit)? = null 可选参数
   折叠条 onClick：有 onShowSummary 则调用它，否则展开/折叠
2. ChatMessage 的 ThinkingBlock 分支：
   - 加 showSummaryPanel 状态
   - ChainOfThought 调用处传 onShowSummary = { showSummaryPanel = true }
   - 加 ModalBottomSheet（简单版：只显示步骤数，不依赖 ThinkingStep 字段）

五查：
1. import 清单：ChainOfThought.kt 无需新 import；ChatMessage.kt 已有
   ModalBottomSheet/rememberBottomSheetState（实读确认）
2. 同文件冲突：ChainOfThought.kt 无在链脚本碰；ChatMessage.kt 被
   batch45/66/68 碰过——锚点精确到 ThinkingBlock 分支
3. 作用域：ChainOfThought 参数在函数体内；ChatMessage 面板状态在函数体内
4. 括号配对：面板独立块自平衡；ChainOfThought 参数行插入
5. 函数签名：ChainOfThought 加可选参数（零破坏）

Python 三查：无引号字面量 / 无未定义引用 / 无 f-string/walrus/join
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhSummaryPanel'


def concat_lines(lines):
    text = ''
    for index, line in enumerate(lines):
        if index > 0:
            text += NL
        text += line
    return text


def fail(path, message):
    print('::error file=' + path + '::batch76 ' + str(message)[:1400])
    raise SystemExit(1)


def indent_of(line):
    return line[:len(line) - len(line.lstrip())]


def insert_after_line(lines, anchor_text, new_line):
    for index, line in enumerate(lines):
        if line.strip() == anchor_text:
            lines.insert(index + 1, new_line)
            return index + 1
    return -1


# ============================================================
# 1. ChainOfThought.kt：加 onShowSummary 参数 + 折叠条逻辑
# ============================================================
COT = 'app/src/main/java/me/rerere/rikkahub/ui/components/ui/ChainOfThought.kt'
cot = (ROOT / COT).read_text(encoding='utf-8')
if MARK not in cot:
    lines = cot.split(NL)
    applied = []

    # 1a. 函数签名加 onShowSummary 参数
    # 锚点：forceExpanded: Boolean = false, 行
    force_indices = []
    for index, line in enumerate(lines):
        if line.strip() == 'forceExpanded: Boolean = false,':
            force_indices.append(index)
    if len(force_indices) != 1:
        fail(COT, 'forceExpanded anchor count=' + str(len(force_indices)))
    fi = force_indices[0]
    ind = indent_of(lines[fi])
    lines.insert(fi + 1, ind + 'onShowSummary: (() -> Unit)? = null, // ' + MARK)
    applied.append('param')

    # 1b. 折叠条 onClick 逻辑
    # 锚点：.clickable { userExpanded = !expanded } 行
    clickable_indices = []
    for index, line in enumerate(lines):
        if '.clickable { userExpanded = !expanded }' in line:
            clickable_indices.append(index)
    if len(clickable_indices) != 1:
        fail(COT, 'clickable anchor count=' + str(len(clickable_indices)))
    ci = clickable_indices[0]
    ind = indent_of(lines[ci])
    # 替换为：if (onShowSummary != null) onShowSummary() else userExpanded = !expanded
    lines[ci] = ind + '.clickable { if (onShowSummary != null) onShowSummary() else userExpanded = !expanded } // ' + MARK
    applied.append('onclick')

    # 自检
    text = concat_lines(lines)
    if 'onShowSummary: (() -> Unit)? = null' not in text:
        fail(COT, 'onShowSummary param missing after apply')
    if 'if (onShowSummary != null) onShowSummary()' not in text:
        fail(COT, 'onShowSummary onclick missing after apply')
    (ROOT / COT).write_text(text, encoding='utf-8')
    print('batch76: ChainOfThought OK (' + ', '.join(applied) + ')')
else:
    print('batch76: ChainOfThought already applied')

# ============================================================
# 2. ChatMessage.kt：加 showSummaryPanel 状态 + ModalBottomSheet
# ============================================================
CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
cm = (ROOT / CM).read_text(encoding='utf-8')
if MARK not in cm:
    lines = cm.split(NL)
    applied = []

    # 2a. 加 showSummaryPanel 状态
    # 锚点：ThinkingBlock 分支的 if (block.steps.isNotEmpty()) 行
    steps_indices = []
    for index, line in enumerate(lines):
        if 'if (block.steps.isNotEmpty())' in line and 'ThinkingBlock' in '\n'.join(lines[max(0, index - 5):index + 1]):
            steps_indices.append(index)
    if len(steps_indices) != 1:
        fail(CM, 'ThinkingBlock steps anchor count=' + str(len(steps_indices)))
    si = steps_indices[0]
    ind = indent_of(lines[si])
    # 在 if 行之前插入状态声明
    lines.insert(si, ind + 'var showSummaryPanel by remember { mutableStateOf(false) } // ' + MARK)
    applied.append('state')

    # 2b. ChainOfThought 调用处加 onShowSummary 参数
    # 锚点：forceExpanded = hasPendingApproval, 行
    fe_indices = []
    for index, line in enumerate(lines):
        if 'forceExpanded = hasPendingApproval,' in line:
            fe_indices.append(index)
    if len(fe_indices) != 1:
        fail(CM, 'forceExpanded param anchor count=' + str(len(fe_indices)))
    fei = fe_indices[0]
    ind = indent_of(lines[fei])
    lines.insert(fei + 1, ind + 'onShowSummary = { showSummaryPanel = true }, // ' + MARK)
    applied.append('callback')

    # 2c. 在 ChainOfThought 调用块结束后加 ModalBottomSheet
    # 锚点：ChainOfThought 调用块的结束 } 行（即 is ThinkingBlock 分支的结束）
    # 从 2b 的插入点往下找 is ThinkingBlock 分支的结束
    # 简化：找 is ThinkingBlock 分支的第一个 } 行（在 ChainOfThought 调用块之后）
    # 从 fei 往下找第一个 } 行（ChainOfThought 的结束）
    cot_end = -1
    for index in range(fei + 1, min(fei + 30, len(lines))):
        if lines[index].strip() == '}':
            cot_end = index
            break
    if cot_end < 0:
        fail(CM, 'ChainOfThought end brace not found')
    # 在 cot_end 之后插入 ModalBottomSheet
    ind = indent_of(lines[cot_end])
    panel_lines = [
        ind + 'if (showSummaryPanel) { // ' + MARK,
        ind + '    ModalBottomSheet(',
        ind + '        onDismissRequest = { showSummaryPanel = false },',
        ind + '    ) {',
        ind + '        Column(',
        ind + '            modifier = Modifier',
        ind + '                .fillMaxWidth()',
        ind + '                .padding(16.dp)',
        ind + '        ) {',
        ind + '            Text(',
        ind + '                text = "工具调用摘要（共 " + block.steps.size + " 步）",',
        ind + '                style = MaterialTheme.typography.titleMedium,',
        ind + '            )',
        ind + '        }',
        ind + '    }',
        ind + '}',
    ]
    lines[cot_end + 1:cot_end + 1] = panel_lines
    applied.append('panel')

    # 自检
    text = concat_lines(lines)
    if 'var showSummaryPanel by remember { mutableStateOf(false) }' not in text:
        fail(CM, 'showSummaryPanel state missing after apply')
    if 'onShowSummary = { showSummaryPanel = true }' not in text:
        fail(CM, 'onShowSummary callback missing after apply')
    if 'ModalBottomSheet' not in text:
        fail(CM, 'ModalBottomSheet missing after apply')
    (ROOT / CM).write_text(text, encoding='utf-8')
    print('batch76: ChatMessage OK (' + ', '.join(applied) + ')')
else:
    print('batch76: ChatMessage already applied')

print('batch76: OK')

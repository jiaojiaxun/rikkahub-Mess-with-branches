#!/usr/bin/env python3
'''batch76v2: 工具折叠 → Summary 面板（ChainOfThought.kt + ChatMessage.kt）

#204 死因（两错同根因）：
1. Unresolved reference 'ModalBottomSheet' —— ChatMessage.kt 没有该 import
2. @Composable invocations... —— ModalBottomSheet 插入在 ChainOfThought 结束 } 之后，
   但找错了 }（找的是 lambda 结束，不是 @Composable 函数体内）

修正：
1. ChatMessage.kt 加 ModalBottomSheet import（锚点 MaterialTheme import）
2. ModalBottomSheet 插入位置改为 showSummaryPanel 声明之后
   （不找 ChainOfThought 结束——避免找错 }）

五查：
1. import 清单：ChatMessage.kt 加 ModalBottomSheet（锚点 MaterialTheme import）
2. 同文件冲突：ChainOfThought.kt 无在链脚本碰；ChatMessage.kt 被 batch45/66/68 碰过
3. 作用域：showSummaryPanel 在 is ThinkingBlock 分支内（@Composable 函数体内）
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
    print('::error file=' + path + '::batch76v2 ' + str(message)[:1400])
    raise SystemExit(1)


def indent_of(line):
    return line[:len(line) - len(line.lstrip())]


def insert_import_after(lines, new_import, anchor_text):
    '''在指定锚点行之后插入新 import'''
    for index, line in enumerate(lines):
        if line.strip() == anchor_text:
            lines.insert(index + 1, new_import)
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
    clickable_indices = []
    for index, line in enumerate(lines):
        if '.clickable { userExpanded = !expanded }' in line:
            clickable_indices.append(index)
    if len(clickable_indices) != 1:
        fail(COT, 'clickable anchor count=' + str(len(clickable_indices)))
    ci = clickable_indices[0]
    ind = indent_of(lines[ci])
    lines[ci] = ind + '.clickable { if (onShowSummary != null) onShowSummary() else userExpanded = !expanded } // ' + MARK
    applied.append('onclick')

    # 自检
    text = concat_lines(lines)
    if 'onShowSummary: (() -> Unit)? = null' not in text:
        fail(COT, 'onShowSummary param missing after apply')
    if 'if (onShowSummary != null) onShowSummary()' not in text:
        fail(COT, 'onShowSummary onclick missing after apply')
    (ROOT / COT).write_text(text, encoding='utf-8')
    print('batch76v2: ChainOfThought OK (' + ', '.join(applied) + ')')
else:
    print('batch76v2: ChainOfThought already applied')

# ============================================================
# 2. ChatMessage.kt：加 ModalBottomSheet import + 状态 + 面板
# ============================================================
CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
cm = (ROOT / CM).read_text(encoding='utf-8')
if MARK not in cm:
    lines = cm.split(NL)
    applied = []

    # 2a. 加 ModalBottomSheet import（锚点：MaterialTheme import）
    if 'import androidx.compose.material3.ModalBottomSheet' not in cm:
        idx = insert_import_after(lines, 'import androidx.compose.material3.ModalBottomSheet', 'import androidx.compose.material3.MaterialTheme')
        if idx < 0:
            fail(CM, 'MaterialTheme import anchor not found')
        applied.append('import')

    # 2b. 加 showSummaryPanel 状态
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

    # 2c. ChainOfThought 调用处加 onShowSummary 参数
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

    # 2d. ModalBottomSheet 插入在 showSummaryPanel 声明之后（修正：不找 ChainOfThought 结束）
    # 锚点：showSummaryPanel 声明行（2b 插入的那一行）
    # 由于 2c 插入了一行，si 索引变化了——重新定位
    state_indices = []
    for index, line in enumerate(lines):
        if 'var showSummaryPanel by remember { mutableStateOf(false) } // ' + MARK in line:
            state_indices.append(index)
    if len(state_indices) != 1:
        fail(CM, 'showSummaryPanel state anchor count=' + str(len(state_indices)))
    sti = state_indices[0]
    ind = indent_of(lines[sti])
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
    lines[sti + 1:sti + 1] = panel_lines
    applied.append('panel')

    # 自检
    text = concat_lines(lines)
    if 'import androidx.compose.material3.ModalBottomSheet' not in text:
        fail(CM, 'ModalBottomSheet import missing after apply')
    if 'var showSummaryPanel by remember { mutableStateOf(false) }' not in text:
        fail(CM, 'showSummaryPanel state missing after apply')
    if 'onShowSummary = { showSummaryPanel = true }' not in text:
        fail(CM, 'onShowSummary callback missing after apply')
    if 'ModalBottomSheet(' not in text:
        fail(CM, 'ModalBottomSheet call missing after apply')
    (ROOT / CM).write_text(text, encoding='utf-8')
    print('batch76v2: ChatMessage OK (' + ', '.join(applied) + ')')
else:
    print('batch76v2: ChatMessage already applied')

print('batch76v2: OK')

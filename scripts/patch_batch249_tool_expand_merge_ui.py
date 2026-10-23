#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch249: 工具步骤就地展开（去序号/去 m-n 计数/默认展开）+ 合并确认剔除新对话 + 合并进度条统一 + 旧备份记忆取证

用户在 run463 实测后提出的四项，锚点全部来自 snapshot 真形态实读（非推测）。

【1 · T-M3 工具步骤「又变成这样了」—— 机制已从源码确认】
ChatMessageTools.kt 的 ChatMessageToolStep 现状:
    var expanded by remember { mutableStateOf(false) }          // 每步默认折叠
    val titleText = if (stepNumber != null) "$stepNumber. " + renderer.title(context) else renderer.title(context)
    ControlledChainOfThoughtStep(
        expanded = expanded,
        onClick = if (context.content != null || isPending || images.isNotEmpty() || webviewParts.isNotEmpty()) {
            { showResult = true }        // ← 行点击被 sheet 抢走
        } else null,
        content = { ...工具名(参数) + renderer.Summary + 图片/拒绝原因... },
    )
ChainOfThought.kt 的 ChainOfThoughtStepContent 里:
    if (onClick != null) { 点击 => onClick() } else if (hasContent) { 点击 => 切换 expanded }
=> onClick 非空时，"就地展开"分支永远走不到，点行只会弹底部 sheet。这就是观感回退的直接原因。

本批按用户选择「C：保留逐行 + 点开必须有原来的解释」落地:
  a. expanded 默认 true（进来就展开，能看到参数与摘要）
  b. onClick = null  => 行点击交还给原地展开/收起
  c. 完整结果（renderer.Preview 底部面板）改由展开区底部的「查看完整结果」按钮打开，逻辑原样保留
  d. 去掉 label 里的 "n. " 序号（stepNumber 参数保留，不动签名，避免影响 ChatMessage.kt 调用点）
  e. 去掉 ChainOfThought 头部 "11/11" 计数

【2 · T-M1 合并确认剔除「本地不存在的对话」】
ConversationMergeAnalyzer.defaultDecision 对 NEW 返回 ConversationMergeDecision.IMPORT
=> 从确认列表剔除 NEW 不影响导入结果，只是不再打扰用户。
MergeConfirmDialog.kt 现状把 NEW 塞进 autoHandled 分组；本批把它移出列表，顶部改显示「另有 N 个新对话将直接导入」。

【3 · T-M2 合并扫描/应用进度与导入导出一致】
ImportExportTab 的范式: CircularWavyProgressIndicator(size 24.dp) + "正在导出：${progress?.detail}"
BackupPage.kt 现状是 batch215 加的纯文字 AlertDialog。本批替换为同款波浪进度环 + 当前事项 + 百分比。
BackupProgress 字段已实读: phase: String, completed: Long, total: Long, detail: String, totalLabel: String,
fraction/percent 派生属性 => percent 可安全使用。

【4 · T-M4 旧备份导入后记忆不显示 —— 本批只取证】
已知: batch230 给 MemoryEntity 加了 conversation_id 列（空串 = 长期/全局），长期查询按该列过滤。
旧备份包里没有该字段 => 反序列化后可能为 null 或缺键，与 "= ''" 的查询条件对不上，于是"一条都不显示"。
但这是**假设**，不盲改。本批 dump 相关源码片段到 ci_diag_batch249.txt:
  · MemoryEntity 的字段与默认值
  · MemoryRepository 的长期/短期查询与映射
  · WebDavSync 里 memory 的备份/恢复段
  · 任何 conversationId/ conversation_id 的出现位置
下一批按实际代码定修法（缺字段按空串兜底 / 导入时显式置空 / 查询兼容 NULL）。

五查:
 1. import 清单: ChatMessageTools 不需要新增（TextButton/stringResource 已 import）；
    MergeConfirmDialog 不需要新增；BackupPage 仅新增 2 条（CircularWavyProgressIndicator、layout.size）；
    ChainOfThought 零新增（删代码）
 2. 同文件冲突: 这 4 个文件在链上被 batch145/156/157/158/215/216/88/136 改过；
    本批锚点逐条取自 snapshot 真形态（含这些批次的注入行），互不重叠
 3. 作用域: hasResultDetail 定义在 ChatMessageToolStep 内、content lambda 之前；newOnly 提到
    MergeConfirmDialog 的 Column 顶部，供顶部统计与 LazyColumn 共用；mergeProgress 在 BackupPage 函数体内
 4. 括号配对: 每个编辑块的旧文本与新文本**各自配平**（删除块自身 () 与 {} 成对），
    因此整文件 balance 编辑前后相等，脚本对此断言
 5. 函数签名: 不改任何函数签名（stepNumber 参数保留但 label 不再使用它）
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败记录并继续
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SQ = chr(39)
DIAG = 'ci_diag_batch249.txt'

CHAIN = 'app/src/main/java/me/rerere/rikkahub/ui/components/ui/ChainOfThought.kt'
TOOLS = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessageTools.kt'
DIALOG = 'app/src/main/java/me/rerere/rikkahub/ui/pages/backup/MergeConfirmDialog.kt'
PAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/backup/BackupPage.kt'
STR_EN = 'app/src/main/res/values/strings.xml'
STR_ZH = 'app/src/main/res/values-zh/strings.xml'
MEM_ENTITY = 'app/src/main/java/me/rerere/rikkahub/data/db/entity/MemoryEntity.kt'
MEM_REPO = 'app/src/main/java/me/rerere/rikkahub/data/repository/MemoryRepository.kt'
WEBDAV = 'app/src/main/java/me/rerere/rikkahub/data/sync/webdav/WebDavSync.kt'

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
        raise RuntimeError('anchor miss: ' + label)
    if len(hits) != 1:
        note('ANCHOR-DUP ' + label + ' count=' + str(len(hits)))
        raise RuntimeError('anchor dup: ' + label)
    return hits[0]


def block(lines, start, count, label):
    got = [ln.strip() for ln in lines[start:start + count]]
    return got


# ---------------------------------------------------------------------------
# 1. ChainOfThought.kt —— 删掉头部 "m/n" 计数
# ---------------------------------------------------------------------------
def patch_chain():
    p = ROOT / CHAIN
    if not p.exists():
        note('MISSING ChainOfThought.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhNoStepCounter249' in t:
        note('chain already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)
    i = find_idx(lines, '// rhToolCallLine: m/n 与「再显示 X 步」同行', 'chain counter comment')
    expect = [
        'Text(',
        'modifier = Modifier.padding(start = 8.dp),',
        'text = visibleSteps.size.toString() + "/" + steps.size,',
        'style = MaterialTheme.typography.labelSmall,',
        'color = MaterialTheme.colorScheme.onSurfaceVariant,',
        ')',
    ]
    got = block(lines, i + 1, len(expect), 'chain counter body')
    if got != expect:
        note('chain body mismatch got=' + repr(got))
        return
    lines = lines[:i] + ['// rhNoStepCounter249: 去掉头部 m/n 计数（用户要求）'] + lines[i + 1 + len(expect):]
    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('chain balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        return
    if 'visibleSteps.size.toString() + "/" + steps.size' in t2:
        note('chain counter still present')
        return
    p.write_text(t2, encoding='utf-8')
    note('chain OK: counter removed')


# ---------------------------------------------------------------------------
# 2. ChatMessageTools.kt —— 默认展开 + 去序号 + 行点击交还展开 + 详情按钮
# ---------------------------------------------------------------------------
def patch_tools():
    p = ROOT / TOOLS
    if not p.exists():
        note('MISSING ChatMessageTools.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhToolExpand249' in t:
        note('tools already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    # 2a. 默认展开
    i = find_idx(lines, 'var expanded by remember { mutableStateOf(false) }', 'tools expanded default')
    lines[i] = ind_of(lines[i]) + 'var expanded by remember { mutableStateOf(true) } // rhToolExpand249: 进来就展开'

    # 2b. 去掉序号前缀
    j = find_idx(lines, 'val titleText = if (stepNumber != null) "$stepNumber. " + renderer.title(context) else renderer.title(context)',
                 'tools titleText')
    lines[j] = ind_of(lines[j]) + 'val titleText = renderer.title(context) // rhToolExpand249: 去掉 n. 序号'

    # 2c. hasResultDetail（插在 hasExtraContent 之后）
    k = find_idx(lines, 'val hasExtraContent = true // rhToolCallLine: 工具调用本身始终可见',
                 'tools hasExtraContent')
    ki = ind_of(lines[k])
    lines = lines[:k + 1] + [
        ki + '// rhToolExpand249: 行点击交给就地展开，完整结果走下方按钮',
        ki + 'val hasResultDetail = context.content != null || isPending || images.isNotEmpty() || webviewParts.isNotEmpty()',
    ] + lines[k + 1:]

    # 2d. onClick -> null
    m = find_idx(lines, 'onClick = if (context.content != null || isPending || images.isNotEmpty() || webviewParts.isNotEmpty()) {',
                 'tools onClick head')
    expect = ['{ showResult = true }', '} else {', 'null', '},']
    got = block(lines, m + 1, len(expect), 'tools onClick body')
    if got != expect:
        note('tools onClick body mismatch got=' + repr(got))
        return
    lines = lines[:m] + ['        onClick = null, // rhToolExpand249: 交还就地展开/收起'] + lines[m + 1 + len(expect):]

    # 2e. 展开区底部加「查看完整结果」按钮
    d = find_idx(lines, 'if (isDenied) {', 'tools isDenied block')
    # 找该 if 块结尾：缩进与 if 相同且为 '}'
    di = ind_of(lines[d])
    close = -1
    for x in range(d + 1, min(d + 14, len(lines))):
        if lines[x] == di + '}':
            close = x
            break
    if close < 0:
        note('tools isDenied close not found')
        return
    btn = [
        di + 'if (hasResultDetail) {',
        di + '    TextButton(onClick = { showResult = true }) {',
        di + '        Text(',
        di + '            text = stringResource(R.string.chat_message_tool_view_detail),',
        di + '            style = MaterialTheme.typography.labelSmall,',
        di + '        )',
        di + '    }',
        di + '}',
    ]
    lines = lines[:close + 1] + btn + lines[close + 1:]

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('tools balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        return
    for need in ['var expanded by remember { mutableStateOf(true) }',
                 'val titleText = renderer.title(context)',
                 'val hasResultDetail = ',
                 'onClick = null,',
                 'R.string.chat_message_tool_view_detail']:
        if need not in t2:
            note('tools selfcheck missing ' + need)
            return
    if 'if (stepNumber != null)' in t2:
        note('tools stepNumber prefix still present')
        return
    p.write_text(t2, encoding='utf-8')
    note('tools OK: default expanded + no prefix + onClick=null + detail button')


# ---------------------------------------------------------------------------
# 3. MergeConfirmDialog.kt —— NEW 不进确认列表
# ---------------------------------------------------------------------------
def patch_dialog():
    p = ROOT / DIALOG
    if not p.exists():
        note('MISSING MergeConfirmDialog.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhMergeSkipNew249' in t:
        note('dialog already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    # 3a. 在 Column 顶部算 newOnly
    c = find_idx(lines, 'Column(modifier = Modifier.fillMaxSize()) {', 'dialog root column')
    ci = ind_of(lines[c])
    lines = lines[:c + 1] + [
        ci + '    // rhMergeSkipNew249: 本地没有的对话没有冲突可确认（默认决策就是 IMPORT），不再进列表',
        ci + '    val newOnly = plan.conversations.count { it.relation == ConversationMergeRelation.NEW }',
    ] + lines[c + 1:]

    # 3b. 顶部统计补一行
    d = find_idx(lines, 'text = "逐项确认差异的处理方式，确认后才会写入",', 'dialog subtitle line')
    # 找到该 Text(...) 块的收尾 ')' —— 从 d 向后找第一个 strip == ')'
    close = -1
    for x in range(d + 1, min(d + 8, len(lines))):
        if lines[x].strip() == ')':
            close = x
            break
    if close < 0:
        note('dialog subtitle close not found')
        return
    si = ind_of(lines[d])
    # 缩进基准取外层 Text( 的缩进（比 text= 少 4）
    base = si[:-4] if len(si) >= 4 else si
    extra = [
        base + 'if (newOnly > 0) {',
        base + '    Text(',
        base + '        text = "另有 " + newOnly + " 个新对话（本地没有）将直接导入",',
        base + '        style = MaterialTheme.typography.bodySmall,',
        base + '        color = MaterialTheme.colorScheme.primary,',
        base + '    )',
        base + '}',
    ]
    lines = lines[:close + 1] + extra + lines[close + 1:]

    # 3c. filter 去掉 NEW
    f = find_idx(lines, 'it.relation == ConversationMergeRelation.NEW ||', 'dialog autoHandled NEW line')
    lines = lines[:f] + lines[f + 1:]

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('dialog balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        return
    if 'val newOnly = plan.conversations.count' not in t2:
        note('dialog newOnly missing')
        return
    if 'it.relation == ConversationMergeRelation.NEW ||' in t2:
        note('dialog NEW filter still present')
        return
    p.write_text(t2, encoding='utf-8')
    note('dialog OK: NEW excluded from confirm list')


# ---------------------------------------------------------------------------
# 4. BackupPage.kt —— 进度条换成导入导出那套
# ---------------------------------------------------------------------------
def patch_page():
    p = ROOT / PAGE
    if not p.exists():
        note('MISSING BackupPage.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhMergeProgress249' in t:
        note('page already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    old_start = find_idx(lines, '// rhMergeLoadingTip (batch215): 合并扫描/应用中的进度提示(此前两状态无 UI, 看起来像卡死)',
                         'page loading tip comment')
    old_block = [
        'if (mergeState is BackupVM.MergeUiState.Preparing || mergeState is BackupVM.MergeUiState.Applying) {',
        'AlertDialog(',
        'onDismissRequest = { },',
        'title = { Text(if (mergeState is BackupVM.MergeUiState.Applying) "正在应用合并…" else "正在扫描备份差异…") },',
        'text = { Text("请稍候，正在处理备份文件，备份较大时需要几秒钟") },',
        'confirmButton = { },',
        ')',
        '}',
    ]
    got = block(lines, old_start + 1, len(old_block), 'page old tip')
    if got != old_block:
        note('page old tip mismatch got=' + repr(got))
        return

    new_block = [
        '// rhMergeProgress249: 与导入/导出备份包一致的进度样式（波浪进度环 + 当前事项 + 百分比）',
        'val mergeProgress by vm.progress.collectAsStateWithLifecycle()',
        'if (mergeState is BackupVM.MergeUiState.Preparing || mergeState is BackupVM.MergeUiState.Applying) {',
        '    val isApplying = mergeState is BackupVM.MergeUiState.Applying',
        '    AlertDialog(',
        '        onDismissRequest = { },',
        '        icon = { CircularWavyProgressIndicator(modifier = Modifier.size(28.dp)) },',
        '        title = { Text(if (isApplying) "正在应用合并…" else "正在扫描备份差异…") },',
        '        text = {',
        '            val p = mergeProgress',
        '            Text(',
        '                if (p == null) {',
        '                    "请稍候，正在处理备份文件…"',
        '                } else {',
        '                    (if (p.detail.isNotBlank()) p.detail else p.phase) +',
        '                        (p.percent?.let { " " + it + "%" } ?: "")',
        '                }',
        '            )',
        '        },',
        '        confirmButton = { },',
        '    )',
        '}',
    ]
    lines = lines[:old_start] + new_block + lines[old_start + 1 + len(old_block):]

    # imports
    ins1 = 'import androidx.compose.material3.CircularWavyProgressIndicator'
    if ins1 not in lines:
        a = find_idx(lines, 'import androidx.compose.material3.ExperimentalMaterial3Api', 'page material3 import')
        lines = lines[:a] + [ins1] + lines[a:]
    ins2 = 'import androidx.compose.foundation.layout.size'
    if ins2 not in lines:
        b = find_idx(lines, 'import androidx.compose.foundation.layout.padding', 'page padding import')
        lines = lines[:b + 1] + [ins2] + lines[b + 1:]

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('page balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        return
    for need in ['// rhMergeProgress249', 'CircularWavyProgressIndicator(modifier = Modifier.size(28.dp))',
                 'import androidx.compose.material3.CircularWavyProgressIndicator',
                 'import androidx.compose.foundation.layout.size']:
        if need not in t2:
            note('page selfcheck missing ' + need)
            return
    if '请稍候，正在处理备份文件，备份较大时需要几秒钟' in t2:
        note('page old text still present')
        return
    p.write_text(t2, encoding='utf-8')
    note('page OK: progress ring + current item')


# ---------------------------------------------------------------------------
# 5. strings —— 查看完整结果
# ---------------------------------------------------------------------------
def patch_strings():
    for rel, text in [(STR_EN, 'View full result'), (STR_ZH, '查看完整结果')]:
        p = ROOT / rel
        if not p.exists():
            note('missing ' + rel)
            continue
        s = p.read_text(encoding='utf-8')
        key = 'chat_message_tool_view_detail'
        if ('name=' + Q + key + Q) in s:
            note('strings already has key in ' + rel)
            continue
        closing = s.rfind('</resources>')
        if closing < 0:
            note('no </resources> in ' + rel)
            continue
        ins = ('    <!-- rhToolExpand249 -->' + NL +
               '    <string name=' + Q + key + Q + '>' + text + '</string>' + NL)
        s = s[:closing] + ins + s[closing:]
        p.write_text(s, encoding='utf-8')
        note('strings OK: ' + rel)


# ---------------------------------------------------------------------------
# 6. T-M4 取证（只读）
# ---------------------------------------------------------------------------
def probe_memory():
    targets = [
        (MEM_ENTITY, ['conversation', 'conversationId', 'conversation_id']),
        (MEM_REPO, ['conversation', 'conversationId', 'conversation_id', 'shortMemory', 'longTerm']),
        (WEBDAV, ['memory', 'Memory']),
    ]
    for rel, kws in targets:
        p = ROOT / rel
        if not p.exists():
            note('probe missing ' + rel)
            continue
        lines = p.read_text(encoding='utf-8').split(NL)
        hits = []
        for i, ln in enumerate(lines):
            for kw in kws:
                if kw in ln:
                    hits.append('L' + str(i + 1) + ':' + ln.strip()[:150])
                    break
        note('probe ' + rel + ' hits=' + str(len(hits)))
        for h in hits[:28]:
            note('probe ' + rel + ' ' + h)


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch249 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch249 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    for name, fn in [
        ('1 chain counter', patch_chain),
        ('2 tools expand', patch_tools),
        ('3 merge dialog NEW', patch_dialog),
        ('4 backup page progress', patch_page),
        ('5 strings', patch_strings),
        ('6 memory probe', probe_memory),
    ]:
        try:
            fn()
            note(name + ' DONE')
        except Exception as e:
            note(name + ' EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
        print('::error::batch249 part: ' + name)
        sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch249 ' + str(line)[:800])
    print('::error::batch249 END lines=' + str(len(report)))


main()
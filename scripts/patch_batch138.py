#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch138: RP 优化 —— Markdown.kt 渲染接线(标准模式颜色覆盖)

来源: Cocolalilal/LastChat 的 RP 优化。把 rpStyleRules 接到 Markdown 渲染管线:
处理 EMPH(*)/STRONG(**)/STRIKETHROUGH(~~)/CODE_SPAN(`) 节点时查 rpStyleRules,
有匹配规则则用自定义颜色覆盖默认样式。

改动清单(11 步):
1. import 区加 RpStyleRule
2. 加 parseColorSafe + resolveRpSpanStyle 两个 helper(放在 TAG 常量前)
3. appendMarkdownNodeContent 签名加 rpStyleRules 参数(默认值,向后兼容)
4. EMPH 分支: withStyle 行前加 val rpStyle,样式改为 rpStyle ?: 默认
5. STRONG 分支: 同上
6. STRIKETHROUGH 分支: 同上
7. CODE_SPAN 分支: val code 行后加 val rpStyle,color 行改为 rpStyle?.color ?: 默认
8. Paragraph 里加 val rpStyleRules = displaySetting.rpStyleRules
9. Paragraph 的 remember key 加 rpStyleRules(规则变化时重组)
10. Paragraph 主调用加 rpStyleRules = rpStyleRules
11. 3 处递归调用加 rpStyleRules = rpStyleRules(warn-only,不阻塞)

自定义模式(%text% 等)不在本 patch 范围,后续单独做。

五查:
1. import 清单: 只加 RpStyleRule(精确行匹配 Settings import)
2. 同文件冲突: Markdown.kt 无在链 patch 碰过
3. 作用域: rpStyleRules 是函数参数/局部变量,递归传参用具名参数
4. 括号配对: 所有替换/插入块自平衡,最终全文配平校验
5. 函数签名: 加参数带默认值,向后兼容;递归调用可选传参

Python 三查: 引号=chr构造(DQ) / NL 手写 concat / 无 f-string/walrus/join / fail-loud
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
DQ = chr(34)
MARK = 'rhRpStyleRules'

MD = 'app/src/main/java/me/rerere/rikkahub/ui/components/richtext/Markdown.kt'


def fail(path, msg, lines=None, around=-1):
    body = 'batch138 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 2)
        hi = min(len(lines), around + 3)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:80] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + path + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


def warn(msg):
    print('::warning::batch138 ' + str(msg)[:500])


def concat_lines(lines):
    text = ''
    first = True
    for line in lines:
        if not first:
            text += NL
        text += line
        first = False
    return text


def indent_of(line):
    return line[:len(line) - len(line.lstrip())]


def find_unique(lines, needle, label, path):
    hits = []
    for i, ln in enumerate(lines):
        if ln.strip() == needle:
            hits.append(i)
    if len(hits) != 1:
        fail(path, label + ' count=' + str(len(hits)), lines, hits[0] if hits else 0)
    return hits[0]


md_path = ROOT / MD
text = md_path.read_text(encoding='utf-8')
if MARK in text:
    print('batch138: Markdown already applied')
    raise SystemExit(0)

lines = text.split(NL)
applied = []

# ===================== 1. import RpStyleRule =====================
ii = find_unique(lines, 'import me.rerere.rikkahub.data.datastore.Settings', 'Settings import', MD)
lines.insert(ii + 1, 'import me.rerere.rikkahub.data.datastore.RpStyleRule // ' + MARK)
applied.append('import')

# ===================== 2. helper 函数(parseColorSafe + resolveRpSpanStyle) =====================
ti = find_unique(lines, 'private const val TAG = "Markdown"', 'TAG const', MD)
helper_lines = [
    '',
    '// ' + MARK + ': 解析颜色字符串为 Compose Color,失败返回 null',
    'internal fun parseColorSafe(colorStr: String): Color? {',
    '    return try {',
    '        val clean = colorStr.trim()',
    '        when {',
    '            clean.startsWith(' + DQ + '#' + DQ + ') && clean.length == 7 -> {',
    '                Color((' + DQ + 'FF' + DQ + ' + clean.removePrefix(' + DQ + '#' + DQ + ')).toLong(16))',
    '            }',
    '            clean.startsWith(' + DQ + '#' + DQ + ') && clean.length == 9 -> {',
    '                Color(clean.removePrefix(' + DQ + '#' + DQ + ').toLong(16))',
    '            }',
    '            else -> null',
    '        }',
    '    } catch (e: Exception) {',
    '        null',
    '    }',
    '}',
    '',
    '// ' + MARK + ': 按 pattern 查 rpStyleRules,返回带自定义颜色的 SpanStyle(或 null)',
    'internal fun resolveRpSpanStyle(',
    '    pattern: String,',
    '    colorScheme: ColorScheme,',
    '    rpStyleRules: List<RpStyleRule>,',
    '): SpanStyle? {',
    '    val rule = rpStyleRules.find { it.pattern == pattern && it.enabled } ?: return null',
    '    val customColor = parseColorSafe(rule.colorHex) ?: return null',
    '    return SpanStyle(color = customColor)',
    '}',
    '',
]
for j, b in enumerate(helper_lines):
    lines.insert(ti + j, b)
applied.append('helpers')

# ===================== 3. appendMarkdownNodeContent 签名加参数 =====================
# 先找函数声明行(唯一)
fn_idx = find_unique(lines, 'private fun AnnotatedString.Builder.appendMarkdownNodeContent(', 'appendMarkdownNodeContent decl', MD)
# 从函数声明往后找第一个 onClickCitation: (String) -> Unit = {}, (参数列表最后一行)
sig_idx = -1
for i in range(fn_idx, min(fn_idx + 15, len(lines))):
    if lines[i].strip() == 'onClickCitation: (String) -> Unit = {},':
        sig_idx = i
        break
if sig_idx < 0:
    fail(MD, 'onClickCitation param in signature not found', lines, fn_idx)
sind = indent_of(lines[sig_idx])
lines.insert(sig_idx, sind + 'rpStyleRules: List<RpStyleRule> = emptyList(), // ' + MARK)
applied.append('sig')

# ===================== 4. EMPH 分支 =====================
ei = find_unique(lines, 'node.type == MarkdownElementTypes.EMPH -> {', 'EMPH branch', MD)
emph_next = lines[ei + 1].strip()
if emph_next != 'withStyle(SpanStyle(fontStyle = FontStyle.Italic)) {':
    fail(MD, 'EMPH next line unexpected: ' + emph_next, lines, ei)
ewind = indent_of(lines[ei + 1])
lines[ei + 1] = ewind + 'val rpStyle = resolveRpSpanStyle(' + DQ + '*' + DQ + ', colorScheme, rpStyleRules) // ' + MARK
lines.insert(ei + 2, ewind + 'withStyle(rpStyle ?: SpanStyle(fontStyle = FontStyle.Italic)) {')
applied.append('emph')

# ===================== 5. STRONG 分支 =====================
stri = find_unique(lines, 'node.type == MarkdownElementTypes.STRONG -> {', 'STRONG branch', MD)
strong_next = lines[stri + 1].strip()
if strong_next != 'withStyle(SpanStyle(fontWeight = FontWeight.Bold)) {':
    fail(MD, 'STRONG next line unexpected: ' + strong_next, lines, stri)
stwind = indent_of(lines[stri + 1])
lines[stri + 1] = stwind + 'val rpStyle = resolveRpSpanStyle(' + DQ + '**' + DQ + ', colorScheme, rpStyleRules) // ' + MARK
lines.insert(stri + 2, stwind + 'withStyle(rpStyle ?: SpanStyle(fontWeight = FontWeight.Bold)) {')
applied.append('strong')

# ===================== 6. STRIKETHROUGH 分支 =====================
sti = find_unique(lines, 'node.type == GFMElementTypes.STRIKETHROUGH -> {', 'STRIKETHROUGH branch', MD)
strike_next = lines[sti + 1].strip()
if strike_next != 'withStyle(SpanStyle(textDecoration = TextDecoration.LineThrough)) {':
    fail(MD, 'STRIKETHROUGH next line unexpected: ' + strike_next, lines, sti)
skwind = indent_of(lines[sti + 1])
lines[sti + 1] = skwind + 'val rpStyle = resolveRpSpanStyle(' + DQ + '~~' + DQ + ', colorScheme, rpStyleRules) // ' + MARK
lines.insert(sti + 2, skwind + 'withStyle(rpStyle ?: SpanStyle(textDecoration = TextDecoration.LineThrough)) {')
applied.append('strike')

# ===================== 7. CODE_SPAN 分支 =====================
ci = find_unique(lines, 'node.type == MarkdownElementTypes.CODE_SPAN -> {', 'CODE_SPAN branch', MD)
code_next = lines[ci + 1].strip()
if code_next != 'val code = node.getTextInNode(content).trim(\'`\')':
    fail(MD, 'CODE_SPAN next line unexpected: ' + code_next, lines, ci)
cnind = indent_of(lines[ci + 1])
# 在 val code 行后插入 val rpStyle
lines.insert(ci + 2, cnind + 'val rpStyle = resolveRpSpanStyle(' + DQ + '`' + DQ + ', colorScheme, rpStyleRules) // ' + MARK)
# 在 CODE_SPAN 分支范围内找 color = colorScheme.primary, 行并替换
color_found = False
for i in range(ci, min(ci + 15, len(lines))):
    if lines[i].strip() == 'color = colorScheme.primary,':
        chind = indent_of(lines[i])
        lines[i] = chind + 'color = rpStyle?.color ?: colorScheme.primary, // ' + MARK
        color_found = True
        break
if not color_found:
    fail(MD, 'CODE_SPAN color line not found', lines, ci)
applied.append('code_span')

# ===================== 8. Paragraph 获取 rpStyleRules =====================
# 收窄到 Paragraph 函数体内: 先找函数声明,再在函数体内找锚点
# (enableLatexRendering 在 Markdown.kt 出现 3 次: Paragraph + INLINE_MATH 块 + 其他)
para_fn_idx = find_unique(lines, 'private fun Paragraph(', 'Paragraph function decl', MD)
# 找 Paragraph 函数体内的 enableLatexRendering 行
pi = -1
for i in range(para_fn_idx, len(lines)):
    if lines[i].strip() == 'val enableLatexRendering = LocalSettings.current.displaySetting.enableLatexRendering':
        pi = i
        break
    # 遇到下一个 @Composable 或 private fun 说明出了 Paragraph 范围,停止
    if i > para_fn_idx and (lines[i].strip().startswith('@Composable') or lines[i].strip().startswith('private fun ')):
        break
if pi < 0:
    fail(MD, 'Paragraph enableLatexRendering not found in function body', lines, para_fn_idx)
pind = indent_of(lines[pi])
lines.insert(pi + 1, pind + 'val rpStyleRules = LocalSettings.current.displaySetting.rpStyleRules // ' + MARK)
applied.append('para_get')

# ===================== 9. remember key 加 rpStyleRules =====================
# 收窄到 Paragraph 函数体内
# 注意: 实际行是 'val annotatedString = remember(content, enableLatexRendering, latexColorArgb) {'
# 不是纯 'remember(...)',所以用 in 包含匹配
ri = -1
for i in range(para_fn_idx, len(lines)):
    if 'remember(content, enableLatexRendering, latexColorArgb) {' in lines[i]:
        ri = i
        break
    if i > para_fn_idx and (lines[i].strip().startswith('@Composable') or lines[i].strip().startswith('private fun ')):
        break
if ri < 0:
    fail(MD, 'remember key not found in Paragraph function body', lines, para_fn_idx)
rind = indent_of(lines[ri])
lines[ri] = rind + 'remember(content, enableLatexRendering, latexColorArgb, rpStyleRules) { // ' + MARK
applied.append('remember_key')

# ===================== 10. 主调用传参 =====================
# 收窄到 Paragraph 函数体内: 从 remember 行往后找第一个 latexColorArgb = latexColorArgb,
call_idx = -1
for i in range(ri, min(ri + 25, len(lines))):
    if lines[i].strip() == 'latexColorArgb = latexColorArgb,':
        call_idx = i
        break
if call_idx < 0:
    fail(MD, 'main call latexColorArgb not found after remember', lines, ri)
clind = indent_of(lines[call_idx])
lines.insert(call_idx + 1, clind + 'rpStyleRules = rpStyleRules, // ' + MARK)
applied.append('call_param')

# ===================== 11. 递归调用传参(warn-only) =====================
# 特征: onClickCitation = onClickCitation (无逗号,参数列表最后一行)
# 且上一行是 latexColorArgb = latexColorArgb,
rec_count = 0
for i in range(len(lines)):
    if lines[i].strip() == 'onClickCitation = onClickCitation':
        # 确认上一行是 latexColorArgb = latexColorArgb,
        if i > 0 and lines[i - 1].strip() == 'latexColorArgb = latexColorArgb,':
            rind2 = indent_of(lines[i])
            lines[i] = rind2 + 'onClickCitation = onClickCitation,'
            lines.insert(i + 1, rind2 + 'rpStyleRules = rpStyleRules, // ' + MARK)
            rec_count += 1
            # 插入后行号漂移,但我们是顺序遍历,后面的行号已变——重新扫描代价高,
            # 改为标记位置统一处理?不,直接break循环重扫
            break
# 上面只处理了第一个,再扫两次(每次插入后重扫)
for _ in range(2):
    for i in range(len(lines)):
        if lines[i].strip() == 'onClickCitation = onClickCitation':
            if i > 0 and lines[i - 1].strip() == 'latexColorArgb = latexColorArgb,':
                rind2 = indent_of(lines[i])
                lines[i] = rind2 + 'onClickCitation = onClickCitation,'
                lines.insert(i + 1, rind2 + 'rpStyleRules = rpStyleRules, // ' + MARK)
                rec_count += 1
                break
if rec_count != 3:
    warn('recursive call param: expected 3, got ' + str(rec_count) + ' (nested styles may miss custom color)')

applied.append('recursive(' + str(rec_count) + ')')

# ===================== 自检 =====================
out = concat_lines(lines)
for need in [
    'import me.rerere.rikkahub.data.datastore.RpStyleRule',
    'internal fun parseColorSafe(',
    'internal fun resolveRpSpanStyle(',
    'rpStyleRules: List<RpStyleRule> = emptyList(),',
    'val rpStyleRules = LocalSettings.current.displaySetting.rpStyleRules',
    'remember(content, enableLatexRendering, latexColorArgb, rpStyleRules)',
    'rpStyleRules = rpStyleRules,',
    'resolveRpSpanStyle(' + DQ + '*' + DQ + ', colorScheme, rpStyleRules)',
    'resolveRpSpanStyle(' + DQ + '**' + DQ + ', colorScheme, rpStyleRules)',
    'resolveRpSpanStyle(' + DQ + '~~' + DQ + ', colorScheme, rpStyleRules)',
    'resolveRpSpanStyle(' + DQ + '`' + DQ + ', colorScheme, rpStyleRules)',
    'color = rpStyle?.color ?: colorScheme.primary,',
]:
    if need not in out:
        fail(MD, 'selfcheck missing: ' + need, lines, 0)
if MARK not in out:
    fail(MD, 'marker missing', lines, 0)
# 括号配平(全文)
if (text.count('(') - text.count(')')) != (out.count('(') - out.count(')')):
    fail(MD, 'paren balance changed', lines, 0)
if (text.count('{') - text.count('}')) != (out.count('{') - out.count('}')):
    fail(MD, 'brace balance changed', lines, 0)

md_path.write_text(out, encoding='utf-8')
print('batch138: Markdown OK (' + ', '.join(applied) + ')')
print('batch138: ALL OK')

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch144: RP 优化语义修复 —— 替换 → 合并(保留原样式,只覆盖颜色)

对抗性检查发现的真实缺陷:
batch138 的 resolveRpSpanStyle 返回 SpanStyle(color=customColor),
然后各分支用 withStyle(rpStyle ?: SpanStyle(fontStyle=Italic))。
命中规则时整个 SpanStyle 被替换 → 斜体/粗体/删除线丢失。

参考实现(LastChat Markdown.kt)铁证:
  val emphColor = emphRule?.let { parseColorSafe(it.colorHex) }
  SpanStyle(fontStyle = FontStyle.Italic, color = emphColor ?: Color.Unspecified)
即: 样式永远保留,颜色只在有规则时覆盖(merge 语义)。

修法:
1. resolveRpSpanStyle → resolveRpColor(返回 Color? 而非 SpanStyle?)
2. EMPH 分支: withStyle(SpanStyle(fontStyle=Italic, color=rpColor ?: Unspecified))
3. STRONG 分支: 同上(fontWeight=Bold)
4. STRIKETHROUGH 分支: 同上(textDecoration=LineThrough)
5. CODE_SPAN 分支: color = rpColor ?: colorScheme.primary(已是合并,只需改引用)

锚点全部是 batch138 注入的 CI 形态(rhRpStyleRules 标记行),顺序在 batch138 之后。

五查:
1. import 清单: 零新增(Color/ColorScheme/SpanStyle 已在)
2. 同文件冲突: Markdown.kt 被 batch138 碰过(我改的正是 batch138 注入的代码),
   锚点都是 batch138 注入行(rhRpStyleRules 标记),不受其他 patch 影响
3. 作用域: 各分支体内的 val 替换,不跨作用域
4. 括号配对: 函数整体替换自平衡;分支行替换同行内
5. 函数签名: resolveRpSpanStyle→resolveRpColor 签名变化,
   但调用点全部同步修改,无残留引用

Python 三查: 引号=chr构造(DQ) / NL 手写 concat / 无 f-string/walrus/join / fail-loud
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
DQ = chr(34)
OLD_MARK = 'rhRpStyleRules'
MARK = 'rhRpMerge144'

MD = 'app/src/main/java/me/rerere/rikkahub/ui/components/richtext/Markdown.kt'


def fail(path, msg, lines=None, around=-1):
    body = 'batch144 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 2)
        hi = min(len(lines), around + 3)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:80] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + path + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


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


def find_fn_end(lines, start, path):
    '''从 start 行开始找函数结束(花括号配平)'''
    depth = 0
    seen_brace = False
    for j in range(start, len(lines)):
        for ch in lines[j]:
            if ch == '{':
                depth += 1
                seen_brace = True
            elif ch == '}':
                depth -= 1
        if seen_brace and depth <= 0:
            return j
    fail(path, 'function end not found', lines, start)
    return -1


md_path = ROOT / MD
text = md_path.read_text(encoding='utf-8')
if MARK in text:
    print('batch144: Markdown already applied')
    raise SystemExit(0)

lines = text.split(NL)
applied = []

# ===================== 1. resolveRpSpanStyle → resolveRpColor =====================
# 找 batch138 注入的函数定义
fn_idx = find_unique(lines, 'internal fun resolveRpSpanStyle(', 'resolveRpSpanStyle decl', MD)
fn_end = find_fn_end(lines, fn_idx, MD)
fn_ind = indent_of(lines[fn_idx])
new_fn = [
    '// ' + MARK + ': 按 pattern 查 rpStyleRules,返回自定义颜色(或 null)',
    '// 合并语义: 调用方保留原样式,只在有规则时覆盖 color',
    'internal fun resolveRpColor(',
    '    pattern: String,',
    '    colorScheme: ColorScheme,',
    '    rpStyleRules: List<RpStyleRule>,',
    '): Color? {',
    '    val rule = rpStyleRules.find { it.pattern == pattern && it.enabled } ?: return null',
    '    return parseColorSafe(rule.colorHex)',
    '}',
]
lines[fn_idx:fn_end + 1] = new_fn
applied.append('resolveFn')

# ===================== 2. EMPH 分支 =====================
# 锚点: val rpStyle = resolveRpSpanStyle("*", colorScheme, rpStyleRules) // rhRpStyleRules
ei = find_unique(
    lines,
    'val rpStyle = resolveRpSpanStyle(' + DQ + '*' + DQ + ', colorScheme, rpStyleRules) // ' + OLD_MARK,
    'EMPH rpStyle line',
    MD,
)
eind = indent_of(lines[ei])
lines[ei] = eind + 'val rpColor = resolveRpColor(' + DQ + '*' + DQ + ', colorScheme, rpStyleRules) // ' + MARK
# 下一行是 withStyle(rpStyle ?: SpanStyle(fontStyle = FontStyle.Italic)) {
emph_with = lines[ei + 1].strip()
if emph_with != 'withStyle(rpStyle ?: SpanStyle(fontStyle = FontStyle.Italic)) {':
    fail(MD, 'EMPH withStyle line unexpected: ' + emph_with, lines, ei)
lines[ei + 1] = eind + 'withStyle(SpanStyle(fontStyle = FontStyle.Italic, color = rpColor ?: Color.Unspecified)) {'
applied.append('emph')

# ===================== 3. STRONG 分支 =====================
stri = find_unique(
    lines,
    'val rpStyle = resolveRpSpanStyle(' + DQ + '**' + DQ + ', colorScheme, rpStyleRules) // ' + OLD_MARK,
    'STRONG rpStyle line',
    MD,
)
strind = indent_of(lines[stri])
lines[stri] = strind + 'val rpColor = resolveRpColor(' + DQ + '**' + DQ + ', colorScheme, rpStyleRules) // ' + MARK
strong_with = lines[stri + 1].strip()
if strong_with != 'withStyle(rpStyle ?: SpanStyle(fontWeight = FontWeight.Bold)) {':
    fail(MD, 'STRONG withStyle line unexpected: ' + strong_with, lines, stri)
lines[stri + 1] = strind + 'withStyle(SpanStyle(fontWeight = FontWeight.Bold, color = rpColor ?: Color.Unspecified)) {'
applied.append('strong')

# ===================== 4. STRIKETHROUGH 分支 =====================
sti = find_unique(
    lines,
    'val rpStyle = resolveRpSpanStyle(' + DQ + '~~' + DQ + ', colorScheme, rpStyleRules) // ' + OLD_MARK,
    'STRIKETHROUGH rpStyle line',
    MD,
)
stind = indent_of(lines[sti])
lines[sti] = stind + 'val rpColor = resolveRpColor(' + DQ + '~~' + DQ + ', colorScheme, rpStyleRules) // ' + MARK
strike_with = lines[sti + 1].strip()
if strike_with != 'withStyle(rpStyle ?: SpanStyle(textDecoration = TextDecoration.LineThrough)) {':
    fail(MD, 'STRIKETHROUGH withStyle line unexpected: ' + strike_with, lines, sti)
lines[sti + 1] = stind + 'withStyle(SpanStyle(textDecoration = TextDecoration.LineThrough, color = rpColor ?: Color.Unspecified)) {'
applied.append('strike')

# ===================== 5. CODE_SPAN 分支 =====================
# 锚点: val rpStyle = resolveRpSpanStyle("`", colorScheme, rpStyleRules) // rhRpStyleRules
ci = find_unique(
    lines,
    'val rpStyle = resolveRpSpanStyle(' + DQ + '`' + DQ + ', colorScheme, rpStyleRules) // ' + OLD_MARK,
    'CODE_SPAN rpStyle line',
    MD,
)
cind = indent_of(lines[ci])
lines[ci] = cind + 'val rpColor = resolveRpColor(' + DQ + '`' + DQ + ', colorScheme, rpStyleRules) // ' + MARK
# color 行: color = rpStyle?.color ?: colorScheme.primary, // rhRpStyleRules
color_hits = []
for i in range(ci, min(ci + 12, len(lines))):
    if lines[i].strip() == 'color = rpStyle?.color ?: colorScheme.primary, // ' + OLD_MARK:
        color_hits.append(i)
if len(color_hits) != 1:
    fail(MD, 'CODE_SPAN color anchor count=' + str(len(color_hits)), lines, ci)
chi = color_hits[0]
chind = indent_of(lines[chi])
lines[chi] = chind + 'color = rpColor ?: colorScheme.primary, // ' + MARK
applied.append('code_span')

# ===================== 自检 =====================
out = concat_lines(lines)
for need in [
    'internal fun resolveRpColor(',
    'resolveRpColor(' + DQ + '*' + DQ + ', colorScheme, rpStyleRules)',
    'resolveRpColor(' + DQ + '**' + DQ + ', colorScheme, rpStyleRules)',
    'resolveRpColor(' + DQ + '~~' + DQ + ', colorScheme, rpStyleRules)',
    'resolveRpColor(' + DQ + '`' + DQ + ', colorScheme, rpStyleRules)',
    'SpanStyle(fontStyle = FontStyle.Italic, color = rpColor ?: Color.Unspecified)',
    'SpanStyle(fontWeight = FontWeight.Bold, color = rpColor ?: Color.Unspecified)',
    'SpanStyle(textDecoration = TextDecoration.LineThrough, color = rpColor ?: Color.Unspecified)',
    'color = rpColor ?: colorScheme.primary,',
]:
    if need not in out:
        fail(MD, 'selfcheck missing: ' + need, lines, 0)
for banned in [
    'resolveRpSpanStyle',
    'rpStyle ?: SpanStyle',
    'rpStyle?.color',
]:
    if banned in out:
        fail(MD, 'selfcheck residue: ' + banned, lines, 0)
if MARK not in out:
    fail(MD, 'marker missing', lines, 0)
# 括号配平
if (text.count('(') - text.count(')')) != (out.count('(') - out.count(')')):
    fail(MD, 'paren balance changed', lines, 0)
if (text.count('{') - text.count('}')) != (out.count('{') - out.count('}')):
    fail(MD, 'brace balance changed', lines, 0)

md_path.write_text(out, encoding='utf-8')
print('batch144: Markdown OK (' + ', '.join(applied) + ')')
print('batch144: ALL OK')

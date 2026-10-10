#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch137: RP 优化 —— DisplaySetting 加 rpStyleRules 字段 + RpStyleRule 数据类

来源: Cocolalilal/LastChat 的 RP 优化(自定义文本样式)功能。
用户可定义规则: 让被特定模式包裹的文本以自定义颜色渲染(如 *text* 灰显动作, %text% 黄强调)。

本 patch 只做数据模型层:
1. PreferencesStore.kt 里 DisplaySetting 之前插入 RpStyleRule 数据类定义
2. DisplaySetting 末尾加 rpStyleRules 字段(默认空列表)

字段用 @Serializable + 默认值,旧数据反序列化时新字段自动用默认值,向后兼容。

五查:
1. import 清单: RpStyleRule 用全限定名 kotlin.uuid.Uuid.random() 不依赖 import;
   DisplaySetting 里 rpStyleRules 引用 RpStyleRule 是同文件内引用,不需 import
2. 同文件冲突: PreferencesStore.kt 被 batch91/92 碰过(displaySetting/ProviderSetting 区域),
   本脚本插入区在 DisplaySetting 定义处,与 batch91/92 的改动区不重叠
3. 作用域: RpStyleRule 是顶层 data class,在 DisplaySetting 之前定义,无前向引用问题
4. 括号配对: RpStyleRule 定义 1 开 1 闭;字段插入行无括号
5. 函数签名: 不改

Python 三查: 无引号字面量(DQ 变量) / 无 f-string/walrus/join / fail-loud
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
DQ = chr(34)
MARK = 'rhRpStyleRules'

PS = 'app/src/main/java/me/rerere/rikkahub/data/datastore/PreferencesStore.kt'


def fail(path, msg, lines=None, around=-1):
    body = 'batch137 ' + str(msg)
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


ps_path = ROOT / PS
text = ps_path.read_text(encoding='utf-8')
if MARK in text:
    print('batch137: PreferencesStore already applied')
else:
    lines = text.split(NL)

    # ---- 1. 在 DisplaySetting 之前插入 RpStyleRule 定义 ----
    # 锚点: data class DisplaySetting( 行
    ds_hits = []
    for i, ln in enumerate(lines):
        if ln.strip() == 'data class DisplaySetting(':
            ds_hits.append(i)
    if len(ds_hits) != 1:
        fail(PS, 'DisplaySetting anchor count=' + str(len(ds_hits)), lines, ds_hits[0] if ds_hits else 0)
    dsi = ds_hits[0]
    # 向上找到 @Serializable 行
    ann_idx = -1
    for k in range(dsi - 1, max(0, dsi - 5), -1):
        if lines[k].strip() == '@Serializable':
            ann_idx = k
            break
    if ann_idx < 0:
        fail(PS, '@Serializable above DisplaySetting not found', lines, dsi)

    rp_def = [
        '',
        '@Serializable',
        'data class RpStyleRule( // ' + MARK,
        '    val id: String = kotlin.uuid.Uuid.random().toString(),',
        '    val pattern: String = ' + DQ + '*' + DQ + ',',
        '    val colorHex: String = ' + DQ + '#808080' + DQ + ',',
        '    val enabled: Boolean = true,',
        ')',
        '',
    ]
    for j, b in enumerate(rp_def):
        lines.insert(ann_idx + j, b)

    # ---- 2. 在 DisplaySetting 末尾加 rpStyleRules 字段 ----
    # 锚点: val volumeKeyScrollRatio: Float = 1.0f, (最后一个字段)
    vol_hits = []
    for i, ln in enumerate(lines):
        if ln.strip() == 'val volumeKeyScrollRatio: Float = 1.0f,':
            vol_hits.append(i)
    if len(vol_hits) != 1:
        fail(PS, 'volumeKeyScrollRatio anchor count=' + str(len(vol_hits)), lines, vol_hits[0] if vol_hits else 0)
    vi = vol_hits[0]
    vind = lines[vi][:len(lines[vi]) - len(lines[vi].lstrip())]
    lines.insert(vi + 1, vind + 'val rpStyleRules: List<RpStyleRule> = emptyList(), // ' + MARK)

    out = concat_lines(lines)
    # 自检
    if 'data class RpStyleRule(' not in out:
        fail(PS, 'RpStyleRule definition missing', lines, 0)
    if 'val rpStyleRules: List<RpStyleRule> = emptyList(),' not in out:
        fail(PS, 'rpStyleRules field missing', lines, 0)
    if MARK not in out:
        fail(PS, 'marker missing', lines, 0)
    # 括号配平检验
    if (text.count('(') - text.count(')')) != (out.count('(') - out.count(')')):
        fail(PS, 'paren balance changed', lines, 0)
    if (text.count('{') - text.count('}')) != (out.count('{') - out.count('}')):
        fail(PS, 'brace balance changed', lines, 0)
    ps_path.write_text(out, encoding='utf-8')
    print('batch137: PreferencesStore OK')

print('batch137: ALL OK')

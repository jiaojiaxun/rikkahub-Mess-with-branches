#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch131: 删除「推荐提供商」与「二维码导入供应商」+ 连带依赖清理

需求: 删除设置-供应商页的推荐按钮/面板与二维码导入(扫码+相册)功能, 并连带删除
只为它们引入的 gradle 依赖, 以减小 APK 体积。

删除清单:
  SettingProviderPage.kt:
    - 函数 RecommendProviderButton / RecommendProviderItem / ImportProviderButton
    - 函数 handleQRResult / handleImageQRCode
    - topBar actions 里两个调用块
    - ProviderItem 里 AiHubMix 折扣徽标块
    - 与已删代码相关且确认不再出现的 import(逐行自动判定)
  RecommendedProviders.kt: 全仓扫描无引用后整文件删除
  app/build.gradle.kts: 全仓扫描无引用后删三行依赖(quickie/barcode/camera)

防误删守卫:
  - 依赖删除由脚本现场全仓扫描决定: 扫到任何残留引用 -> 保留并打印;
    构建绝不因依赖误删而挂.
  - import 清理只针对候选符号(显式类/函数名, 不含操作符扩展如 plus),
    且仅当该符号在"除所有 import 行外的正文"中不再出现才删.
  - 所有块删除用花括号配平定位; 删除前后全文件配平必须一致.

五查:
1. import 清单: 只删候选, 逐行判定, 防操作符约定误删
2. 同文件冲突: SettingProviderPage.kt 被 batch42 碰过(filteredProviders 搜索区),
   本脚本删除区在 topBar actions 与文件下部函数区, 与 batch42 不重叠
3. 作用域: 删除顶层 private 函数与 actions 内调用块, 不涉作用域
4. 括号配对: 配平删除 + 前后配平自检
5. 函数签名: 纯删除, 不改签名

Python 三查:
1. 引号一律 chr() 构造; 同一字面量只拼一次
2. 不注入 Kotlin 代码; NL 仅拼行
3. helper 先定义后用; 锚点找不到即 dump 现场行 + exit(1)
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
D = chr(34)
BS = chr(92)

SP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingProviderPage.kt'
RP = 'app/src/main/java/me/rerere/rikkahub/data/datastore/RecommendedProviders.kt'
BG = 'app/build.gradle.kts'

CAND = [
    'QRResult', 'ScanQRCode', 'RECOMMENDED_PROVIDERS', 'decodeProviderSetting',
    'ImageUtils', 'Camera01', 'Image02', 'FileImport', 'Sparkles',
    'rememberLauncherForActivityResult', 'ActivityResultContracts',
    'AutoAIIcon', 'ModalBottomSheet', 'rememberBottomSheetState', 'SheetValue', 'Uri',
]

DEP_JOBS = [
    ('quickie.bundled', 'io.github.g00fy2'),
    ('barcode.scanning', 'com.google.mlkit'),
    ('androidx.camera.core', 'androidx.camera'),
]


def concat_items(items, sep):
    text = ''
    first = True
    for item in items:
        if not first:
            text += sep
        text += str(item)
        first = False
    return text


def fail(path, msg, lines=None, around=-1):
    body = 'batch131 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = concat_items(
            ('L' + str(i + 1) + ':' + lines[i].strip()[:100] for i in range(lo, hi)),
            ' || ',
        )
        body = body + ' || ctx: ' + ctx
    print('::error file=' + path + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


def strip_strings(line):
    out = ''
    in_str = False
    prev_bs = False
    for ch in line:
        if in_str:
            if prev_bs:
                prev_bs = False
            elif ch == BS:
                prev_bs = True
            elif ch == D:
                in_str = False
            continue
        if ch == D:
            in_str = True
            continue
        out += ch
    return out


def balance(text):
    p = 0
    b = 0
    for ln in text.split(NL):
        code = strip_strings(ln)
        p += code.count('(') - code.count(')')
        b += code.count('{') - code.count('}')
    return p, b


def concat_lines(lines):
    text = ''
    first = True
    for line in lines:
        if not first:
            text += NL
        text += line
        first = False
    return text


def brace_end(lines, start, label, path):
    depth = 0
    started = False
    for j in range(start, len(lines)):
        for ch in strip_strings(lines[j]):
            if ch == '{':
                depth += 1
                started = True
            elif ch == '}':
                depth -= 1
        if started and depth <= 0:
            return j
    fail(path, label + ' brace end not found', lines, start)
    return -1


def remove_declaration(text, sig_prefix, label, path):
    lines = text.split(NL)
    idx = -1
    for i, ln in enumerate(lines):
        if ln.strip().startswith(sig_prefix):
            idx = i
            break
    if idx < 0:
        fail(path, label + ' not found', lines, 0)
    start = idx
    for k in (idx - 1, idx - 2):
        if k >= 0 and lines[k].strip().startswith('@'):
            start = k
        else:
            break
    end = brace_end(lines, idx, label, path)
    return concat_lines(lines[:start] + lines[end + 1:])


def remove_brace_from(text, pred, label, path):
    lines = text.split(NL)
    hits = [i for i, ln in enumerate(lines) if pred(ln.strip())]
    if len(hits) != 1:
        fail(path, label + ' count=' + str(len(hits)), lines, hits[0] if hits else 0)
    idx = hits[0]
    end = brace_end(lines, idx, label, path)
    return concat_lines(lines[:idx] + lines[end + 1:])


def prune_imports(text, cand):
    lines = text.split(NL)
    removed = []
    for i in reversed(range(len(lines))):
        ln = lines[i].strip()
        if not ln.startswith('import '):
            continue
        seg = ln[7:].strip()
        if seg.endswith('.*'):
            continue
        sym = seg.split(' as ')[0].split('.')[-1]
        if sym not in cand:
            continue
        body_text = concat_lines(
            x for j, x in enumerate(lines) if j != i and not x.strip().startswith('import ')
        )
        if sym in body_text:
            continue
        del lines[i]
        removed.append(sym)
    return concat_lines(lines), removed


def scan_repo(symbol):
    hits = []
    base = ROOT / 'app' / 'src'
    for p in base.rglob('*.kt'):
        try:
            t = p.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            continue
        if symbol in t:
            hits.append(str(p.relative_to(ROOT)))
    mf = ROOT / 'app' / 'src' / 'main' / 'AndroidManifest.xml'
    try:
        if mf.exists() and symbol in mf.read_text(encoding='utf-8', errors='ignore'):
            hits.append(str(mf.relative_to(ROOT)))
    except Exception:
        pass
    return hits


# ============================================================
# 1. SettingProviderPage.kt
# ============================================================
sp = (ROOT / SP).read_text(encoding='utf-8')
if 'RecommendProviderButton' not in sp and 'ImportProviderButton' not in sp:
    print('batch131: SettingProviderPage already applied')
else:
    bal0 = balance(sp)
    text = sp
    text = remove_declaration(text, 'private fun RecommendProviderButton(', 'fn RecommendProviderButton', SP)
    text = remove_declaration(text, 'private fun RecommendProviderItem(', 'fn RecommendProviderItem', SP)
    text = remove_declaration(text, 'private fun ImportProviderButton(', 'fn ImportProviderButton', SP)
    text = remove_declaration(text, 'private fun handleQRResult(', 'fn handleQRResult', SP)
    text = remove_declaration(text, 'private fun handleImageQRCode(', 'fn handleImageQRCode', SP)
    text = remove_brace_from(
        text,
        lambda s: s == 'RecommendProviderButton { provider ->',
        'call RecommendProviderButton',
        SP,
    )
    text = remove_brace_from(
        text,
        lambda s: s == 'ImportProviderButton {',
        'call ImportProviderButton',
        SP,
    )
    text = remove_brace_from(
        text,
        lambda s: s == 'if (provider.name == ' + D + 'AiHubMix' + D + ') {',
        'AiHubMix badge',
        SP,
    )
    text, removed_imps = prune_imports(text, CAND)

    lines = text.split(NL)
    for banned in [
        'RecommendProviderButton', 'RecommendProviderItem', 'ImportProviderButton',
        'handleQRResult', 'handleImageQRCode', 'RECOMMENDED_PROVIDERS',
        'ScanQRCode', 'QRResult',
    ]:
        if banned in text:
            fail(SP, 'residue after delete: ' + banned, lines, 0)
    for must in ['AddButton', 'ProviderItem', 'fun SettingProviderPage(', 'ProviderConfigure']:
        if must not in text:
            fail(SP, 'missing after delete: ' + must, lines, 0)
    if balance(text) != bal0:
        fail(SP, 'balance changed after delete', lines, 0)
    (ROOT / SP).write_text(text, encoding='utf-8')
    print('batch131: SettingProviderPage OK (imports removed: ' + concat_items(removed_imps, ',') + ')')


# ============================================================
# 2. RecommendedProviders.kt —— 全仓扫描无引用才删文件
# ============================================================
rp_path = ROOT / RP
if not rp_path.exists():
    print('batch131: RecommendedProviders.kt already removed')
else:
    refs = [h for h in scan_repo('RECOMMENDED_PROVIDERS') if h != str(RP)]
    if refs:
        print('batch131: WARN RecommendedProviders.kt kept, referenced by: ' + concat_items(refs[:5], ','))
    else:
        rp_path.unlink()
        print('batch131: RecommendedProviders.kt removed (no references)')


# ============================================================
# 3. app/build.gradle.kts —— 全仓扫描无引用才删依赖行
# ============================================================
bg = (ROOT / BG).read_text(encoding='utf-8')
bg_lines = bg.split(NL)
deleted = []
kept = []
bal_bg0 = balance(bg)
for alias, sym in DEP_JOBS:
    ln_match = 'implementation(libs.' + alias + ')'
    idx = -1
    for i, ln in enumerate(bg_lines):
        if ln.strip() == ln_match:
            idx = i
            break
    if idx < 0:
        kept.append(alias + ':line-absent')
        continue
    hits = scan_repo(sym)
    if hits:
        kept.append(alias + ':used-by=' + concat_items(hits[:3], ','))
        continue
    del bg_lines[idx]
    deleted.append(alias)
if len(deleted) == 3:
    for i, ln in enumerate(bg_lines):
        if ln.strip() == '// quickie (qrcode scanner)':
            del bg_lines[i]
            break
out_bg = concat_lines(bg_lines)
if balance(out_bg) != bal_bg0:
    fail(BG, 'gradle balance changed', bg_lines, 0)
if out_bg != bg:
    (ROOT / BG).write_text(out_bg, encoding='utf-8')
print('batch131: gradle deleted=' + str(deleted) + ' kept=' + str(kept))

print('batch131: ALL OK')
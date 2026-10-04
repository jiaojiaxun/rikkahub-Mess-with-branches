#!/usr/bin/env python3
'''batch79: 模型名规范化去中文——识别模型对应上下文时自动去除 CJK 字符
现状：ModelNameNormalizer.key() 的 nonAlphaNumeric=[^\p{L}\p{N}]+ 保留汉字(\p{L}含CJK)，
"深度求索deepseek-v4" 匹配不到 deepseekv4 规则。
改法：先 strip CJK/全角段，再走原有 nonAlphaNumeric 压缩。
锚点：两行均为实读确认的唯一行。零新 import（Regex 已用）。
'''
from pathlib import Path
ROOT = Path.cwd()
NL = chr(10)
M = 'rhStripCjk'

def fail(p, m):
    print('::error file=' + p + '::batch79 ' + str(m)[:1200])
    raise SystemExit(1)

F = 'app/src/main/java/me/rerere/rikkahub/data/model/ModelNameNormalizer.kt'
t = (ROOT / F).read_text(encoding='utf-8')
if M in t:
    print('batch79: already applied')
else:
    lines = t.split(NL)
    old_re = 'private val nonAlphaNumeric = Regex("[^\\\\p{L}\\\\p{N}]+")'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == old_re]
    if len(hits) != 1:
        for i, ln in enumerate(lines):
            if 'nonAlphaNumeric' in ln:
                print('  >> line ' + str(i) + ': ' + ln.strip()[:160])
        fail(F, 'nonAlphaNumeric anchor count=' + str(len(hits)))
    d = lines[hits[0]][:len(lines[hits[0]]) - len(lines[hits[0]].lstrip())]
    lines.insert(hits[0] + 1, d + '// ' + M + ': 模型名中的 CJK/全角字符不参与上下文族匹配')
    lines.insert(hits[0] + 2, d + 'private val cjkChars = Regex("[\\\\u3000-\\\\u303f\\\\u3400-\\\\u4dbf\\\\u4e00-\\\\u9fff\\\\uf900-\\\\ufaff\\\\uff00-\\\\uffef]+")')
    old_compact = 'val compact = segment.replace(nonAlphaNumeric, "")'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == old_compact]
    if len(hits) != 1:
        fail(F, 'compact anchor count=' + str(len(hits)))
    d = lines[hits[0]][:len(lines[hits[0]]) - len(lines[hits[0]].lstrip())]
    lines[hits[0]] = d + 'val compact = segment.replace(cjkChars, "").replace(nonAlphaNumeric, "")'
    t = NL.join(lines)
    for need in [M, 'cjkChars', 'segment.replace(cjkChars, "")']:
        if need not in t:
            fail(F, 'selfcheck missing: ' + need)
    (ROOT / F).write_text(t, encoding='utf-8')
    print('batch79: OK')

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch134: 补 androidx.exifinterface 依赖

编译错误: ImageUtils.kt 引用 ExifInterface/getAttributeInt 但依赖缺失
(Unresolved reference 'ExifInterface')。上游移植加了引用但依赖没跟上。

修法:
1. gradle/libs.versions.toml:
   - [versions] 加 exifinterface = "1.8.1"
   - [libraries] 加 androidx-exifinterface = { group="androidx.exifinterface", name="exifinterface", version.ref="exifinterface" }
2. app/build.gradle.kts dependencies 加 implementation(libs.androidx.exifinterface)

幂等: 三处各自检查已存在则跳过。
锚点: metadataExtractor/metadata-extractor 行(图片元数据相关,同域)。
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
TOML = 'gradle/libs.versions.toml'
BG = 'app/build.gradle.kts'


def fail(tag, msg, lines=None, around=-1):
    body = 'batch134 ' + str(tag) + ': ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:100] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error::' + body[:1400])
    sys.stdout.flush()
    sys.exit(1)


def read_lines(path):
    return (ROOT / path).read_text(encoding='utf-8').split(NL)


def write_lines(path, lines):
    (ROOT / path).write_text(NL.join(lines), encoding='utf-8')


def insert_after(path, pred, new_lines, label):
    lines = read_lines(path)
    hits = [i for i, ln in enumerate(lines) if pred(ln)]
    if len(hits) != 1:
        fail(label, 'anchor count=' + str(len(hits)) + ' path=' + path, lines, hits[0] if hits else 0)
    i = hits[0]
    indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    for offset, seg in enumerate(new_lines):
        lines.insert(i + 1 + offset, indent + seg if seg else seg)
    write_lines(path, lines)


# 1. libs.versions.toml [versions] 加 exifinterface
lines = read_lines(TOML)
if any('exifinterface' in ln for ln in lines):
    print('batch134: toml exifinterface already present')
else:
    ver_line = 'exifinterface = "1.8.1"'
    insert_after(
        TOML,
        lambda ln: ln.strip().startswith('metadataExtractor ='),
        [ver_line],
        'toml-version',
    )
    print('batch134: toml version added')

# 2. libs.versions.toml [libraries] 加 androidx-exifinterface
lines = read_lines(TOML)
if any('androidx.exifinterface' in ln for ln in lines):
    print('batch134: toml library already present')
else:
    lib_line = 'androidx-exifinterface = { group = "androidx.exifinterface", name = "exifinterface", version.ref = "exifinterface" }'
    insert_after(
        TOML,
        lambda ln: ln.strip().startswith('metadata-extractor ='),
        [lib_line],
        'toml-library',
    )
    print('batch134: toml library added')

# 3. app/build.gradle.kts dependencies 加 implementation
lines = read_lines(BG)
if any('androidx.exifinterface' in ln or 'exifinterface' in ln for ln in lines):
    print('batch134: build.gradle exifinterface already present')
else:
    insert_after(
        BG,
        lambda ln: 'implementation(libs.metadata.extractor)' in ln,
        ['implementation(libs.androidx.exifinterface)'],
        'gradle-dep',
    )
    print('batch134: build.gradle dependency added')

print('batch134: ALL OK')
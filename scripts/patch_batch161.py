#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch161: 豆沙包续跑改进——ResponseStreamErrorException 也重试

用户反馈: "模型生成到一半，突然停下来，你都不知道续跑"

根因: GenerationHandler.kt 的 shouldRetryGenerationStreamFailure 里:
    if (failure is ResponseStreamErrorException || isContextLimitFailure(failure)) {
        return false  // ← 流被意外关闭时不重试！
    }
ResponseStreamErrorException 被排除在重试之外——流被意外关闭时不重试。

修法: 把 ResponseStreamErrorException 从排除列表移除（让它可以重试）。

改动(GenerationHandler.kt 单文件): 行内替换 shouldRetryGenerationStreamFailure 的条件。

五查:
1. import 清单: 零新增
2. 同文件冲突: GenerationHandler.kt 被 batch118 碰过——锚点在 shouldRetryGenerationStreamFailure
   函数体内,与 batch118 的改动区不重叠
3. 作用域: 在函数体内,局部变量可见
4. 括号配对: 行内替换,不影响配平
5. 函数签名: 不改

Python 三查: 无引号字面量; 无 f-string; 失败显式 exit(1)
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhResumeStreamErr'
GH = 'app/src/main/java/me/rerere/rikkahub/data/ai/GenerationHandler.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch161 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + GH + '::' + body[:1400])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


t = (ROOT / GH).read_text(encoding='utf-8')
if MARK in t:
    print('batch161: already applied')
    sys.exit(0)

bal0 = balance(t)
lines = t.split(NL)

# 找 shouldRetryGenerationStreamFailure 里的 ResponseStreamErrorException 排除
OLD = 'if (failure is ResponseStreamErrorException || isContextLimitFailure(failure)) {'
hits = [i for i, ln in enumerate(lines) if ln.strip() == OLD]
if len(hits) != 1:
    fail('ResponseStreamErrorException anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
hi = hits[0]
d = ind(lines[hi])

# 替换: 去掉 ResponseStreamErrorException 排除
NEW = 'if (isContextLimitFailure(failure)) { // ' + MARK + ': stream error 也可重试'
lines[hi] = d + NEW

out = NL.join(lines)
if MARK not in out:
    fail('marker missing')
if 'failure is ResponseStreamErrorException ||' in out:
    fail('old condition still present')
if balance(out) != bal0:
    fail('balance changed')

(ROOT / GH).write_text(out, encoding='utf-8')
print('::notice::batch161 OK - stream error now retryable')

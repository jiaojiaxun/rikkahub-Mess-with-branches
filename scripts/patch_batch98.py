#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch98: 加 MiMo 上下文规则 —— 小米 MiMo 2.5+ 实际上下文 1M

【问题】ModelContextLengthResolver 的 CONTEXT_RULES 没有 mimo 规则,
MiMo 模型 fallback 到 OpenRouter API 查询,返回 200K(过时数据)。
用户确认 MiMo 2.5 实际上下文 = 1M(1_048_576)。

【修法】在 Mistral 段(magistral 行)之前加一条 mimo 通用规则:
  ContextRule(listOf("mimo"), 1_048_576)
归一化后 "mimov25" 包含 "mimo" → 命中 → 1M。

五查:
1. import:零新增
2. 同文件冲突:ModelContextLengthResolver.kt 被 batch56/79/94 改过——
   本批锚点 = magistral 行(原始态,未被碰过),在 Mistral 段,与 kimi 段不重叠
3. 作用域:CONTEXT_RULES 位于 companion object 内
4. 括号配对:单行插入,自平衡
5. 函数签名:不改
Python 三查:Q=chr(34) / NL 手写 / 无 f-string / 失败 exit(1)
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhMimoCtx'
RS = 'app/src/main/java/me/rerere/rikkahub/data/model/ModelContextLengthResolver.kt'


def fail(msg, lines=None, around=-1):
    body = 'batch98 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:90] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + RS + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


t = (ROOT / RS).read_text(encoding='utf-8')
if MARK in t:
    print('batch98: already applied')
else:
    lines = t.split(NL)

    # 锚点 = magistral 行(Mistral 段第一行,原始态,未被 batch56/79/94 碰过)
    ANCHOR = 'ContextRule(listOf(' + Q + 'magistral' + Q + '), 1_048_576),'
    hits = [i for i, ln in enumerate(lines) if ln.strip() == ANCHOR]
    if len(hits) != 1:
        fail('magistral anchor count=' + str(len(hits)), lines, hits[0] if hits else 0)
    i = hits[0]
    d = ind(lines[i])

    new_line = d + 'ContextRule(listOf(' + Q + 'mimo' + Q + '), 1_048_576), // ' + MARK + ' (batch98): 小米 MiMo 2.5+ 实际 1M(用户确认)'
    lines.insert(i, new_line)
    out = NL.join(lines)

    for need in [MARK, 'ContextRule(listOf(' + Q + 'mimo' + Q + '), 1_048_576)']:
        if need not in out:
            fail('selfcheck missing: ' + need)
    # 顺序:mimo 必须在 magistral 之前
    if out.index('listOf(' + Q + 'mimo' + Q + ')') > out.index('listOf(' + Q + 'magistral' + Q + ')'):
        fail('mimo rule must precede magistral')

    (ROOT / RS).write_text(out, encoding='utf-8')
    print('batch98: OK (MiMo -> 1M context rule added)')

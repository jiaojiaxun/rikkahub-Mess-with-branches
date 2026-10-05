#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch94 v2: 补 kimi-k2 家族规则(修复 ModelContextLengthResolverTest > commonFamiliesResolve)

v1 (#b94 首次)死因:SyntaxError: unterminated string literal at line 98 ——
      拼接 'listOf(' + Q + 'kimik2' + Q + '), 262_144) 时漏了闭引号,
      应作 '... + Q + '), 262_144')'。教训:多处重复拼接同一字符串必出错。
v2 策略:把规则字符串抽成【单一常量 KIMI2_RULE】,所有检查/查找/计数都引用它,
      全脚本只做一次引号拼接。

现象:CI 单元测试 :app:testDebugUnitTest 长期失败(annotation,非 job 结论)——
      ModelContextLengthResolverTest.kt commonFamiliesResolve FAILED。

根因(实读):batch56 为实现版本区分,把通用 kimi 规则从 262144 降到 131072,
      并在其前插入 kimik3/kimik26/kimik25。OpenRouter 的 moonshotai/kimi-k2
      归一化后 key = "kimik2",既不匹配 kimik26 也不匹配 kimik25,落到通用
      kimi = 131072,与测试断言 262144 冲突。

事实核实(search_web,2026-10-05):原始 K2 = 128K;Kimi-K2-Instruct-0905 起 = 256K;
      K2.5/K2.6/K2.7 = 256K;K3 = 1M。OpenRouter 的 moonshotai/kimi-k2 即 0905 = 256K。
      => 测试断言正确,batch56 漏了基础 k2 这一条。

修法:在通用 kimi 规则之前补一条更具体的 kimik2 -> 262144。
      顺序 = kimik3 / kimik26 / kimik25 / kimik2 / kimi,先具体后通用。

五查:
1. import:零新增
2. 同文件冲突:ModelContextLengthResolver.kt 被 batch56 改过(batch92/93 均未碰它)。
   锚点 = 通用 kimi 兜底行(batch56 的产物),用 startswith 前缀匹配,不依赖具体数值
3. 作用域:CONTEXT_RULES 位于 companion object 内,插入行同级
4. 括号配对:插入单行,自闭合;断言插入前后括号差值不变
5. 函数签名:不改任何签名

Python 三查:引号走 Q=chr(34) 构造且【单一常量只拼一次】/ NL 手写 concat /
      无 f-string/walrus / 失败显式 exit(1)
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhKimiK2Fix'
RS = 'app/src/main/java/me/rerere/rikkahub/data/model/ModelContextLengthResolver.kt'

# ---- 唯一一次引号拼接。此后全脚本只引用 KIMI2_RULE / KIMI2_NEED ----
KIMI2_RULE = 'ContextRule(listOf(' + Q + 'kimik2' + Q + '), 262_144)'
KIMI2_NEED = KIMI2_RULE + ', // ' + MARK
# 通用 kimi 兜底行前缀(参数恰为 "kimi",不会命中 kimik3/kimik26/kimik25/kimik2)
GENERIC_KIMI_PREFIX = 'ContextRule(listOf(' + Q + 'kimi' + Q + '), '


def fail(msg, lines=None, around=-1):
    body = 'batch94v2 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = ' || '.join('L' + str(i + 1) + ':' + lines[i].strip()[:80] for i in range(lo, hi))
        body = body + ' || ctx: ' + ctx
    print('::error file=' + RS + '::' + body[:1500])
    sys.stdout.flush()
    sys.exit(1)


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


t = (ROOT / RS).read_text(encoding='utf-8')
if MARK in t:
    print('batch94v2: already applied')
    sys.exit(0)

bal0 = balance(t)
lines = t.split(NL)

hits = [i for i, ln in enumerate(lines) if ln.strip().startswith(GENERIC_KIMI_PREFIX)]
if len(hits) != 1:
    fail('kimi fallback rule count=' + str(len(hits)), lines, hits[0] if hits else 0)

i = hits[0]
d = lines[i][:len(lines[i]) - len(lines[i].lstrip())]

# 幂等兜底:紧邻上文若已是 kimik2 规则则跳过
if any(KIMI2_RULE in lines[j] for j in range(max(0, i - 2), i)):
    print('batch94v2: kimik2 rule already present above, skip')
    sys.exit(0)

lines.insert(i, d + KIMI2_NEED)

out = NL.join(lines)

if KIMI2_NEED not in out:
    fail('selfcheck missing: ' + KIMI2_NEED)

# 顺序断言:kimik2 必须出现在通用 kimi 之前(先具体后通用)
idx_k2 = out.find(KIMI2_RULE)
idx_kimi = out.find(GENERIC_KIMI_PREFIX)
if idx_k2 < 0 or idx_kimi < 0 or idx_k2 > idx_kimi:
    fail('order violated: kimik2 must precede generic kimi')

# 无重复:kimik2 规则仅一条
if out.count(KIMI2_RULE) != 1:
    fail('kimik2 rule count != 1')

if balance(out) != bal0:
    fail('bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(out)))

(ROOT / RS).write_text(out, encoding='utf-8')
print('batch94v2: OK (kimik2 -> 262144 inserted before generic kimi)')

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch233: 真实修复 232 模型链 Elvis 被注释 bug (ChatService.kt:1183)

根因(读 run442 annotation + snapshot 实读确认):
  232 v2 的正则替换 findModelById(...) → getChatModelOf(X) // rhA3Wiring
  只匹配到调用的闭括号 `)`, 残留文本继续拼接。当原文的 `?: ...` 与 `)` 同行时
  (rerunToolInternal 形态), 残留 Elvis 被行尾 `// rhA3Wiring` 注释吃掉:
    val model = settings.getChatModelOf(conversation) // rhA3Wiring ?: return RerunToolResult.Failure(...)
  → model 泄漏为 Model?, 传给 buildToolsForRerun(model: Model) → 编译错误 1183。
  handleMessageComplete 形态的 Elvis 在下一行(实读确认安全, 未中招)。

修复: 逐行扫描全文件 `// rhA3Wiring ?:` 同行中招模式, 把 Elvis 恢复到下一行
  (缩进 = 行前导 + 4), 形如:
    val model = settings.getChatModelOf(conversation) // rhA3Wiring
        ?: return RerunToolResult.Failure("no chat model selected")

幂等: 修复后该模式消失, 重跑自然 skip; 若并行会话已推 232 v3 修过同样无害(skip)。
不依赖 232 的任何锚点, 只认副作用特征串 `// rhA3Wiring ?:`。
范围: 只修编译阻断项(Elvis); 不动 232 的语义迁移(如未换完的助手链), 那是 232 的范围。

五查:
1. import 清单: 无新 import (纯文本修复)
2. 同文件冲突: 只动 ChatService.kt; 与 232 无锚点竞争(特征串扫描); 与我的 230/231 区域不相交
   (230 动 memories 装配/memoryText; 此修复动模型链, 都基于 232 应用后的形态)
3. 作用域: 纯文本重排, 不改语义
4. 括号配对: 修复前后全文 balance 对比
5. 函数签名: 无签名变更

Python 三查: 引号全部 SQ 构造; 无 f-string/join/walrus; helper 先定义后用; fail-loud + dump
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'
MISS = '// rhA3Wiring ?:'
DIAG = 'ci_diag_batch233.txt'


def diag_write(lines):
    try:
        p = ROOT / DIAG
        old = ''
        if p.exists():
            old = p.read_text(encoding='utf-8')
        body = old
        for ln in lines:
            body += str(ln) + NL
        p.write_text(body, encoding='utf-8')
    except Exception as e:
        print('::error::batch233 diag write failed: ' + str(e)[:200])


def main():
    p = ROOT / CS
    if not p.exists():
        print('::error::batch233 ChatService.kt missing')
        sys.exit(1)
    t = p.read_text(encoding='utf-8')

    # 诊断: dump 所有 rhA3Wiring 行(修复前), 复盘留证
    wiring_lines = []
    for i, ln in enumerate(t.split(NL)):
        if 'rhA3Wiring' in ln:
            wiring_lines.append('L' + str(i + 1) + ': ' + ln.strip()[:150])
    diag_write(['=== batch233 BEFORE rhA3Wiring lines (' + str(len(wiring_lines)) + ') ===']
               + wiring_lines)

    if MISS not in t:
        print('::notice::batch233 OK already - no commented-out elvis found')
        sys.exit(0)

    bal0 = (t.count('(') - t.count(')')) + (t.count('{') - t.count('}'))
    lines = t.split(NL)
    out = ''
    fixed = 0
    for i, ln in enumerate(lines):
        if i > 0:
            out += NL
        if MISS in ln:
            idx = ln.find(MISS)
            before = ln[:idx].rstrip()
            after = ln[idx + len(MISS):]
            lead = len(ln) - len(ln.lstrip())
            out += before + ' // rhA3Wiring'
            out += NL + (' ' * (lead + 4)) + '?:' + after
            fixed += 1
        else:
            out += ln

    bal1 = (out.count('(') - out.count(')')) + (out.count('{') - out.count('}'))
    if bal1 != bal0:
        print('::error::batch233 balance changed ' + str(bal0) + '->' + str(bal1))
        sys.exit(1)
    if fixed < 1:
        print('::error::batch233 fixed=0 despite MISS present')
        sys.exit(1)

    p.write_text(out, encoding='utf-8')
    t2 = p.read_text(encoding='utf-8')
    if MISS in t2:
        print('::error::batch233 still has commented elvis after write')
        sys.exit(1)
    diag_write(['=== batch233 AFTER fixed=' + str(fixed) + ' (elvis restored) ==='])
    print('::notice::batch233 OK - restored ' + str(fixed)
          + ' commented-out elvis (ChatService 1183 fix)')


main()
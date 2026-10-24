#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch257c: 回滚 batch257 的错误插入（止血，让构建恢复绿）

【run#472 编译错误的真因 —— 读 annotations 确认，不是猜】
    ChatService.kt:1652:13  Unresolved reference 'milliseconds'
    ChatService.kt:1652:13  Syntax error: Expecting ')'
    ChatService.kt:1652:13  Syntax error: Expecting an argument
    ChatService.kt:1652:13  Mixing named and positional arguments is not allowed ...
    ChatService.kt:1653:13  Syntax error: Expecting an element
    ChatService.kt:1653:14  Syntax error: Unexpected tokens
    ChatService.kt:1653:30  An explicit type is required on a value parameter
    ChatService.kt:1668:17  Suspension functions can only be called within coroutine body
    ChatService.kt:1689:15  Unresolved reference 'collect'
    ChatService.kt:1362:32  Cannot infer type for type parameter 'R'

=> `.sample(80.milliseconds)` 被插到了**第 1652 行**（某函数调用参数列表中间），
   不是我以为的 `generateText(...).onCompletion { }.collect { }` 那里。
   原因：batch257 的锚点 `).onCompletion { completionCause ->` 在 ChatService 里出现多次，
   脚本取"第一个匹配"，命中了另一个流处理链。
   语法被截断后产生连锁错误（1668/1689/1362 都是连带）。
   同时 `import kotlinx.coroutines.flow.sample` 确实写进去了（snapshot import 区可见），
   但代码里的 `.sample(...)` 在错误位置 => 编译失败。

【本批只做止血：删干净，不重做 T-P2】
删除三样东西（全部用内容匹配，不依赖行号）：
 1. 含 `rhUiThrottle257` 的注释行
 2. 含 `.sample(80.milliseconds)` 的代码行
 3. `import kotlinx.coroutines.flow.sample // rhUiThrottle257` 那一行
删完只剩其他 8 项修复（引用/shell/模型切换/记忆/合并/工具展开/MCP头像/初始化耗时），
构建应恢复绿。

【为什么本批不重新实现 T-P2】
它是性能优化，不是故障修复；而它已经连续两轮把构建打红。
用户真正需要的是能装上实测的那 8 项修复。T-P2 的正确落点需要在
`}.collect { chunk ->`（唯一形态）上做，并先确认该行全文件唯一 —— 留到下一批单独做、单独验证。

五查:
 1. import 清单: 本批只删不增
 2. 同文件冲突: 只删 batch257 自己写入的三行，不触碰其他批次
 3. 作用域: 删除整行，不影响其余代码
 4. 括号配对: `.sample(80.milliseconds)` 自身配平（1 对），删除后 balance 不变（断言）
 5. 函数签名: 零改动
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败记录并继续
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch257c.txt'

CS = 'app/src/main/java/me/rerere/rikkahub/service/ChatService.kt'

report = []


def note(msg):
    report.append(str(msg)[:900])


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def lines_to_text(lines):
    out = ''
    for idx, line in enumerate(lines):
        if idx > 0:
            out += NL
        out += line
    return out


def rollback():
    p = ROOT / CS
    if not p.exists():
        note('MISSING ChatService.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhUiThrottle257' not in t and '80.milliseconds' not in t:
        note('nothing to roll back (already clean)')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    removed = []
    kept = []
    for ln in lines:
        s = ln.strip()
        drop = False
        if 'rhUiThrottle257' in s:
            drop = True
        elif '.sample(80.milliseconds)' in s:
            drop = True
        elif s == 'import kotlinx.coroutines.flow.sample // rhUiThrottle257':
            drop = True
        elif s == 'import kotlinx.coroutines.flow.sample':
            drop = True
        if drop:
            removed.append(s[:120])
        else:
            kept.append(ln)

    if not removed:
        note('no matching line found, abort')
        return

    t2 = lines_to_text(kept)
    if balance(t2) != bal0:
        note('balance changed ' + str(bal0) + ' -> ' + str(balance(t2)) + ' (should be equal: sample() self-balanced)')
        return
    if '80.milliseconds' in t2:
        note('selfcheck failed: 80.milliseconds still present')
        return
    if 'rhUiThrottle257' in t2:
        note('selfcheck failed: marker still present')
        return
    p.write_text(t2, encoding='utf-8')
    note('chatService OK: removed ' + str(len(removed)) + ' line(s)')
    for r in removed:
        note('removed: ' + r)


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch257c diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch257c diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    try:
        rollback()
        note('1 rollback DONE')
    except Exception as e:
        note('1 rollback EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::batch257c part: rollback')
    sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch257c ' + str(line)[:800])
    print('::error::batch257c END lines=' + str(len(report)))


main()
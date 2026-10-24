#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch257b: 修 batch257 的编译红（80.milliseconds 的 import 缺失）

【batch257 的失败复盘 —— run#472 failure】
batch257 把 `.sample(80.milliseconds)` 插进去了，但 `import kotlin.time.Duration.Companion.milliseconds`
的锚点 `import kotlin.time.Instant` 在 ChatService.kt 里不存在，脚本"warning 后继续写盘"——
于是 ChatService 里出现了 `.sample(80.milliseconds)` 而对应 import 缺失 => 编译红：
unresolved reference: milliseconds。
这是脚本的**设计缺陷**：缺 import 时应该 abort（不写盘），而不是写盘后再等编译失败。
教训已记：import 锚点未命中时，必须 fail 并中止该文件写入。

【修正方法】
把 `80.milliseconds` 换成不需要任何 import 的全限定表达式:
    kotlin.time.Duration.parse("PT0.08S")     // 0.08 秒 = 80ms, 返回 Duration
sample 接受 Duration => 类型正确，零 import 需求。

【为什么不直接补 import】
该 import 当时没找到插入锚点（kotlin.time.Instant 不存在于本文件），硬插可能撞行序或吃掉下行；
用全限定表达式绕开整个 import 问题，更稳。

【本批做的事（一处替换，零新增 import）】
1. 找到 snapshot 里 batch257 写入的 `.sample(80.milliseconds)` 行
2. 替换为 `.sample(kotlin.time.Duration.parse("PT0.08S"))`
3. 断言：替换后 `80.milliseconds` 在本文件不存在
4. 同时清理（若存在）多余的 `import kotlin.time.Duration.Companion.milliseconds`
   —— batch257 其实没插成（锚点没命中），这里只是防御性清理

五查:
 1. import 清单: 零新增（用全限定表达式），且防御性删除可能存在的多余 import
 2. 同文件冲突: 只动 batch257 刚写入的那一行，锚点唯一
 3. 作用域: 无（同一行的表达式替换）
 4. 括号配对: `80.milliseconds` -> `kotlin.time.Duration.parse("PT0.08S")` 括号 1 对 1 => balance 不变（断言）
 5. 函数签名: 零改动
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败记录并继续
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch257b.txt'

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


def ind_of(line):
    s = line.lstrip()
    return line[:len(line) - len(s)]


def patch():
    p = ROOT / CS
    if not p.exists():
        note('MISSING ChatService.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'PT0.08S' in t:
        note('chatService already fixed')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    hits = [i for i, ln in enumerate(lines) if ln.strip() == '.sample(80.milliseconds)']
    if len(hits) != 1:
        note('ANCHOR-MISS .sample(80.milliseconds) count=' + str(len(hits)))
        return
    i = hits[0]
    lines[i] = ind_of(lines[i]) + '.sample(kotlin.time.Duration.parse("PT0.08S")) // rhUiThrottle257b: 全限定，绕开 import'

    # 防御性删除可能误插的 milliseconds import（batch257 其实没插成，这里只是兜底）
    bad = [i2 for i2, ln in enumerate(lines)
           if ln.strip() == 'import kotlin.time.Duration.Companion.milliseconds']
    if bad:
        note('found stray milliseconds import count=' + str(len(bad)) + ' -> removing')
        for idx in sorted(bad, reverse=True):
            lines.pop(idx)

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        return
    if '80.milliseconds' in t2:
        note('selfcheck failed: 80.milliseconds still present')
        return
    if 'kotlin.time.Duration.parse("PT0.08S")' not in t2:
        note('selfcheck failed: parse expression missing')
        return
    if 'import kotlinx.coroutines.flow.sample' not in t2:
        note('selfcheck failed: flow.sample import missing (batch257 was supposed to add it)')
        return
    p.write_text(t2, encoding='utf-8')
    note('chatService OK: .sample(kotlin.time.Duration.parse("PT0.08S"))')


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch257b diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch257b diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    try:
        patch()
        note('1 throttle import fix DONE')
    except Exception as e:
        note('1 throttle import fix EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::batch257b part: throttle import fix')
    sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch257b ' + str(line)[:800])
    print('::error::batch257b END lines=' + str(len(report)))


main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch258: 流式状态推送节流（T-P2）—— 在唯一锚点上重做，失败即中止不写盘

【为什么重做（batch257 的三次失败都记在这）】
1. run#472 红：锚点 `).onCompletion { completionCause ->` 在 ChatService.kt 里**不止一处**，
   脚本取第一个匹配 → `.sample(80.milliseconds)` 被插到第 1652 行的**参数列表中间**，
   语法被截断 ⇒ 1652/1653/1668/1689/1362 连锁编译错。
2. run#473 红（batch257b）：想替换 `.sample(80.milliseconds)` 但 `count=0`，未修到。
3. run#474（batch257c 回滚）：报 `nothing to roll back (already clean)` ——
   说明"写入"和"回滚"两个脚本在同一批 runner 上的实际先后与预期不一致。
=> batch257 / batch257b 已改为 no-op（不再写任何源码），彻底消除变量。

【本批的设计原则（三条硬约束）】
A. 锚点必须**全局唯一**：`find_idx` 若命中 0 次或 >1 次，直接 raise 并**不写盘**。
   失败只留 ::error 报告，构建不受影响（因为 257 已 no-op）。
B. import 缺失时**中止写入**，不允许"warning 后继续"（这正是第一轮翻车的原因）。
C. 只改一处、只加一个操作符；出错时删掉那一行即可回退。

【技术依据（实读确认）】
· `providerHandler.streamText()` = **增量** chunk（每块只带新增文本）⇒ 绝不能丢
· `GenerationHandler.generateText()` = `Flow<GenerationChunk>`，
  `emit(GenerationChunk.Messages(messages))` 里的 messages 是**完整快照** ⇒ 可丢中间帧
· ChatService 侧现有链：`generateText(...).onCompletion { ... }.collect { chunk -> ... }`
  每帧都做 `updateCurrentMessages`（O 全文）+ `updateConversation`（写 StateFlow）+ 事件发射
本批只在 `.collect` 之前插入采样，不动 provider 流、不动 onCompletion 的收尾逻辑。

【改动（一处）】
    }.collect { chunk ->          →   }.sample(kotlin.time.Duration.parse("PT0.08S")).collect { chunk -> // rhUiThrottle258
用全限定 `kotlin.time.Duration.parse(...)` 免掉 `milliseconds` 的 import 依赖（第一轮就死在这）。
`sample` 本身需要 `import kotlinx.coroutines.flow.sample`：锚点 `import kotlinx.coroutines.flow.onCompletion`
必须唯一，否则中止（不写盘）。

五查:
 1. import 清单: 仅 `kotlinx.coroutines.flow.sample` 一条；锚点不唯一则中止
 2. 同文件冲突: ChatService 被 batch95/232/233/234/235/238/251 改过；
    本批锚点 `}.collect { chunk ->` 与上述落点均不重叠（251 改的是 sendMessage 的 launch）
 3. 作用域: 纯 Flow 操作符插入，不引入新符号
 4. 括号配对: 新增 `.sample(...)` 1 对括号 => balance 不变（断言）
 5. 函数签名: 零改动
Python 三查: Q/SQ 变量构造引号; NL 显式 concat 禁 join/f-string/walrus; helper 先定义后用; 失败即中止
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
DIAG = 'ci_diag_batch258.txt'

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


class Abort(Exception):
    pass


def unique(lines, needle, label):
    hits = [i for i, ln in enumerate(lines) if ln.strip() == needle]
    if len(hits) != 1:
        note('ABORT ' + label + ': count=' + str(len(hits)) + ' (need exactly 1) -> ' + repr(needle))
        raise Abort(label)
    return hits[0]


def patch():
    p = ROOT / CS
    if not p.exists():
        note('ABORT missing ChatService.kt')
        return
    t = p.read_text(encoding='utf-8')
    if 'rhUiThrottle258' in t:
        note('already applied')
        return
    bal0 = balance(t)
    lines = t.split(NL)

    # A. 先确认 import 锚点唯一（失败即中止，不写盘）
    import_idx = unique(lines, 'import kotlinx.coroutines.flow.onCompletion', 'import onCompletion anchor')

    # B. 再确认 collect 锚点唯一
    collect_idx = unique(lines, '}.collect { chunk ->', 'collect anchor')

    # C. 两处都通过后才动
    if 'import kotlinx.coroutines.flow.sample' not in t:
        lines = lines[:import_idx + 1] + [
            'import kotlinx.coroutines.flow.sample // rhUiThrottle258',
        ] + lines[import_idx + 1:]
        collect_idx += 1

    ci = ind_of(lines[collect_idx])
    lines[collect_idx] = (ci + '}.sample(kotlin.time.Duration.parse("PT0.08S"))'
                          '.collect { chunk -> // rhUiThrottle258')

    t2 = lines_to_text(lines)
    if balance(t2) != bal0:
        note('ABORT balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
        return
    for need in ['import kotlinx.coroutines.flow.sample',
                 '.sample(kotlin.time.Duration.parse("PT0.08S"))',
                 '// rhUiThrottle258']:
        if need not in t2:
            note('ABORT selfcheck missing ' + need)
            return
    if t2.count('.sample(kotlin.time.Duration.parse("PT0.08S"))') != 1:
        note('ABORT sample inserted more than once')
        return
    p.write_text(t2, encoding='utf-8')
    note('chatService OK: sampled at collect (unique anchor), balances=' + str(bal0))


def write_diag():
    body = ''
    for line in report:
        body += str(line) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
        print('::error::batch258 diag written chars=' + str(len(body)))
    except Exception as e:
        print('::error::batch258 diag write FAILED ' + str(e)[:200])
    sys.stdout.flush()


def main():
    try:
        patch()
        note('1 ui throttle DONE')
    except Abort as e:
        note('1 ui throttle ABORTED (no file written): ' + str(e))
    except Exception as e:
        note('1 ui throttle EXCEPTION ' + type(e).__name__ + ' ' + str(e)[:300])
    print('::error::batch258 part: ui throttle')
    sys.stdout.flush()
    write_diag()
    for line in report:
        print('::error::batch258 ' + str(line)[:800])
    print('::error::batch258 END lines=' + str(len(report)))


main()
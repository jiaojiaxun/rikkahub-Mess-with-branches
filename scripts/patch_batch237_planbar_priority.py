#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch237: PlanBar 强制优先 —— 计划是必填项(用户要求)

用户反馈: PlanBar「不是第一时间显示, 到了后期才显示」; 要求「计划应该强制优先,
不是模型主动的, 是必填项」。

根因(读 snapshot 实读):
  A. 模型行为: TodoTools 描述仅说「Call it BEFORE starting a multi-step task (3+ steps)」,
     语气不足, 模型常拖到中后期才第一次调用。
  B. UI 门控: findActivePlan 要求 isExecuted —— 模型发出调用后还要等整批工具执行完
     (同批含慢工具时更久) 才显示。

修复:
  1. TodoTools.kt 描述强制化: MANDATORY FIRST STEP —— 任何 2+ 步任务的第一个工具调用
     必须是 todo_write(在其它工具调用/写文件/可见工作之前); 用户把计划当进度条, 期待
     任务一开始就出现; 这是要求不是可选。
  2. TodoPlanCard.kt findActivePlan: 去掉 isExecuted 门控, 改为「倒序取最新的可解析
     todo_write」——参数一完整立即显示(不等整批执行); 流式半截 JSON 解析失败自动跳过
     回落更早一次; 从未调用/不合法仍返回空(入口保持隐藏)。

五查:
1. import 清单: 无新 import(takeIf/filter/mapNotNull 均为 stdlib)
2. 同文件冲突: TodoTools.kt / TodoPlanCard.kt 均为 batch228 直接入库的新文件, 此后无在链
   patch 改过; 锚点=snapshot 实读
3. 作用域: 描述字符串块 + findActivePlan 函数体(含其上方注释), 不改签名/不引入符号
4. 括号配对: 三处替换块均自平衡; 全文 balance 断言
5. 函数签名: findActivePlan 签名与返回类型不变

Python 三查: 锚点均为无引号文本(em dash/中文/括号均安全); NL 手写 concat; fail-loud + 断言
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhPlanBar237'
TOOLS = 'app/src/main/java/me/rerere/rikkahub/data/ai/tools/TodoTools.kt'
CARD = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/TodoPlanCard.kt'


def fail(msg):
    print('::error::batch237 ' + str(msg)[:1400])
    sys.stdout.flush()
    sys.exit(1)


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def replace_once(text, old, new, label):
    n = text.count(old)
    if n == 0:
        fail(label + ': anchor not found. head=' + repr(old[:120]))
    if n != 1:
        fail(label + ': anchor count=' + str(n) + ' (expected 1). head=' + repr(old[:120]))
    return text.replace(old, new, 1)


def main():
    # ======== 1. TodoTools.kt 描述强制化 ========
    p = ROOT / TOOLS
    if not p.exists():
        fail('TodoTools.kt missing')
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        print('batch237: tools already applied')
    else:
        bal0 = balance(t)
        old_a = ('        Create or update the task plan for the current work. Use it to break a multi-step' + NL
                 + '        task into an explicit checklist and keep it current as you make progress.')
        new_a = ('        Create or update the task plan for the current work.' + NL
                 + NL
                 + '        MANDATORY FIRST STEP ( ' + MARK + ' ): For ANY task that involves 2 or more distinct steps,' + NL
                 + '        your FIRST tool call MUST be todo_write with the complete plan - before any other' + NL
                 + '        tool call, file write, or user-visible work. The user sees this plan as a live' + NL
                 + '        progress bar and expects it from the very start, not mid-task. This is required' + NL
                 + '        behavior, not optional.')
        t = replace_once(t, old_a, new_a, 'tools intro')
        old_b = ('        - Call it BEFORE starting a multi-step task (3+ distinct steps), and again every' + NL
                 + '          time a step\'s status changes. Skip it for simple single-step requests.')
        new_b = '        - Update the plan every time a step\'s status changes.'
        t = replace_once(t, old_b, new_b, 'tools rule')
        if balance(t) != bal0:
            fail('TodoTools: balance changed')
        p.write_text(t, encoding='utf-8')
        print('batch237: TodoTools OK')

    # ======== 2. TodoPlanCard.kt findActivePlan 提前 ========
    p2 = ROOT / CARD
    if not p2.exists():
        fail('TodoPlanCard.kt missing')
    c = p2.read_text(encoding='utf-8')
    if MARK in c:
        print('batch237: card already applied')
    else:
        bal1 = balance(c)
        old_c = ('/**' + NL
                 + ' * rhPlanBar228: 从消息列表里取「当前计划」——最后一条已执行的 todo_write 调用(文档5.5)。' + NL
                 + ' * 双向倒序取时间上最后一次调用;isExecuted 门控保证流式半截调用不算数;' + NL
                 + ' * 从未调用过或不合法时返回空列表(入口据此隐藏)。' + NL
                 + ' */' + NL
                 + 'fun findActivePlan(messages: List<UIMessage>): List<TodoEntry> =' + NL
                 + '    messages.asReversed()' + NL
                 + '        .asSequence()' + NL
                 + '        .flatMap { message -> message.parts.asReversed().asSequence() }' + NL
                 + '        .filterIsInstance<UIMessagePart.Tool>()' + NL
                 + '        .firstOrNull { it.toolName == TODO_TOOL_NAME && it.isExecuted }' + NL
                 + '        ?.let { parseTodos(it.input) }' + NL
                 + '        .orEmpty()')
        new_c = ('/**' + NL
                 + ' * rhPlanBar237: 从消息列表里取「当前计划」——倒序取最新的可解析 todo_write 调用(文档5.5)。' + NL
                 + ' * 不再要求 isExecuted: 模型一发出完整参数即显示(不必等整批工具执行完, 显示时机提前);' + NL
                 + ' * 流式半截 JSON 解析失败自动跳过并回落更早一次调用; 从未调用或不合法返回空(入口隐藏)。' + NL
                 + ' */' + NL
                 + 'fun findActivePlan(messages: List<UIMessage>): List<TodoEntry> =' + NL
                 + '    messages.asReversed()' + NL
                 + '        .asSequence()' + NL
                 + '        .flatMap { message -> message.parts.asReversed().asSequence() }' + NL
                 + '        .filterIsInstance<UIMessagePart.Tool>()' + NL
                 + '        .filter { it.toolName == TODO_TOOL_NAME }' + NL
                 + '        .mapNotNull { part -> parseTodos(part.input).takeIf { it.isNotEmpty() } }' + NL
                 + '        .firstOrNull()' + NL
                 + '        .orEmpty()')
        c = replace_once(c, old_c, new_c, 'findActivePlan')
        if balance(c) != bal1:
            fail('TodoPlanCard: balance changed')
        if 'isExecuted' in c.split('fun findActivePlan')[1].split('fun parseTodos')[0]:
            fail('TodoPlanCard: isExecuted still in findActivePlan')
        p2.write_text(c, encoding='utf-8')
        print('batch237: TodoPlanCard OK')

    print('::notice::batch237 OK - PlanBar mandatory-first (tool description) + show-on-parse (UI gate removed)')


main()
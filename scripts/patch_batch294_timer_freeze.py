#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch294: freeze the thought work timer when the block finishes.

Problem reported by the user:
- "worked Ns" kept increasing after the tool call had already finished.
- after output finished, the thinking timer could still keep counting.

Root cause:
- The old timer used the message-level `loading` flag. That stays true while
  final answer text is still streaming, even after every reasoning/tool step
  in the block is finished.
- When not loading and no reasoning finishedAt existed, it fell back to a
  fresh `tick` (current wall clock), so completed tool-only blocks could
  display an ever-growing duration.

Fix:
- Compute block activity from the steps themselves:
  Reasoning finishedAt == null, Tool not executed, ServerTool not finished.
- Only tick while that block activity is true.
- On active -> inactive transition, freeze the end timestamp.
- Use reasoning finishedAt when available; otherwise use the frozen end.
- Tool starts remain a valid start source, but a completed historical
  tool-only block without a known end still shows no fabricated duration.

Single file write, line/function-boundary anchored, idempotent marker
rhDrawer294, no exit(1) literal, no multi-line Python parentheses.
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhDrawer294'
DIAG = 'ci_diag_batch294_timer_freeze.txt'
DRAWER = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/RhThoughtDrawer.kt'
report = []
failures = []


def note(message):
    report.append(str(message)[:900])


def fail(message):
    failures.append(str(message)[:300])
    report.append('FAIL ' + str(message)[:420])


def lines_of(text):
    return text.split(NL)


def text_of(lines):
    out = ''
    for i, line in enumerate(lines):
        if i:
            out += NL
        out += line
    return out


def main():
    text = (ROOT / DRAWER).read_text(encoding='utf-8')
    if MARK in text:
        note('drawer already at 294')
    else:
        start = text.find('private fun rememberRhWorkedSeconds(')

        end = text.find('private fun rhStepsStartMillis(', start)
        if start < 0 or end < 0:
            fail('timer function boundaries missing')
        else:
            new_fn = '''private fun rememberRhWorkedSeconds(steps: List<ThinkingStep>, loading: Boolean): Long {
    val start = remember(steps) { rhStepsStartMillis(steps, true) }
    val recordedEnd = remember(steps) { rhStepsEndMillis(steps) }
    val active = loading && steps.any { step ->
        when (step) {
            is ThinkingStep.ReasoningStep -> step.reasoning.finishedAt == null
            is ThinkingStep.ToolStep -> !step.tool.isExecuted
            is ThinkingStep.ServerToolStep -> !step.tool.isFinished
        }
    }
    var tick by remember { mutableStateOf(0L) }
    var frozenEnd by remember { mutableStateOf(0L) }
    var wasActive by remember { mutableStateOf(false) }

    LaunchedEffect(active) {
        if (active) {
            wasActive = true
            frozenEnd = 0L
            while (true) {
                tick = System.currentTimeMillis()
                delay(1000L)
            }
        } else {
            tick = System.currentTimeMillis()
            if (wasActive && frozenEnd == 0L) {
                frozenEnd = tick
            }
        }
    }

    if (start == null || start <= 0L) {
        return 0L
    }
    val end = when {
        active -> maxOf(tick, start)
        frozenEnd > 0L -> maxOf(frozenEnd, recordedEnd ?: 0L)
        recordedEnd != null -> recordedEnd
        else -> return 0L
    }
    val delta = end - start
    if (delta <= 0L) {
        return 0L
    }
    return delta / 1000L
}

'''
            text = text[:start] + new_fn + text[end:]

        if MARK not in text:
            package_line = 'package me.rerere.rikkahub.ui.components.message'
            if package_line in text:
                text = text.replace(package_line, package_line + NL + '// ' + MARK, 1)
            else:
                fail('package line missing')

        checks = [
            'val active = loading && steps.any { step ->',
            'is ThinkingStep.ReasoningStep -> step.reasoning.finishedAt == null',
            'is ThinkingStep.ToolStep -> !step.tool.isExecuted',
            'is ThinkingStep.ServerToolStep -> !step.tool.isFinished',
            'var frozenEnd by remember { mutableStateOf(0L) }',
            'frozenEnd = tick',
            'rhStepsStartMillis(steps, true)',
        ]
        for token in checks:
            if token not in text:
                fail('missing ' + token)
        if 'val end = if (loading) maxOf(tick, start)' in text:
            fail('old loading-based end still present')
        if text.count('(') != text.count(')') or text.count('{') != text.count('}'):
            fail('drawer unbalanced')
        if not failures:
            (ROOT / DRAWER).write_text(text, encoding='utf-8')
            note('drawer 294 OK: block-active timer freezes after steps finish')

    body = NL.join(report) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:
        print('::error::batch294 diag write failed ' + str(exc)[:200])
    for line in report:
        print('::error::batch294 ' + str(line)[:800])
    if failures:
        print('::error::batch294 FAILED count=' + str(len(failures)))
        raise SystemExit(1)
    print('batch294: OK')


main()
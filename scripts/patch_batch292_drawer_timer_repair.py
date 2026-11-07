#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch292: repair the timer function after batch291.

batch291 tried to replace rhStepsStartMillis by scanning for the first
top-level brace. v9 produced a flat-indented function whose inner forEach
closing braces also sit at column 0, so 291 can cut inside the function.
This patch replaces the whole region between the two known function names
instead of scanning braces: rhStepsStartMillis -> rhStepsEndMillis.

It also re-asserts the reference group semantics if 291 did not land it.
Single write per file, no multi-line Python parentheses, no exit(0) literal.
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhDrawer292'
DIAG = 'ci_diag_batch292_drawer_timer_repair.txt'
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


def indent_of(line):
    stripped = line.lstrip()
    return line[:len(line) - len(stripped)]


def replace_block(lines, old_tail, new_block, label):
    start = -1
    for i in range(0, len(lines) - len(old_tail) + 1):
        if [line.strip() for line in lines[i:i + len(old_tail)]] == old_tail:
            start = i
            break
    if start < 0:
        fail(label + ' block missing')
        return lines
    base = indent_of(lines[start])
    block = []
    for line in new_block:
        block.append(base + line)
    return lines[:start] + block + lines[start + len(old_tail):]


def main():
    text = (ROOT / DRAWER).read_text(encoding='utf-8')
    if MARK in text:
        note('drawer already at 292')
    else:
        lines = lines_of(text)

        old_conditional = [
            'Column(modifier = Modifier.fillMaxWidth()) {',
            'steps.fastForEach { step ->',
            'if (step is ThinkingStep.ReasoningStep || groupOpened) {',
            'scope.content(step)',
            '}',
            '}',
            '}',
        ]
        new_conditional = [
            'if (groupOpened) {',
            '    Column(modifier = Modifier.fillMaxWidth()) {',
            '        steps.fastForEach { step ->',
            '            scope.content(step)',
            '        }',
            '    }',
            '}',
        ]
        if 'step is ThinkingStep.ReasoningStep || groupOpened' in text:
            lines = replace_block(lines, old_conditional, new_conditional, 'group block')

        for i, line in enumerate(lines):
            if 'val start = remember(steps) { rhStepsStartMillis(steps) }' in line:
                lines[i] = indent_of(line) + 'val start = remember(steps, loading) { rhStepsStartMillis(steps, loading) }'
                break

        text = text_of(lines)
        start = text.find('private fun rhStepsStartMillis(')
        end = text.find('private fun rhStepsEndMillis(', start)
        if start < 0 or end < 0:
            fail('timer function boundaries missing')
        else:
            new_fn = '''private fun rhStepsStartMillis(steps: List<ThinkingStep>, includeTools: Boolean): Long? {
    val candidates = mutableListOf<Long>()
    steps.filterIsInstance<ThinkingStep.ReasoningStep>().forEach { step ->
        candidates.add(step.reasoning.createdAt.toEpochMilliseconds())
    }
    if (includeTools) {
        steps.filterIsInstance<ThinkingStep.ToolStep>().forEach { step ->
            step.tool.executionStartedAt?.let { stamp ->
                candidates.add(stamp)
            }
        }
    }
    return candidates.minOrNull()
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
            'if (groupOpened) {',
            'rhStepsStartMillis(steps, loading)',
            'private fun rhStepsStartMillis(steps: List<ThinkingStep>, includeTools: Boolean)',
            'if (includeTools) {',
        ]
        for token in checks:
            if token not in text:
                fail('missing ' + token)
        if 'step is ThinkingStep.ReasoningStep || groupOpened' in text:
            fail('old group conditional remains')
        if text.count('(') != text.count(')') or text.count('{') != text.count('}'):
            fail('drawer unbalanced')
        if not failures:
            (ROOT / DRAWER).write_text(text, encoding='utf-8')
            note('drawer 292 OK: function-boundary timer repair')

    body = NL.join(report) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:
        print('::error::batch292 diag write failed ' + str(exc)[:200])
    for line in report:
        print('::error::batch292 ' + str(line)[:800])
    if failures:
        raise SystemExit(1)
    print('batch292: OK')


main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch291: two correctness fixes for the thought drawer.

1. The reference screenshots keep reasoning rows inside the tool group:
   F2 shows only "worked Ns" + "used N web tools" while the group is closed,
   F3 shows reasoning/tool rows interleaved after opening it. v9 exposed
   reasoning even with the group closed; restore the nested semantics.

2. v9 added Tool.executionStartedAt to the timer unconditionally. For a
   completed historical tool-only block the end timestamp is now, so it
   displayed a growing fake duration. Only include tool start times while
   loading is true; historical tool-only blocks fall back to the plain title.

Line-oriented, idempotent, no multi-line Python parentheses, no exit(1)
literal, every file written once after checks.
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhDrawer291'
DIAG = 'ci_diag_batch291_drawer_group_timer.txt'
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


def find_one(lines, predicate, label):
    hits = [i for i, line in enumerate(lines) if predicate(line)]
    if len(hits) != 1:
        fail(label + ' count=' + str(len(hits)))
        return -1
    return hits[0]


def replace_block(lines, start, old_tail, new_block):
    got = [line.strip() for line in lines[start:start + len(old_tail)]]
    if got != old_tail:
        fail('block mismatch at ' + str(start))
        return lines
    base = indent_of(lines[start])
    block = []
    for line in new_block:
        block.append(base + line)
    return lines[:start] + block + lines[start + len(old_tail):]


def main():
    text = (ROOT / DRAWER).read_text(encoding='utf-8')
    if MARK in text:
        note('drawer already at 291')
    else:
        lines = lines_of(text)
        package = find_one(lines, lambda line: line.strip() == 'package me.rerere.rikkahub.ui.components.message', 'package')
        if package < 0:
            note('no package, abort')
        else:
            old_tail = [
                'Column(modifier = Modifier.fillMaxWidth()) {',
                'steps.fastForEach { step ->',
                'if (step is ThinkingStep.ReasoningStep || groupOpened) {',
                'scope.content(step)',
                '}',
                '}',
                '}',
            ]
            start = -1
            for i in range(0, len(lines) - len(old_tail) + 1):
                if [line.strip() for line in lines[i:i + len(old_tail)]] == old_tail:
                    start = i
                    break
            if start < 0:
                fail('group block missing')
            else:
                new_block = [
                    'if (groupOpened) {',
                    '    Column(modifier = Modifier.fillMaxWidth()) {',
                    '        steps.fastForEach { step ->',
                    '            scope.content(step)',
                    '        }',
                    '    }',
                    '}',
                ]
                lines = replace_block(lines, start, old_tail, new_block)

            old_start = 'val start = remember(steps) { rhStepsStartMillis(steps) }'
            idx = find_one(lines, lambda line: line.strip() == old_start, 'timer call')
            if idx >= 0:
                lines[idx] = indent_of(lines[idx]) + 'val start = remember(steps, loading) { rhStepsStartMillis(steps, loading) }'

            fn_start = find_one(
                lines,
                lambda line: line.strip() == 'private fun rhStepsStartMillis(steps: List<ThinkingStep>): Long? {',
                'timer function',
            )
            if fn_start >= 0:
                fn_end = -1
                for i in range(fn_start + 1, len(lines)):
                    if lines[i].strip() == '}' and indent_of(lines[i]) == '':
                        fn_end = i
                        break
                if fn_end < 0:
                    fail('timer function end missing')
                else:
                    new_fn = [
                        'private fun rhStepsStartMillis(steps: List<ThinkingStep>, includeTools: Boolean): Long? {',
                        '    val candidates = mutableListOf<Long>()',
                        '    steps.filterIsInstance<ThinkingStep.ReasoningStep>().forEach { step ->',
                        '        candidates.add(step.reasoning.createdAt.toEpochMilliseconds())',
                        '    }',
                        '    if (includeTools) {',
                        '        steps.filterIsInstance<ThinkingStep.ToolStep>().forEach { step ->',
                        '            step.tool.executionStartedAt?.let { stamp ->',
                        '                candidates.add(stamp)',
                        '            }',
                        '        }',
                        '    }',
                        '    return candidates.minOrNull()',
                        '}',
                    ]
                    lines = lines[:fn_start] + new_fn + lines[fn_end + 1:]

            if MARK not in '\\n'.join(lines):
                lines.insert(package + 1, '// ' + MARK)
            text = text_of(lines)

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
            fail('old reasoning conditional still present')
        if text.count('(') != text.count(')') or text.count('{') != text.count('}'):
            fail('drawer unbalanced')
        if not failures:
            (ROOT / DRAWER).write_text(text, encoding='utf-8')
            note('drawer 291 OK: group nesting + loading-only tool timer')

    body = NL.join(report) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:
        print('::error::batch291 diag write failed ' + str(exc)[:200])
    for line in report:
        print('::error::batch291 ' + str(line)[:800])
    if failures:
        raise SystemExit(1)
    print('batch291: OK')


main()
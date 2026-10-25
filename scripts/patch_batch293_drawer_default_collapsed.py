#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch293: thought drawer stays collapsed by default, including while streaming.

Current source auto-expands both the drawer and the tool group whenever
loading is true:

    val opened = userExpanded || forceExpanded || loading
    val groupOpened = userGroupExpanded || forceExpanded || loading

That conflicts with the requested behavior: the drawer must default to
collapsed, and streaming/output must not change the fold state. This patch
removes only the `|| loading` term from both values.

forceExpanded is intentionally kept so a pending tool approval still forces
the drawer open; the approval card must never be hidden.
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhDrawer293'
DIAG = 'ci_diag_batch293_default_collapsed.txt'
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


def replace_line(lines, expected, replacement, label):
    idx = find_one(lines, lambda line: line.strip() == expected, label)
    if idx < 0:
        return lines
    lines[idx] = indent_of(lines[idx]) + replacement
    return lines


def main():
    text = (ROOT / DRAWER).read_text(encoding='utf-8')
    if MARK in text:
        note('drawer already at 293')
    else:
        lines = lines_of(text)
        lines = replace_line(
            lines,
            'val opened = userExpanded || forceExpanded || loading',
            'val opened = userExpanded || forceExpanded // ' + MARK + ': default collapsed',
            'opened line',
        )
        lines = replace_line(
            lines,
            'val groupOpened = userGroupExpanded || forceExpanded || loading',
            'val groupOpened = userGroupExpanded || forceExpanded // ' + MARK + ': group default collapsed',
            'groupOpened line',
        )
        text = text_of(lines)

        checks = [
            'val opened = userExpanded || forceExpanded // ' + MARK,
            'val groupOpened = userGroupExpanded || forceExpanded // ' + MARK,
            'rhStepsStartMillis(steps, loading)',
        ]
        for token in checks:
            if token not in text:
                fail('missing ' + token)
        if 'val opened = userExpanded || forceExpanded || loading' in text:
            fail('opened still auto-expands on loading')
        if 'val groupOpened = userGroupExpanded || forceExpanded || loading' in text:
            fail('groupOpened still auto-expands on loading')
        if text.count('(') != text.count(')') or text.count('{') != text.count('}'):
            fail('drawer unbalanced')
        if not failures:
            (ROOT / DRAWER).write_text(text, encoding='utf-8')
            note('drawer 293 OK: collapsed by default and independent of loading')

    body = NL.join(report) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:
        print('::error::batch293 diag write failed ' + str(exc)[:200])
    for line in report:
        print('::error::batch293 ' + str(line)[:800])
    if failures:
        print('::error::batch293 FAILED count=' + str(len(failures)))
        raise SystemExit(1)
    print('batch293: OK')


main()
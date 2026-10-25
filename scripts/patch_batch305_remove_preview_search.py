#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch305: remove preview search bar below the chat top bar.'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhPreviewSearchRemoved305'
DIAG = 'ci_diag_batch305_preview_search.txt'
FILE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
report = []
failures = []


def note(message):
    report.append(str(message)[:900])


def fail(message):
    failures.append(str(message)[:300])
    report.append('FAIL ' + str(message)[:520])


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def patch():
    path = ROOT / FILE
    text = path.read_text(encoding='utf-8')
    if MARK in text:
        note('already applied')
        return
    start = text.find('private fun ChatListPreview(')
    if start < 0:
        fail('ChatListPreview anchor missing')
        return
    tail = text[start:]
    old_block = '''        // 搜索框
        OutlinedTextField(
            value = searchQuery,
            onValueChange = { searchQuery = it },
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp),
            placeholder = { Text(stringResource(R.string.history_page_search)) },
            leadingIcon = {
                Icon(
                    imageVector = HugeIcons.Search01,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp)
                )
            },
            trailingIcon = {
                if (searchQuery.isNotEmpty()) {
                    IconButton(onClick = { searchQuery = "" }) {
                        Icon(
                            imageVector = HugeIcons.Cancel01,
                            contentDescription = stringResource(R.string.accessibility_clear_text),
                            modifier = Modifier.size(20.dp)
                        )
                    }
                }
            },
            singleLine = true,
            shape = CircleShape,
            maxLines = 1,
        )'''
    if tail.count(old_block) != 1:
        fail('search block count=' + str(tail.count(old_block)))
        return
    new_tail = tail.replace(
        old_block,
        '        // ' + MARK + ': 顶栏下方搜索遮挡条已移除',
        1,
    )

    old_padding = 'contentPadding = PaddingValues(16.dp) + PaddingValues(bottom = 32.dp + innerPadding.calculateBottomPadding()),'
    new_padding = 'contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 32.dp + innerPadding.calculateBottomPadding()), // ' + MARK
    if new_tail.count(old_padding) != 1:
        fail('preview padding anchor count=' + str(new_tail.count(old_padding)))
        return
    new_tail = new_tail.replace(old_padding, new_padding, 1)
    new_text = text[:start] + new_tail

    if balance(new_text) != balance(text):
        fail('source balance changed')
        return
    if 'OutlinedTextField(' in new_text:
        fail('preview search call still present')
        return
    if 'HugeIcons.Search01' not in new_text:
        fail('preview search icon import missing unexpectedly')
        return
    if new_text.count(MARK) < 2:
        fail('marker count=' + str(new_text.count(MARK)))
        return
    path.write_text(new_text, encoding='utf-8')
    note('preview OK: search bar removed, top padding 16 -> 8')


def write_diag():
    body = NL.join(report) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:
        print('::error::batch305 diag write failed ' + str(exc)[:200])
    for line in report:
        print('::error::batch305 ' + line)


def main():
    try:
        patch()
    except Exception as exc:
        fail('patch EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
    write_diag()
    if failures:
        print('::error::batch305 FAILED count=' + str(len(failures)))
        raise SystemExit(1)
    print('batch305: OK')


main()

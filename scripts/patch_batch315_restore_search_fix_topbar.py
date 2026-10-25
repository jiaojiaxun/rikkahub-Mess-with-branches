#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch315: restore preview search and fix top bar safe-area mismatch.'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK_SEARCH = 'rhPreviewSearchRestored315'
MARK_TOPBAR = 'rhTopBarHeight315'
DIAG = 'ci_diag_batch315_restore_search_topbar.txt'
CHATLIST = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
CHATPAGE = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'
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


def ensure_import(lines, line, anchor):
    stripped = [item.strip() for item in lines]
    if line in stripped:
        return True
    hits = [index for index, item in enumerate(stripped) if item == anchor]
    if len(hits) != 1:
        fail('import anchor ' + anchor + ' count=' + str(len(hits)))
        return False
    lines.insert(hits[0] + 1, line)
    return True


def patch_chatlist():
    path = ROOT / CHATLIST
    text = path.read_text(encoding='utf-8')
    if MARK_SEARCH in text:
        note('chatlist already applied')
        return
    if 'rhPreviewSearchRemoved305' not in text:
        fail('batch305 removal marker missing')
        return

    lines = text.split(NL)
    if not ensure_import(
        lines,
        'import me.rerere.hugeicons.stroke.Search01',
        'import me.rerere.hugeicons.stroke.CursorPointer01',
    ):
        return
    if not ensure_import(
        lines,
        'import androidx.compose.material3.OutlinedTextField',
        'import androidx.compose.material3.MaterialTheme',
    ):
        return
    text = NL.join(lines)

    old_comment = '        // rhPreviewSearchRemoved305: 顶栏下方搜索遮挡条已移除'
    search_block = '''        // ''' + MARK_SEARCH + ''': 恢复预览搜索框
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
    if text.count(old_comment) != 1:
        fail('search removal comment count=' + str(text.count(old_comment)))
        return
    text = text.replace(old_comment, search_block, 1)

    old_padding = 'contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 32.dp + innerPadding.calculateBottomPadding()), // rhPreviewSearchRemoved305'
    new_padding = 'contentPadding = PaddingValues(start = 16.dp, end = 16.dp, top = 8.dp, bottom = 32.dp + innerPadding.calculateBottomPadding()),'
    if text.count(old_padding) != 1:
        fail('preview padding anchor count=' + str(text.count(old_padding)))
        return
    text = text.replace(old_padding, new_padding, 1)

    if 'rhPreviewSearchRemoved305' in text:
        fail('old removal marker still present')
        return
    if MARK_SEARCH not in text:
        fail('restore marker missing')
        return
    for token in [
        'OutlinedTextField(',
        'HugeIcons.Search01',
        'import me.rerere.hugeicons.stroke.Search01',
        'import androidx.compose.material3.OutlinedTextField',
        'R.string.history_page_search',
    ]:
        if token not in text:
            fail('chatlist missing ' + token)
            return
    path.write_text(text, encoding='utf-8')
    note('chatlist OK: preview search restored')


def patch_chatpage():
    path = ROOT / CHATPAGE
    text = path.read_text(encoding='utf-8')
    if MARK_TOPBAR in text:
        note('chatpage already applied')
        return
    old_height = '.heightIn(min = 58.dp)'
    new_height = '.heightIn(min = 50.dp) // ' + MARK_TOPBAR + ': total 50 + 7*2 = 64dp'
    if text.count(old_height) != 1:
        fail('top bar height anchor count=' + str(text.count(old_height)))
        return
    new_text = text.replace(old_height, new_height, 1)
    if balance(new_text) != balance(text):
        fail('chatpage balance changed')
        return
    if new_text.count('.heightIn(min = 50.dp)') != 1:
        fail('new top bar height missing')
        return
    if '.heightIn(min = 58.dp)' in new_text:
        fail('old top bar height still present')
        return
    path.write_text(new_text, encoding='utf-8')
    note('chatpage OK: top bar row 58 -> 50, total aligns to 64dp')


def write_diag():
    body = NL.join(report) + NL
    try:
        (ROOT / DIAG).write_text(body, encoding='utf-8')
    except Exception as exc:
        print('::error::batch315 diag write failed ' + str(exc)[:200])
    for line in report:
        print('::error::batch315 ' + line)


def main():
    for name, action in [
        ('chatlist', patch_chatlist),
        ('chatpage', patch_chatpage),
    ]:
        try:
            action()
        except Exception as exc:
            fail(name + ' EXCEPTION ' + type(exc).__name__ + ' ' + str(exc)[:300])
    write_diag()
    if failures:
        print('::error::batch315 FAILED count=' + str(len(failures)))
        raise SystemExit(1)
    print('batch315: OK')


main()

#!/usr/bin/env python3
'''batch75: 关于板块清理 + 赞助弹窗删除（SettingPage.kt）

D 需求：
1. 删除赞助弹窗（launchCount > 100 的 AlertDialog）
2. 删除 aboutSettings CardGroup 里的三个入口：
   - 使用文档（openUrl docs.rikka-ai.com）
   - 赞助（跳 Screen.SettingDonate）
   - 分享（Intent.ACTION_SEND）
3. 保留：关于入口（跳 SettingAbout）+ 请求日志入口（跳 Screen.Log）

五查：
1. import 清单：无新 import（只删除代码）
2. 同文件冲突：SettingPage.kt 无在链脚本碰
3. 作用域：赞助弹窗在 Scaffold 前；aboutSettings 在 LazyColumn items 内
4. 括号配对：用配对扫描器找首尾，删除整块
5. 函数签名：无签名改动

Python 三查：无引号字面量 / 无未定义引用 / 无 f-string/walrus/join
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhAboutCleanup'


def concat_lines(lines):
    text = ''
    for index, line in enumerate(lines):
        if index > 0:
            text += NL
        text += line
    return text


def fail(path, message):
    print('::error file=' + path + '::batch75 ' + str(message)[:1400])
    raise SystemExit(1)


def find_paren_end(lines, start_index):
    '''从 start_index 开始，找配对的 ) 结束行（只看圆括号）'''
    depth = 0
    for i in range(start_index, len(lines)):
        for ch in lines[i]:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
                if depth == 0:
                    return i
    return -1


def find_brace_end(lines, start_index):
    '''从 start_index 开始，找配对的 } 结束行（只看花括号）'''
    depth = 0
    for i in range(start_index, len(lines)):
        for ch in lines[i]:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return i
    return -1


def find_item_start(lines, anchor_index):
    '''从 anchor_index 往上找 item( 开始行'''
    for i in range(anchor_index, max(anchor_index - 30, -1), -1):
        if lines[i].strip() == 'item(':
            return i
    return -1


SP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/setting/SettingPage.kt'
t = (ROOT / SP).read_text(encoding='utf-8')
if MARK in t:
    print('batch75: already applied')
else:
    lines = t.split(NL)
    applied = []

    # ============================================================
    # 1. 删除赞助弹窗（if (settings.launchCount > 100 && ...) { AlertDialog(...) }）
    # ============================================================
    launch_indices = []
    for index, line in enumerate(lines):
        if 'if (settings.launchCount > 100 &&' in line:
            launch_indices.append(index)
    if len(launch_indices) != 1:
        fail(SP, 'sponsor alert anchor count=' + str(len(launch_indices)))
    launch_idx = launch_indices[0]
    # 用花括号配对找 if 块的结束
    if_end = find_brace_end(lines, launch_idx)
    if if_end < 0:
        fail(SP, 'sponsor alert block end not found')
    # 删除整个 if 块
    lines = lines[:launch_idx] + lines[if_end + 1:]
    applied.append('sponsor-alert-removed')

    # ============================================================
    # 2. 删除使用文档入口（Icon(HugeIcons.Book01, null)）
    # ============================================================
    book_indices = []
    for index, line in enumerate(lines):
        if 'Icon(HugeIcons.Book01, null)' in line:
            book_indices.append(index)
    if len(book_indices) != 1:
        fail(SP, 'documentation icon anchor count=' + str(len(book_indices)))
    book_idx = book_indices[0]
    # 往上找 item( 开始
    item_start = find_item_start(lines, book_idx)
    if item_start < 0:
        fail(SP, 'documentation item start not found')
    # 用括号配对找 item( 的结束
    item_end = find_paren_end(lines, item_start)
    if item_end < 0:
        fail(SP, 'documentation item end not found')
    # 删除整个 item 块
    lines = lines[:item_start] + lines[item_end + 1:]
    applied.append('documentation-removed')

    # ============================================================
    # 3. 删除赞助入口（navController.navigate(Screen.SettingDonate)）
    # ============================================================
    donate_indices = []
    for index, line in enumerate(lines):
        if 'navController.navigate(Screen.SettingDonate)' in line:
            donate_indices.append(index)
    if len(donate_indices) != 1:
        fail(SP, 'donate navigate anchor count=' + str(len(donate_indices)))
    donate_idx = donate_indices[0]
    # 往上找 item( 开始
    item_start = find_item_start(lines, donate_idx)
    if item_start < 0:
        fail(SP, 'donate item start not found')
    # 用括号配对找 item( 的结束
    item_end = find_paren_end(lines, item_start)
    if item_end < 0:
        fail(SP, 'donate item end not found')
    # 删除整个 item 块
    lines = lines[:item_start] + lines[item_end + 1:]
    applied.append('donate-removed')

    # ============================================================
    # 4. 删除分享入口（Icon(HugeIcons.Share04, null)）
    # ============================================================
    share_indices = []
    for index, line in enumerate(lines):
        if 'Icon(HugeIcons.Share04, null)' in line:
            share_indices.append(index)
    if len(share_indices) != 1:
        fail(SP, 'share icon anchor count=' + str(len(share_indices)))
    share_idx = share_indices[0]
    # 往上找 item( 开始
    item_start = find_item_start(lines, share_idx)
    if item_start < 0:
        fail(SP, 'share item start not found')
    # 用括号配对找 item( 的结束
    item_end = find_paren_end(lines, item_start)
    if item_end < 0:
        fail(SP, 'share item end not found')
    # 删除整个 item 块
    lines = lines[:item_start] + lines[item_end + 1:]
    applied.append('share-removed')

    # ============================================================
    # 5. 自检
    # ============================================================
    text = concat_lines(lines)
    if 'settings.launchCount > 100' in text:
        fail(SP, 'sponsor alert still present after removal')
    if 'HugeIcons.Book01' in text:
        fail(SP, 'documentation icon still present after removal')
    if 'Screen.SettingDonate' in text and 'sponsorAlert' not in text:
        fail(SP, 'donate navigate still present after removal')
    if 'HugeIcons.Share04' in text:
        fail(SP, 'share icon still present after removal')
    if 'Screen.SettingAbout' not in text:
        fail(SP, 'about entry missing (should be preserved)')
    if 'Screen.Log' not in text:
        fail(SP, 'log entry missing (should be preserved)')
    (ROOT / SP).write_text(text, encoding='utf-8')
    print('batch75: OK (' + ', '.join(applied) + ')')

print('batch75: done')

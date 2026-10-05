#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
batch86b v5: Yuihub Step4-5 透传链 —— 修 #237 根因(尾逗号缺失)

=========== #237 根因(证据链完整,已确诊) ===========
报错:
    ChatMessage.kt:186 Syntax error: Expecting an element.
    ChatMessage.kt:186 Unresolved reference 'onChangeAvatar' on receiver of type 'Modifier'.
    ChatList.kt:202/495 No parameter with name 'onEditNickname' found.
真实源码(实读):
                ChatMessageUserAvatar(
                    nickname = settings.userNickname,
                    modifier = Modifier.weight(1f)      <-- 无尾逗号
                )
插入位置正确(在 `)` 之前),但【前一行无尾逗号】:
    modifier = Modifier.weight(1f)
    onChangeAvatar = onChangeUserAvatar,     <-- 被解析为 Modifier 链续行
=> 铁律 25 第三次复发(#216 形参 -> 本次实参)。v2 的括号配平只看闭合括号。

=========== v5 修法(结构性) ===========
1. ensure_trailing_comma():插入前确保插入点前一行以 ',' 结尾(注释前插)
2. 位置断言(铁律 29:配平相等 != 位置正确):
   a) 前一行须以 ',' 结尾  b) 插入区不得含 '.' 开头续行
   c) 插入后 3 行内须见闭合行  d) sig 参数行必须早于 call 实参行
3. dump 一律塞进 ::error message(#238 教训:print 落 job log,匿名读不到)
4. 失败路径显式 sys.exit(1)(v3 教训:漏 exit 使构建继续跑到测试阶段)

=========== 五查 ===========
1. import:ChatMessage 锚 data.model.Assistant;ChatList 锚 data.model.Conversation
   (均实读存在);行级 strip 全等 + 插入后回读断言
2. 同文件冲突:ChatMessage 被 batch66/68、ChatList 被 69/71/77 碰过
   -> 全用配平定位;本批只加可选参数,不覆盖那些补丁的改动
3. 作用域:ChatList 内 ChatMessage( 调用限定在 ChatListNormal 函数体(花括号配平),
   避开 ChatListPreview
4. 括号配对:插入自闭合行;补逗号不改配平;前后全文配平必须相等
5. 函数签名:全部新增可选参数(默认 null)-> 现有调用点零破坏

=========== Python 三查 ===========
1. 引号一律变量构造(Q=chr(34))2. 全部 helper 先定义后用;无非法语法
3. 无 f-string / walrus / join;失败路径显式 SystemExit
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhUserAvatarEdit'

# ---- 插入串常量:插入与自检共用同一份(#236 教训:物理上不可能漂移)----
CM_SIG_ROWS = [
    '// ' + MARK + ': 点消息处头像/昵称分别弹改头像/改昵称(对话页为唯一编辑入口)',
    'onChangeUserAvatar: ((Avatar) -> Unit)? = null,',
    'onEditUserNickname: (() -> Unit)? = null,',
]
CM_CALL_ROWS = [
    '// ' + MARK,
    'onChangeAvatar = onChangeUserAvatar,',
    'onEditNickname = onEditUserNickname,',
]
CL_SIG_ROWS = [
    '// ' + MARK,
    'onChangeUserAvatar: ((Avatar) -> Unit)? = null,',
    'onEditUserNickname: (() -> Unit)? = null,',
]
CL_FWD_ROWS = [
    '// ' + MARK,
    'onChangeUserAvatar = onChangeUserAvatar,',
    'onEditNickname = onEditUserNickname,',
]
AVATAR_IMP = 'import me.rerere.rikkahub.data.model.Avatar'


def fail(path, msg, dump_text=''):
    body = str(msg)[:800]
    if dump_text:
        body = body + ' || DUMP: ' + str(dump_text)[:1500]
    print('::error file=' + path + '::batch86b v5 ' + body)
    sys.stdout.flush()
    sys.exit(1)


def concat(lines):
    t = ''
    for i, ln in enumerate(lines):
        if i > 0:
            t += NL
        t += ln
    return t


def ind(ln):
    return ln[:len(ln) - len(ln.lstrip())]


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def strip_comment(line):
    i = line.find('//')
    return line[:i] if i >= 0 else line


def dump_str(lines, lo, hi):
    out = []
    for i in range(max(0, lo), min(hi, len(lines))):
        out.append('L' + str(i + 1) + ':' + lines[i].strip()[:80])
    return ' | '.join(out)


def paren_close(lines, start):
    depth = 0
    seen = False
    for i in range(start, len(lines)):
        for ch in strip_comment(lines[i]):
            if ch == '(':
                depth += 1
                seen = True
            elif ch == ')':
                depth -= 1
        if seen and depth <= 0:
            return i
    return -1


def ensure_trailing_comma(lines, prev_idx):
    if prev_idx < 0:
        return False
    s = lines[prev_idx].rstrip()
    if s.endswith(','):
        return False
    ci = s.find('//')
    if ci >= 0:
        lines[prev_idx] = s[:ci].rstrip() + ', ' + s[ci:]
    else:
        lines[prev_idx] = s + ','
    return True


def insert_before_close(lines, decl_anchor, rows, path, tag):
    hits = [i for i, ln in enumerate(lines) if ln.strip() == decl_anchor]
    if len(hits) != 1:
        fail(path, tag + ' anchor count=' + str(len(hits)), dump_str(lines, 0, len(lines)))
    si = hits[0]
    close = paren_close(lines, si)
    if close < 0:
        fail(path, tag + ' parens never balance', dump_str(lines, si, si + 40))
    if close <= si:
        fail(path, tag + ' close<=start ' + str(close) + '<=' + str(si))

    added_comma = ensure_trailing_comma(lines, close - 1)

    d = ind(lines[si])
    for j, r in enumerate(rows):
        lines.insert(close + j, d + r)
    ins_lo = close
    ins_hi = close + len(rows) - 1

    prev_line = lines[ins_lo - 1].rstrip()
    if not prev_line.endswith(','):
        fail(path, tag + ' prev line missing comma: ' + repr(prev_line),
             dump_str(lines, ins_lo - 3, ins_hi + 4))
    if any(ln.strip().startswith('.') for ln in lines[ins_lo:ins_hi + 1]):
        fail(path, tag + ' inserted region has chained-dot line',
             dump_str(lines, ins_lo - 3, ins_hi + 4))
    found_close = False
    for i in range(ins_hi + 1, min(ins_hi + 4, len(lines))):
        st = lines[i].strip()
        if st == ')' or st == ') {' or st.startswith('),'):
            found_close = True
            break
    if not found_close:
        fail(path, tag + ' no closing paren within 3 lines',
             dump_str(lines, si, min(ins_hi + 6, len(lines))))
    return len(rows), added_comma


def assert_rows_present(lines, rows, path, tag, expect):
    for r in rows:
        c = sum(1 for ln in lines if ln.strip() == r)
        if c != expect:
            fail(path, tag + ' count=' + str(c) + ' expect=' + str(expect) + ' :: ' + r,
                 dump_str(lines, 0, len(lines)))


results = []

# =========================================================================
# Step4  ChatMessage.kt
# =========================================================================
CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
cm = (ROOT / CM).read_text(encoding='utf-8')
if MARK in cm:
    print('batch86b v5: ChatMessage already applied')
else:
    lines = cm.split(NL)
    bal0 = balance(cm)
    applied = []

    if not any(ln.strip() == AVATAR_IMP for ln in lines):
        hits = [i for i, ln in enumerate(lines) if ln.strip() == 'import me.rerere.rikkahub.data.model.Assistant']
        if len(hits) != 1:
            fail(CM, 'Assistant import anchor count=' + str(len(hits)), dump_str(lines, 0, 220))
        lines.insert(hits[0], AVATAR_IMP)
        if not any(ln.strip() == AVATAR_IMP for ln in lines):
            fail(CM, 'Avatar import read-back failed')
        applied.append('import-Avatar')

    n, c1 = insert_before_close(lines, 'fun ChatMessage(', CM_SIG_ROWS, CM, 'ChatMessage sig')
    applied.append('sig+' + str(n) + ('+comma' if c1 else ''))
    n, c2 = insert_before_close(lines, 'ChatMessageUserAvatar(', CM_CALL_ROWS, CM, 'ChatMessageUserAvatar call')
    applied.append('call+' + str(n) + ('+comma' if c2 else ''))

    assert_rows_present(lines, CM_SIG_ROWS[1:], CM, 'ChatMessage sig', 1)
    assert_rows_present(lines, CM_CALL_ROWS[1:], CM, 'ChatMessage call', 1)
    if not any(ln.strip() == AVATAR_IMP for ln in lines):
        fail(CM, 'Avatar import missing (strip-equal)')
    t = concat(lines)
    if balance(t) != bal0:
        fail(CM, 'balance changed ' + str(bal0) + '->' + str(balance(t)))
    sig_i = [i for i, ln in enumerate(lines) if ln.strip() == CM_SIG_ROWS[1]][0]
    call_i = [i for i, ln in enumerate(lines) if ln.strip() == CM_CALL_ROWS[1]][0]
    if sig_i > call_i:
        fail(CM, 'param inserted after call site')
    (ROOT / CM).write_text(t, encoding='utf-8')
    results.append('ChatMessage(' + ', '.join(applied) + ')')
    print('batch86b v5: ChatMessage OK (' + ', '.join(applied) + ')')

# =========================================================================
# Step5  ChatList.kt
# =========================================================================
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
cl = (ROOT / CL).read_text(encoding='utf-8')
if MARK in cl:
    print('batch86b v5: ChatList already applied')
else:
    lines = cl.split(NL)
    bal0 = balance(cl)
    applied = []

    if not any(ln.strip() == AVATAR_IMP for ln in lines):
        hits = [i for i, ln in enumerate(lines) if ln.strip() == 'import me.rerere.rikkahub.data.model.Conversation']
        if len(hits) != 1:
            fail(CL, 'Conversation import anchor count=' + str(len(hits)), dump_str(lines, 0, 220))
        lines.insert(hits[0], AVATAR_IMP)
        if not any(ln.strip() == AVATAR_IMP for ln in lines):
            fail(CL, 'Avatar import read-back failed')
        applied.append('import-Avatar')

    n, c = insert_before_close(lines, 'fun ChatList(', CL_SIG_ROWS, CL, 'ChatList sig')
    applied.append('ChatList-sig+' + str(n) + ('+comma' if c else ''))
    n, c = insert_before_close(lines, 'ChatListNormal(', CL_FWD_ROWS, CL, 'ChatListNormal call')
    applied.append('forward1+' + str(n) + ('+comma' if c else ''))
    n, c = insert_before_close(lines, 'private fun ChatListNormal(', CL_SIG_ROWS, CL, 'ChatListNormal sig')
    applied.append('ChatListNormal-sig+' + str(n) + ('+comma' if c else ''))

    fn_hits = [i for i, ln in enumerate(lines) if ln.strip() == 'private fun ChatListNormal(']
    if len(fn_hits) != 1:
        fail(CL, 'ChatListNormal decl count=' + str(len(fn_hits)), dump_str(lines, 0, len(lines)))
    fn_start = fn_hits[0]
    sig_close = paren_close(lines, fn_start)
    if sig_close < 0:
        fail(CL, 'ChatListNormal parens never balance', dump_str(lines, fn_start, fn_start + 40))
    brace = 0
    seen = False
    fn_end = -1
    for i in range(sig_close, len(lines)):
        for ch in strip_comment(lines[i]):
            if ch == '{':
                brace += 1
                seen = True
            elif ch == '}':
                brace -= 1
        if seen and brace <= 0:
            fn_end = i
            break
    if fn_end < 0:
        fail(CL, 'ChatListNormal body never balances', dump_str(lines, sig_close, sig_close + 40))
    inner = [i for i in range(sig_close, fn_end) if lines[i].strip() == 'ChatMessage(']
    if len(inner) != 1:
        fail(CL, 'ChatMessage( inside ChatListNormal count=' + str(len(inner)),
             dump_str(lines, sig_close, fn_end))
    ci = inner[0]
    ci_close = paren_close(lines, ci)
    if ci_close < 0 or ci_close > fn_end:
        fail(CL, 'ChatMessage call close outside body', dump_str(lines, ci, min(ci + 30, len(lines))))
    c = ensure_trailing_comma(lines, ci_close - 1)
    d = ind(lines[ci])
    for j, r in enumerate(CL_FWD_ROWS):
        lines.insert(ci_close + j, d + r)
    prev_line = lines[ci_close - 1].rstrip()
    if not prev_line.endswith(','):
        fail(CL, 'forward2 prev line missing comma: ' + repr(prev_line),
             dump_str(lines, ci_close - 3, ci_close + 6))
    applied.append('forward2+3' + ('+comma' if c else ''))

    assert_rows_present(lines, CL_SIG_ROWS[1:], CL, 'ChatList sig rows', 2)
    assert_rows_present(lines, CL_FWD_ROWS[1:], CL, 'ChatList fwd rows', 2)
    if not any(ln.strip() == AVATAR_IMP for ln in lines):
        fail(CL, 'Avatar import missing (strip-equal)')
    t = concat(lines)
    if balance(t) != bal0:
        fail(CL, 'balance changed ' + str(bal0) + '->' + str(balance(t)))
    (ROOT / CL).write_text(t, encoding='utf-8')
    results.append('ChatList(' + ', '.join(applied) + ')')
    print('batch86b v5: ChatList OK (' + ', '.join(applied) + ')')

print('batch86b v5: OK -> ' + ' | '.join(results))

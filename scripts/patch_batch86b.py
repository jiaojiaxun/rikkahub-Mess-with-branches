#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
batch86b v2: Yuihub Step4-5 透传链 —— 修 #236 自检串不一致

#236 验尸(根因唯一,证据确凿):
    batch86b sig/call line count wrong: sig=0 call=1
    - call=1 -> ChatMessageUserAvatar 调用点插入【成功】
    - sig=0  -> ChatMessage 签名参数【检查失败】,但插入其实也成功了
根因:严格自检的检查串漏了尾逗号 ——
    插入的是 'onChangeUserAvatar: ((Avatar) -> Unit)? = null,'(带逗号)
    检查写的却是 'onChangeUserAvatar: ((Avatar) -> Unit)? = null'(无逗号)
    同批里前面用子串 in(过了)、后面用 strip 全等(挂了),两种匹配不一致。
这是自检 bug 第 3 次(#225 假阳性 -> batch86a v1 非法 Python -> 本次逗号不一致)。

【结构性修法(本批落实)】
    插入行与检查行共用【同一份常量】:
        CM_SIG_ROWS / CM_CALL_ROWS / CL_* 只定义一次,
        插入用它,自检也用同一变量 -> 物理上不可能再出现"两处写法不一致"。
    另:所有自检一律用 strip 全等(与铁律20 一致),不再混用 in 子串。

================================ 五查(与 v1 相同,仅自检修正) ============
1. import:ChatMessage 锚 data.model.Assistant;ChatList 锚 data.model.Conversation
   (均实读存在);插入后回读断言(行级 strip 全等)
2. 同文件冲突:ChatMessage 被 batch66/68 碰过、ChatList 被 69/71/77 碰过
   -> 签名锚必须【括号配平定位】,不用"最后一个参数"假设(#216 教训)
3. 作用域:ChatList 内 ChatMessage( 调用限定在 ChatListNormal 函数体区间
   (花括号配平找 fn_end),避开 ChatListPreview
4. 括号配对:插入自闭合行;插入前后全文配平必须相等
5. 函数签名:全部新增【可选参数(默认 null)】-> 现有调用点零破坏

============================ Python 三查 ===============================
1. 无引号字面量问题:Q/SQ 变量拼接
2. 无未定义引用:全部 helper 先定义后用;常量先定义后用
3. 无 f-string / walrus / join;无非法 for(v1 教训)

========================== 铁律 28 检查 =================================
本批不插入 @Composable 函数块 -> #232 注解重复模式不适用。
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhUserAvatarEdit'

# ---- 插入串常量(插入与自检共用同一份,杜绝两处写法漂移)----
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


def fail(path, msg):
    print('::error file=' + path + '::batch86b ' + str(msg)[:1400])
    raise SystemExit(1)


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
    if i >= 0:
        return line[:i]
    return line


def dump(lines, lo, hi, title):
    print('  dump ' + title + ':')
    for i in range(max(0, lo), min(hi, len(lines))):
        print('    >> ' + str(i) + ': ' + lines[i].strip()[:150])


def paren_close(lines, start):
    '''从 start 行(含 `fun Xxx(` 或 `Xxx(`)做 paren 深度扫描(先剥行注释),
       返回 depth 首次归零的行号;失败 -1。'''
    depth = 0
    seen = False
    for i in range(start, len(lines)):
        code = strip_comment(lines[i])
        for ch in code:
            if ch == '(':
                depth += 1
                seen = True
            elif ch == ')':
                depth -= 1
        if seen and depth <= 0:
            return i
    return -1


def insert_before_close(lines, decl_anchor, rows, path, tag):
    '''锚 decl_anchor(strip 全等,唯一) -> 配平找闭合行 -> 在闭合行前插入 rows'''
    hits = [i for i, ln in enumerate(lines) if ln.strip() == decl_anchor]
    if len(hits) != 1:
        dump(lines, 0, len(lines), decl_anchor)
        fail(path, tag + ' decl count=' + str(len(hits)))
    si = hits[0]
    close = paren_close(lines, si)
    if close < 0:
        dump(lines, si, min(si + 40, len(lines)), tag + ' signature')
        fail(path, tag + ' signature parens never balance')
    d = ind(lines[si])
    for j, r in enumerate(rows):
        lines.insert(close + j, d + r)
    return len(rows)


def assert_rows_present(lines, rows, path, tag, expect):
    '''用与插入【同一份常量】做 strip 全等计数断言'''
    for r in rows:
        c = sum(1 for ln in lines if ln.strip() == r)
        if c != expect:
            dump(lines, 0, len(lines), tag + ' rows (want ' + str(expect) + 'x ' + r + ')')
            fail(path, tag + ' row count=' + str(c) + ' expect=' + str(expect) + ' :: ' + r)


results = []

# =========================================================================
# Step4  ChatMessage.kt
# =========================================================================
CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
cm = (ROOT / CM).read_text(encoding='utf-8')
if MARK in cm:
    print('batch86b: ChatMessage already applied')
else:
    lines = cm.split(NL)
    bal0 = balance(cm)
    applied = []

    # 4a. import Avatar(锚 = 实读存在的 data.model.Assistant)
    if not any(ln.strip() == AVATAR_IMP for ln in lines):
        hits = [i for i, ln in enumerate(lines) if ln.strip() == 'import me.rerere.rikkahub.data.model.Assistant']
        if len(hits) != 1:
            dump(lines, 0, 220, 'Assistant import')
            fail(CM, 'Assistant import anchor count=' + str(len(hits)))
        lines.insert(hits[0], AVATAR_IMP)
        if not any(ln.strip() == AVATAR_IMP for ln in lines):
            fail(CM, 'Avatar import read-back failed')
        applied.append('import-Avatar')

    # 4b. ChatMessage 签名 +3(配平定位)
    n = insert_before_close(lines, 'fun ChatMessage(', CM_SIG_ROWS, CM, 'ChatMessage')
    applied.append('sig+' + str(n))

    # 4c. ChatMessageUserAvatar 调用 +3(配平定位)
    n = insert_before_close(lines, 'ChatMessageUserAvatar(', CM_CALL_ROWS, CM, 'ChatMessageUserAvatar call')
    applied.append('call+' + str(n))

    # 自检(共用常量 + strip 全等)
    assert_rows_present(lines, CM_SIG_ROWS[1:], CM, 'ChatMessage sig', 1)
    assert_rows_present(lines, CM_CALL_ROWS[1:], CM, 'ChatMessage call', 1)
    if not any(ln.strip() == AVATAR_IMP for ln in lines):
        fail(CM, 'Avatar import missing (strip-equal)')
    t = concat(lines)
    if balance(t) != bal0:
        fail(CM, 'bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(t)))
    # 位置断言:签名参数必须早于调用实参
    sig_i = [i for i, ln in enumerate(lines) if ln.strip() == CM_SIG_ROWS[1]][0]
    call_i = [i for i, ln in enumerate(lines) if ln.strip() == CM_CALL_ROWS[1]][0]
    if sig_i > call_i:
        fail(CM, 'param inserted after call site (wrong region)')
    (ROOT / CM).write_text(t, encoding='utf-8')
    results.append('ChatMessage(' + ', '.join(applied) + ')')
    print('batch86b: ChatMessage OK (' + ', '.join(applied) + ')')

# =========================================================================
# Step5  ChatList.kt
# =========================================================================
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
cl = (ROOT / CL).read_text(encoding='utf-8')
if MARK in cl:
    print('batch86b: ChatList already applied')
else:
    lines = cl.split(NL)
    bal0 = balance(cl)
    applied = []

    # 5a. import Avatar(锚 = 实读存在的 data.model.Conversation)
    if not any(ln.strip() == AVATAR_IMP for ln in lines):
        hits = [i for i, ln in enumerate(lines) if ln.strip() == 'import me.rerere.rikkahub.data.model.Conversation']
        if len(hits) != 1:
            dump(lines, 0, 220, 'Conversation import')
            fail(CL, 'Conversation import anchor count=' + str(len(hits)))
        lines.insert(hits[0], AVATAR_IMP)
        if not any(ln.strip() == AVATAR_IMP for ln in lines):
            fail(CL, 'Avatar import read-back failed')
        applied.append('import-Avatar')

    # 5b. ChatList 签名 +3
    n = insert_before_close(lines, 'fun ChatList(', CL_SIG_ROWS, CL, 'ChatList')
    applied.append('ChatList-sig+' + str(n))

    # 5c. ChatList -> ChatListNormal 转发 +3
    n = insert_before_close(lines, 'ChatListNormal(', CL_FWD_ROWS, CL, 'ChatListNormal call')
    applied.append('forward1+' + str(n))

    # 5d. ChatListNormal 签名 +3
    n = insert_before_close(lines, 'private fun ChatListNormal(', CL_SIG_ROWS, CL, 'ChatListNormal')
    applied.append('ChatListNormal-sig+' + str(n))

    # 5e. ChatListNormal -> ChatMessage 转发 +3(限定在 ChatListNormal 函数体内)
    fn_hits = [i for i, ln in enumerate(lines) if ln.strip() == 'private fun ChatListNormal(']
    if len(fn_hits) != 1:
        dump(lines, 0, len(lines), 'private fun ChatListNormal(')
        fail(CL, 'ChatListNormal decl count=' + str(len(fn_hits)))
    fn_start = fn_hits[0]
    sig_close = paren_close(lines, fn_start)
    if sig_close < 0:
        fail(CL, 'ChatListNormal signature parens never balance')
    brace = 0
    seen = False
    fn_end = -1
    for i in range(sig_close, len(lines)):
        code = strip_comment(lines[i])
        for ch in code:
            if ch == '{':
                brace += 1
                seen = True
            elif ch == '}':
                brace -= 1
        if seen and brace <= 0:
            fn_end = i
            break
    if fn_end < 0:
        dump(lines, sig_close, min(sig_close + 40, len(lines)), 'ChatListNormal body')
        fail(CL, 'ChatListNormal body never balances')
    inner = [i for i in range(sig_close, fn_end) if lines[i].strip() == 'ChatMessage(']
    if len(inner) != 1:
        dump(lines, sig_close, fn_end, 'ChatMessage( inside ChatListNormal')
        fail(CL, 'ChatMessage( call inside ChatListNormal count=' + str(len(inner)))
    ci = inner[0]
    ci_close = paren_close(lines, ci)
    if ci_close < 0 or ci_close > fn_end:
        fail(CL, 'ChatMessage call close not found within ChatListNormal body')
    d = ind(lines[ci])
    for j, r in enumerate(CL_FWD_ROWS):
        lines.insert(ci_close + j, d + r)
    applied.append('forward2+3')

    # 自检(共用常量 + strip 全等)
    assert_rows_present(lines, CL_SIG_ROWS[1:], CL, 'ChatList sig rows', 2)   # 两层签名
    assert_rows_present(lines, CL_FWD_ROWS[1:], CL, 'ChatList fwd rows', 2)   # 两处转发
    if not any(ln.strip() == AVATAR_IMP for ln in lines):
        fail(CL, 'Avatar import missing (strip-equal)')
    t = concat(lines)
    if balance(t) != bal0:
        fail(CL, 'bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(t)))
    (ROOT / CL).write_text(t, encoding='utf-8')
    results.append('ChatList(' + ', '.join(applied) + ')')
    print('batch86b: ChatList OK (' + ', '.join(applied) + ')')

print('batch86b: OK -> ' + ' | '.join(results))

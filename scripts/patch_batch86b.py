#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
batch86b v7: Yuihub Step4-5 透传链 —— 修 #242 根因(转发参数名 typo)

=========== #242 验尸(证据链完整) ===========
报错: ChatList.kt:202/495  No parameter with name 'onEditNickname' found.
202 = ChatList -> ChatListNormal 转发行
495 = ChatListNormal -> ChatMessage 转发行

参数链各层的【正确】参数名:
  ChatPage   -> ChatList              : onEditUserNickname
  ChatList   -> ChatListNormal        : onEditUserNickname   <- 我写错了
  ChatListNormal -> ChatMessage       : onEditUserNickname   <- 我写错了
  ChatMessage -> ChatMessageUserAvatar: onEditNickname       (叶子层,正确)

我的 CL_FWD_ROWS 硬编码了 'onEditNickname = onEditUserNickname,'
——把【叶子层】的参数名 onEditNickname 错用于【中间转发层】。

为什么自检没拦住:assert_rows_present 只验证"我写的行存在",而我写的就是那行 typo
—— 自检验证的是"我写了什么",不是"该写什么"。和 #236 同一类陷阱。

=========== v7 结构性修法(不是补丁) ===========
【派生代替硬编码】转发行不再手写,从签名行派生:
  def fwd_of(decl): 'onChangeUserAvatar: T = null,' -> 'onChangeUserAvatar = onChangeUserAvatar,'
  CL_FWD_ROWS = ['// ' + MARK] + [fwd_of(r) for r in CL_SIG_ROWS[1:]]
  => 转发行的左/右参数名与签名行【同一份来源】,物理上不可能再不一致。

加一致性断言(铁律 33):
  对每条转发行 'A = B,' 断言 A == B 且 A in 已声明签名参数名集合。
  (转发=纯透传时,左右名必须一致;若将来要改名,必须显式走 rename 表,不允许 typo 混进去)

=========== 其余与 v6 完全一致(五查 + Python 三查 + 铁律 25/29/30/31) ===========
铁律 32:判断行尾符号必须剥 // 注释(用 code_part)
铁律 33(新增):转发参数名 = 签名参数名 的纯透传,必须从签名行【派生】,禁手写两遍
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhUserAvatarEdit'

CM_SIG_ROWS = [
    '// ' + MARK + ': 点消息处头像/昵称分别弹改头像/改昵称(对话页为唯一编辑入口)',
    'onChangeUserAvatar: ((Avatar) -> Unit)? = null,',
    'onEditUserNickname: (() -> Unit)? = null,',
]
# ChatMessage -> ChatMessageUserAvatar:叶子层参数名不同(显式 rename),手写但单独校验
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
AVATAR_IMP = 'import me.rerere.rikkahub.data.model.Avatar'


def param_name_of(decl):
    '''从声明行提取参数名: 'onChangeUserAvatar: T = null,' -> 'onChangeUserAvatar' '''
    return decl.strip().split(':', 1)[0].strip()


# CL_FWD_ROWS 从 CL_SIG_ROWS 派生(纯透传,左右同名)—— 物理上不可能 typo
CL_FWD_ROWS = ['// ' + MARK] + [param_name_of(r) + ' = ' + param_name_of(r) + ','
                                for r in CL_SIG_ROWS[1:]]


def fail(path, msg, dump_text=''):
    body = str(msg)[:800]
    if dump_text:
        body = body + ' || DUMP: ' + str(dump_text)[:1500]
    print('::error file=' + path + '::batch86b v7 ' + body)
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


def code_part(line):
    i = line.find('//')
    if i >= 0:
        return line[:i].rstrip()
    return line.rstrip()


def paren_close(lines, start):
    depth = 0
    seen = False
    for i in range(start, len(lines)):
        for ch in code_part(lines[i]):
            if ch == '(':
                depth += 1
                seen = True
            elif ch == ')':
                depth -= 1
        if seen and depth <= 0:
            return i
    return -1


def dump_str(lines, lo, hi):
    out = []
    for i in range(max(0, lo), min(hi, len(lines))):
        out.append('L' + str(i + 1) + ':' + lines[i].strip()[:80])
    return ' | '.join(out)


def ensure_trailing_comma(lines, prev_idx):
    if prev_idx < 0:
        return False, False
    raw = lines[prev_idx]
    code = code_part(raw)
    ci = raw.find('//')
    fixed_double = False
    if code.endswith(',,'):
        code = code[:-1]
        fixed_double = True
    if code.endswith(','):
        if fixed_double:
            lines[prev_idx] = code + (' ' + raw[ci:] if ci >= 0 else '')
        return False, fixed_double
    new_code = code + ','
    if ci >= 0:
        lines[prev_idx] = new_code + ' ' + raw[ci:]
    else:
        lines[prev_idx] = new_code
    return True, fixed_double


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
    added, fixed = ensure_trailing_comma(lines, close - 1)
    d = ind(lines[si])
    for j, r in enumerate(rows):
        lines.insert(close + j, d + r)
    ins_lo = close
    ins_hi = close + len(rows) - 1
    prev_code = code_part(lines[ins_lo - 1])
    if not prev_code.endswith(','):
        fail(path, tag + ' prev code missing comma: ' + repr(prev_code),
             dump_str(lines, ins_lo - 3, ins_hi + 4))
    if prev_code.endswith(',,'):
        fail(path, tag + ' prev code has double comma: ' + repr(prev_code),
             dump_str(lines, ins_lo - 3, ins_hi + 4))
    if any(code_part(ln).startswith('.') for ln in lines[ins_lo:ins_hi + 1]):
        fail(path, tag + ' inserted region has chained-dot code',
             dump_str(lines, ins_lo - 3, ins_hi + 4))
    found = False
    for i in range(ins_hi + 1, min(ins_hi + 4, len(lines))):
        st = lines[i].strip()
        if st == ')' or st == ') {' or st.startswith('),'):
            found = True
            break
    if not found:
        fail(path, tag + ' no closing paren within 3 lines',
             dump_str(lines, si, min(ins_hi + 6, len(lines))))
    return len(rows), added, fixed


def assert_rows_present(lines, rows, path, tag, expect):
    for r in rows:
        c = sum(1 for ln in lines if ln.strip() == r)
        if c != expect:
            fail(path, tag + ' count=' + str(c) + ' expect=' + str(expect) + ' :: ' + r,
                 dump_str(lines, 0, len(lines)))


def check_fwd_consistency(sig_rows, fwd_rows, path, tag):
    '''铁律 33:纯透传转发行 'A = B,' 须满足 A==B 且 A 在签名声明参数名集合内'''
    declared = set(param_name_of(r) for r in sig_rows if not r.strip().startswith('//'))
    for r in fwd_rows:
        st = r.strip()
        if st.startswith('//'):
            continue
        lhs = st.split('=', 1)[0].strip()
        rhs = st.split('=', 1)[1].strip().rstrip(',')
        if lhs != rhs:
            fail(path, tag + ' pass-through renamed: ' + repr(st))
        if lhs not in declared:
            fail(path, tag + ' fwd param not declared: ' + repr(lhs) + ' declared=' + str(sorted(declared)))


results = []

# =========================================================================
# Step4  ChatMessage.kt
# =========================================================================
CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
cm = (ROOT / CM).read_text(encoding='utf-8')
if MARK in cm:
    print('batch86b v7: ChatMessage already applied')
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

    n, a1, f1 = insert_before_close(lines, 'fun ChatMessage(', CM_SIG_ROWS, CM, 'ChatMessage sig')
    applied.append('sig+' + str(n) + ('+comma' if a1 else '') + ('+dedup' if f1 else ''))
    n, a2, f2 = insert_before_close(lines, 'ChatMessageUserAvatar(', CM_CALL_ROWS, CM, 'ChatMessageUserAvatar call')
    applied.append('call+' + str(n) + ('+comma' if a2 else '') + ('+dedup' if f2 else ''))

    assert_rows_present(lines, CM_SIG_ROWS[1:], CM, 'ChatMessage sig', 1)
    assert_rows_present(lines, CM_CALL_ROWS[1:], CM, 'ChatMessage call', 1)
    if not any(ln.strip() == AVATAR_IMP for ln in lines):
        fail(CM, 'Avatar import missing (strip-equal)')
    t = concat(lines)
    if balance(t) != bal0:
        fail(CM, 'balance changed ' + str(bal0) + '->' + str(balance(t)))
    for i, ln in enumerate(lines):
        if code_part(ln).endswith(',,'):
            fail(CM, 'double comma at L' + str(i + 1), dump_str(lines, i - 2, i + 3))
    sig_i = [i for i, ln in enumerate(lines) if ln.strip() == CM_SIG_ROWS[1]][0]
    call_i = [i for i, ln in enumerate(lines) if ln.strip() == CM_CALL_ROWS[1]][0]
    if sig_i > call_i:
        fail(CM, 'param inserted after call site')
    (ROOT / CM).write_text(t, encoding='utf-8')
    results.append('ChatMessage(' + ', '.join(applied) + ')')
    print('batch86b v7: ChatMessage OK (' + ', '.join(applied) + ')')

# =========================================================================
# Step5  ChatList.kt
# =========================================================================
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
cl = (ROOT / CL).read_text(encoding='utf-8')
if MARK in cl:
    print('batch86b v7: ChatList already applied')
else:
    # 铁律 33:转发行必须与签名声明一致(派生已保证,此处再显式校验一次)
    check_fwd_consistency(CL_SIG_ROWS, CL_FWD_ROWS, CL, 'pre')

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

    n, a, f = insert_before_close(lines, 'fun ChatList(', CL_SIG_ROWS, CL, 'ChatList sig')
    applied.append('ChatList-sig+' + str(n) + ('+comma' if a else '') + ('+dedup' if f else ''))
    n, a, f = insert_before_close(lines, 'ChatListNormal(', CL_FWD_ROWS, CL, 'ChatListNormal call')
    applied.append('forward1+' + str(n) + ('+comma' if a else '') + ('+dedup' if f else ''))
    n, a, f = insert_before_close(lines, 'private fun ChatListNormal(', CL_SIG_ROWS, CL, 'ChatListNormal sig')
    applied.append('ChatListNormal-sig+' + str(n) + ('+comma' if a else '') + ('+dedup' if f else ''))

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
        for ch in code_part(lines[i]):
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
    a, f = ensure_trailing_comma(lines, ci_close - 1)
    d = ind(lines[ci])
    for j, r in enumerate(CL_FWD_ROWS):
        lines.insert(ci_close + j, d + r)
    prev_code = code_part(lines[ci_close - 1])
    if not prev_code.endswith(','):
        fail(CL, 'forward2 prev code missing comma: ' + repr(prev_code),
             dump_str(lines, ci_close - 3, ci_close + 6))
    if prev_code.endswith(',,'):
        fail(CL, 'forward2 prev code double comma: ' + repr(prev_code),
             dump_str(lines, ci_close - 3, ci_close + 6))
    applied.append('forward2+3' + ('+comma' if a else '') + ('+dedup' if f else ''))

    assert_rows_present(lines, CL_SIG_ROWS[1:], CL, 'ChatList sig rows', 2)
    assert_rows_present(lines, CL_FWD_ROWS[1:], CL, 'ChatList fwd rows', 2)
    if not any(ln.strip() == AVATAR_IMP for ln in lines):
        fail(CL, 'Avatar import missing (strip-equal)')
    t = concat(lines)
    if balance(t) != bal0:
        fail(CL, 'balance changed ' + str(bal0) + '->' + str(balance(t)))
    for i, ln in enumerate(lines):
        if code_part(ln).endswith(',,'):
            fail(CL, 'double comma at L' + str(i + 1), dump_str(lines, i - 2, i + 3))
    (ROOT / CL).write_text(t, encoding='utf-8')
    results.append('ChatList(' + ', '.join(applied) + ')')
    print('batch86b v7: ChatList OK (' + ', '.join(applied) + ')')

print('batch86b v7: OK -> ' + ' | '.join(results))

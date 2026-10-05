#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
batch86b v6: Yuihub Step4-5 透传链 —— 修 #241 根因(注释感知的逗号检查)

=========== #241 验尸(dump 通道生效,拿到确切真值) ===========
失败: ChatMessage sig prev line missing comma:
      '    onQuote: (() -> Unit)? = null,, // rhQuoteMenu'
dump(L136-142):
      L137 onRerunTool: ...
      L138 onQuote: (() -> Unit)? = null,, // rhQuoteMenu      <-- 双逗号
      L139 // rhUserAvatarEdit: ...                            <-- 我的插入
      L140 onChangeUserAvatar: ((Avatar) -> Unit)? = null,

根因:ensure_trailing_comma 判断逗号时看的是【整行】(含 // 注释):
      s = '    onQuote: (() -> Unit)? = null, // rhQuoteMenu'
      if s.endswith(','):   -> False(整行以注释结尾,不是逗号!)
      => 误判"没逗号" -> 在注释前再插一个 ',' -> '= null,, // ...' 双逗号语法错
      位置断言同病:也只看整行 -> 断言失败(理由错但结果对)

=========== v6 修法(注释感知,结构性) ===========
新增 code_part(line):剥掉 `//` 注释后的 [:-].rstrip()
所有"逗号/链式行"判断一律基于 code_part,不再看整行:
  1. ensure_trailing_comma:code_part 已以 ',' 结尾 -> 不补
  2. 防御:code_part 若以 ',,' 结尾 -> 收敛为 ','
  3. 位置断言前一行:code_part 须以 ',' 结尾
  4. 链式续行判断:code_part 以 '.' 开头才算

=========== 五查(与前版一致) ===========
1. import:ChatMessage 锚 data.model.Assistant;ChatList 锚 data.model.Conversation
2. 同文件冲突:ChatMessage 被 66/68(引入 onQuote)、ChatList 被 69/71/77 碰过
   -> 全配平定位;本批只加可选参数
3. 作用域:ChatList 内 ChatMessage( 调用限定在 ChatListNormal 函数体(花括号配平)
4. 括号配对:插入自闭合行;补逗号不改配平;前后全文配平须相等
5. 函数签名:全部新增可选参数(默认 null)-> 现有调用点零破坏

=========== 铁律 ===========
25(插入前须确认插入点前一行有尾逗号——且必须是【代码部分】有)
29(配平相等 != 位置正确;须位置断言)
30(dump 必须塞 ::error message——本轮已验证有效)
31(失败路径显式 sys.exit(1))

=========== Python 三查 ===========
1. 引号一律变量构造 2. helper 先定义后用;无非法语法 3. 无 f-string/walrus/join
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
    print('::error file=' + path + '::batch86b v6 ' + body)
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
    '''剥掉 // 注释后的代码部分(已 rstrip)。所有逗号/链式判断都用它。'''
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
    '''注释感知:只看代码部分是否以 ',' 结尾;顺带收敛已有的 ',,'
       返回 (是否补了逗号, 是否收敛了双逗号)'''
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


results = []

# =========================================================================
# Step4  ChatMessage.kt
# =========================================================================
CM = 'app/src/main/java/me/rerere/rikkahub/ui/components/message/ChatMessage.kt'
cm = (ROOT / CM).read_text(encoding='utf-8')
if MARK in cm:
    print('batch86b v6: ChatMessage already applied')
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
    if ',, ' in t or ',\n' + NL + ' ' + ',' in t:
        # 粗检:全文不得出现 ',,'
        for i, ln in enumerate(lines):
            if code_part(ln).endswith(',,'):
                fail(CM, 'double comma at L' + str(i + 1), dump_str(lines, i - 2, i + 3))
    sig_i = [i for i, ln in enumerate(lines) if ln.strip() == CM_SIG_ROWS[1]][0]
    call_i = [i for i, ln in enumerate(lines) if ln.strip() == CM_CALL_ROWS[1]][0]
    if sig_i > call_i:
        fail(CM, 'param inserted after call site')
    (ROOT / CM).write_text(t, encoding='utf-8')
    results.append('ChatMessage(' + ', '.join(applied) + ')')
    print('batch86b v6: ChatMessage OK (' + ', '.join(applied) + ')')

# =========================================================================
# Step5  ChatList.kt
# =========================================================================
CL = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatList.kt'
cl = (ROOT / CL).read_text(encoding='utf-8')
if MARK in cl:
    print('batch86b v6: ChatList already applied')
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
    print('batch86b v6: ChatList OK (' + ', '.join(applied) + ')')

print('batch86b v6: OK -> ' + ' | '.join(results))

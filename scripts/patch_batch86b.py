#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
batch86b: Yuihub Step4-5 —— 用户信息透传链(高风险层)

Step4  ChatMessage.kt    +onChangeUserAvatar / onEditUserNickname 并透传给 ChatMessageUserAvatar
Step5  ChatList.kt       ChatList 与 ChatListNormal 两层签名 + 两处转发(共 4 处)

本步做完后链路: ChatPage(未写) -> ChatList -> ChatListNormal -> ChatMessage -> ChatMessageUserAvatar
                 (叶子层已在 batch86a 落地)

================================ 核心策略 =================================
【绝不用"最后一个参数"做锚】—— #216 教训:假设参数列表末尾会因前置 patch
改写签名而失配。本批改用【括号配平】定位签名闭合:
    1) 锚 `fun Xxx(` 行(行级 strip 全等)
    2) 从该行起做 paren-depth 扫描(先剥 `//` 行注释,防注释里的括号干扰)
    3) depth 首次归零处 = 参数列表闭合行 -> 在其【之前】插参数
这样无论 batch66/68/77 是否给签名加过参数,插入点恒正确。

================================ 五查 ===================================
1. import 清单(铁律20:行级 strip 全等 + 插入后回读断言)
   - ChatMessage.kt: 需 import me.rerere.rikkahub.data.model.Avatar
     ← 实读该文件 import 段有 me.rerere.rikkahub.data.model.Assistant
       (可作锚),无 Avatar;插入后回读
   - ChatList.kt: 同样需 Avatar;实读有 me.rerere.rikkahub.data.model.Conversation(可作锚)
2. 同文件冲突:
   - ChatMessage.kt 被 batch66/68 碰过 → 故签名锚【必须】用括号配平(不用行序)
   - ChatList.kt  被 batch69/71/77 碰过 → 同上;本批只加【可选参数】不改已有行,
     与那些补丁的改动区(签名末/调用末)按配平插入自然对齐,不覆盖
   - 两文件本批独占(无其他在链脚本与本批改同一行)
3. 作用域:全部在 @Composable 函数签名/调用实参区内
4. 括号配平:签名插入用配平定位;插入内容为 `name: Type = null,` 形式(自闭合);
   调用插入为 `name = name,` 形式;插入后全文括号配平必须与插入前一致
5. 函数签名:全部新增【可选参数(带默认 null)】→ 所有现有调用点零改动、零破坏

============================ Python 三查 ===============================
1. 无引号字面量问题:Q/SQ 变量拼接(本批文本里双引号出现在签名类型中,用 Q 构造)
2. 无未定义引用:所有函数(strip_comment/paren_close/concat/ind/fail)先定义后用
3. 无 f-string / walrus / join;无非法 for 语法(v1 教训:自检代码也要过三查)

========================== 铁律 28 检查 =================================
本批【不插入】 @Composable 函数块,只在已有函数的参数区与调用区加行
→ #232 的注解重复模式不适用。
'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhUserAvatarEdit'


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
    # 剥 // 行注释(URL 里的 // 也顺带剥,但那多在字符串里且不含未配对括号,安全)
    i = line.find('//')
    if i >= 0:
        return line[:i]
    return line


def paren_close(lines, start, tag):
    '''从 start 行(含 `fun Xxx(`)做 paren 深度扫描,返回 depth 首次归零的行号。
       归零处即参数列表闭合行;失败返回 -1。'''
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


def dump(lines, lo, hi, title):
    print('  dump ' + title + ':')
    for i in range(max(0, lo), min(hi, len(lines))):
        print('    >> ' + str(i) + ': ' + lines[i].strip()[:150])


def insert_before_close(lines, decl_anchor, new_rows, path, tag):
    '''锚 decl_anchor(strip 全等) → 配平找闭合 → 在闭合行前插入 new_rows
       返回 (插入行数, 闭合行号)'''
    hits = [i for i, ln in enumerate(lines) if ln.strip() == decl_anchor]
    if len(hits) != 1:
        dump(lines, 0, len(lines), decl_anchor)
        fail(path, tag + ' decl count=' + str(len(hits)))
    si = hits[0]
    close = paren_close(lines, si, tag)
    if close < 0:
        dump(lines, si, min(si + 40, len(lines)), tag + ' signature body')
        fail(path, tag + ' signature parens never balance')
    d = ind(lines[si])
    for j, r in enumerate(new_rows):
        lines.insert(close + j, d + r)
    return len(new_rows), close


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
    AVATAR_IMP = 'import me.rerere.rikkahub.data.model.Avatar'
    if not any(ln.strip() == AVATAR_IMP for ln in lines):
        hits = [i for i, ln in enumerate(lines) if ln.strip() == 'import me.rerere.rikkahub.data.model.Assistant']
        if len(hits) != 1:
            dump(lines, 0, 200, 'Assistant import')
            fail(CM, 'Assistant import anchor count=' + str(len(hits)))
        lines.insert(hits[0], AVATAR_IMP)
        if not any(ln.strip() == AVATAR_IMP for ln in lines):
            fail(CM, 'Avatar import read-back failed')
        applied.append('import-Avatar')

    # 4b. ChatMessage 签名 +2 可选参数(配平定位,不假设最后一个参数)
    n, close = insert_before_close(
        lines,
        'fun ChatMessage(',
        [
            '// ' + MARK + ': 点消息处头像/昵称分别弹改头像/改昵称(对话页为唯一编辑入口)',
            'onChangeUserAvatar: ((Avatar) -> Unit)? = null,',
            'onEditUserNickname: (() -> Unit)? = null,',
        ],
        CM, 'ChatMessage')
    applied.append('sig+' + str(n))

    # 4c. ChatMessageUserAvatar 调用处 +2 实参(配平定位)
    n, close = insert_before_close(
        lines,
        'ChatMessageUserAvatar(',
        [
            '// ' + MARK,
            'onChangeAvatar = onChangeUserAvatar,',
            'onEditNickname = onEditUserNickname,',
        ],
        CM, 'ChatMessageUserAvatar call')
    applied.append('call+' + str(n))

    # 自检
    t = concat(lines)
    for need in ['onChangeUserAvatar: ((Avatar) -> Unit)? = null',
                 'onEditUserNickname: (() -> Unit)? = null',
                 'onChangeAvatar = onChangeUserAvatar,',
                 'onEditNickname = onEditUserNickname,',
                 AVATAR_IMP]:
        if need not in t:
            fail(CM, 'selfcheck missing: ' + need)
    if not any(ln.strip() == AVATAR_IMP for ln in lines):
        fail(CM, 'Avatar import missing (strip-equal)')
    if balance(t) != bal0:
        fail(CM, 'bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(t)))
    # 防误插:两个新参数必须都在 ChatMessage 的参数区(即在 ChatMessageUserAvatar 调用之前)
    sig_line = [i for i, ln in enumerate(lines) if ln.strip() == 'onChangeUserAvatar: ((Avatar) -> Unit)? = null']
    call_line = [i for i, ln in enumerate(lines) if ln.strip() == 'onChangeAvatar = onChangeUserAvatar,']
    if len(sig_line) != 1 or len(call_line) != 1:
        fail(CM, 'sig/call line count wrong: sig=' + str(len(sig_line)) + ' call=' + str(len(call_line)))
    if sig_line[0] > call_line[0]:
        fail(CM, 'param inserted after call site (wrong position)')
    (ROOT / CM).write_text(t, encoding='utf-8')
    results.append('ChatMessage(' + ', '.join(applied) + ')')
    print('batch86b: ChatMessage OK (' + ', '.join(applied) + ')')

# =========================================================================
# Step5  ChatList.kt  —— 两层签名 + 两处转发
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
    AVATAR_IMP = 'import me.rerere.rikkahub.data.model.Avatar'
    if not any(ln.strip() == AVATAR_IMP for ln in lines):
        hits = [i for i, ln in enumerate(lines) if ln.strip() == 'import me.rerere.rikkahub.data.model.Conversation']
        if len(hits) != 1:
            dump(lines, 0, 200, 'Conversation import')
            fail(CL, 'Conversation import anchor count=' + str(len(hits)))
        lines.insert(hits[0], AVATAR_IMP)
        if not any(ln.strip() == AVATAR_IMP for ln in lines):
            fail(CL, 'Avatar import read-back failed')
        applied.append('import-Avatar')

    # 5b. ChatList 签名 +2
    n, _ = insert_before_close(
        lines, 'fun ChatList(',
        ['// ' + MARK, 'onChangeUserAvatar: ((Avatar) -> Unit)? = null,',
         'onEditUserNickname: (() -> Unit)? = null,'],
        CL, 'ChatList')
    applied.append('ChatList-sig+' + str(n))

    # 5c. ChatList -> ChatListNormal 调用转发 +2
    n, _ = insert_before_close(
        lines, 'ChatListNormal(',
        ['// ' + MARK, 'onChangeUserAvatar = onChangeUserAvatar,',
         'onEditUserNickname = onEditUserNickname,'],
        CL, 'ChatListNormal call')
    applied.append('forward1+' + str(n))

    # 5d. ChatListNormal 签名 +2(锚 private fun ChatListNormal()
    n, _ = insert_before_close(
        lines, 'private fun ChatListNormal(',
        ['// ' + MARK, 'onChangeUserAvatar: ((Avatar) -> Unit)? = null,',
         'onEditUserNickname: (() -> Unit)? = null,'],
        CL, 'ChatListNormal')
    applied.append('ChatListNormal-sig+' + str(n))

    # 5e. ChatListNormal -> ChatMessage 调用转发 +2
    #     该文件里 `ChatMessage(` 调用可能不止一处(ChatListPreview 也可能调)
    #     故限定在 ChatListNormal 函数体内:定位其起始,配平找整个函数体结束,
    #     在该区间内找 ChatMessage( 调用
    fn_hits = [i for i, ln in enumerate(lines) if ln.strip() == 'private fun ChatListNormal(']
    if len(fn_hits) != 1:
        dump(lines, 0, len(lines), 'private fun ChatListNormal(')
        fail(CL, 'ChatListNormal decl count=' + str(len(fn_hits)))
    fn_start = fn_hits[0]
    # 找函数体:从签名闭合继续配平花括号
    sig_close = paren_close(lines, fn_start, 'ChatListNormal')
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
        dump(lines, sig_close, min(sig_close + 40, len(lines)), 'ChatListNormal body end')
        fail(CL, 'ChatListNormal body never balances')

    inner = [i for i in range(sig_close, fn_end) if lines[i].strip() == 'ChatMessage(']
    if len(inner) != 1:
        dump(lines, sig_close, fn_end, 'ChatMessage( calls inside ChatListNormal')
        fail(CL, 'ChatMessage( call inside ChatListNormal count=' + str(len(inner)))
    ci = inner[0]
    ci_close = paren_close(lines, ci, 'ChatMessage call')
    if ci_close < 0 or ci_close > fn_end:
        fail(CL, 'ChatMessage call close not found within ChatListNormal body')
    d = ind(lines[ci])
    for j, r in enumerate([
        '// ' + MARK,
        'onChangeUserAvatar = onChangeUserAvatar,',
        'onEditUserNickname = onEditUserNickname,',
    ]):
        lines.insert(ci_close + j, d + r)
    applied.append('forward2+3')

    # 自检
    t = concat(lines)
    for need in ['onChangeUserAvatar: ((Avatar) -> Unit)? = null',
                 'onEditUserNickname: (() -> Unit)? = null',
                 'onChangeUserAvatar = onChangeUserAvatar,',
                 'onEditUserNickname = onEditUserNickname,',
                 AVATAR_IMP]:
        if need not in t:
            fail(CL, 'selfcheck missing: ' + need)
    # 两层签名各 1 次,两处转发各 1 次(= 各 2 次出现:签名 + 调用)
    if t.count('onChangeUserAvatar: ((Avatar) -> Unit)? = null,') != 2:
        fail(CL, 'param decl count != 2, got=' + str(t.count('onChangeUserAvatar: ((Avatar) -> Unit)? = null,')))
    if t.count('onChangeUserAvatar = onChangeUserAvatar,') != 2:
        fail(CL, 'forward count != 2, got=' + str(t.count('onChangeUserAvatar = onChangeUserAvatar,')))
    if not any(ln.strip() == AVATAR_IMP for ln in lines):
        fail(CL, 'Avatar import missing (strip-equal)')
    if balance(t) != bal0:
        fail(CL, 'bracket balance changed: ' + str(bal0) + ' -> ' + str(balance(t)))
    (ROOT / CL).write_text(t, encoding='utf-8')
    results.append('ChatList(' + ', '.join(applied) + ')')
    print('batch86b: ChatList OK (' + ', '.join(applied) + ')')

print('batch86b: OK -> ' + ' | '.join(results))

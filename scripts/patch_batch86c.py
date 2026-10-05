#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''
batch86c: Yuihub Step6 —— ChatPage.kt 用户信息编辑入口(昵称改名对话框 + 2 lambda)

作用:把「改昵称」入口从抽屉搬到对话页。点消息处自己的昵称 -> 弹改名框。
      (改头像走 ChatMessageAvatar 的 onUpdate,已在 batch86a 落地)

=========== 实读证据(全部亲自读过,非记忆) ===========
1. ChatPage.kt import 段【已有】:
     import me.rerere.rikkahub.ui.hooks.EditStateContent
     import me.rerere.rikkahub.ui.hooks.useEditState
   => 零 import 新增(避免 #230 前缀误命中风险)
2. ChatVM.updateSettings(newSettings: Settings): Job —— 搜索命中确认存在
3. ChatPage.kt 结构:
     fun ChatPage(...)                 <- 读 settings/conversation/...
     private fun ChatPageContent(setting: Settings, ...)   <- 承载下面这些
         var previewMode by rememberSaveable { mutableStateOf(false) }   <- 局部状态区
         val assistant = setting.getCurrentAssistant()
         ...
         ChatList(                      <- 缩进 12
             innerPadding = innerPadding,
             ...
             onConversationSystemPromptChange = { newPrompt -> ... },   <- 末参数
         )
4. 变量名是 setting(不是 settings) —— 见 ChatPageContent 形参
5. 现成的 EditStateContent 用例模式(抽屉里 folderToRename 等)已实读

=========== 五查 ===========
1. import:零新增(useEditState/EditStateContent 已在;AlertDialog/OutlinedTextField/
   TextButton/Text 均已在 ChatPage import 段实读确认)
2. 同文件冲突:ChatPage.kt 被 batch62/63/70/72/80v6/82 碰过 ->
   本批锚点用【unique 状态行】(previewMode 声明)与【ChatList( 调用 + 配平闭合】,
   不与那些补丁的改动行重叠
3. 作用域:状态与对话框插入在 private fun ChatPageContent 函数体内;
   lambda 插入在 ChatList( 的实参区内(配平定位)
4. 括号配对:插入 2 行声明(自闭合);对话框块多行需自平衡(已逐行核对);
   插入后全文配平必须与插入前一致
5. 函数签名:不改任何签名;ChatList 调用新增 2 个【具名实参】

=========== 铁律 25/29 落实 ===========
- 插入 ChatList 实参前,调 ensure_trailing_comma 确保前一行以 ',' 结尾
  (前一行是 onConversationSystemPromptChange = {...}, 已以 ',' 结尾,应无需补)
- 位置断言:前一行以 ',' 结尾 / 插入区无 '.' 续行 / 插入后 3 行内见 ')' /
  插入行必须位于 `ChatList(` 之后
- dump 一律塞 ::error message(铁律 30)
- 失败显式 sys.exit(1)(铁律 31)

=========== Python 三查 ===========
1. 引号一律 Q=chr(34) 构造(块内含 " 与 ' 的地方都走变量)
2. helper 全部先定义后用;无非法语法
3. 无 f-string / walrus / join
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhUserInfoEdit'

CP = 'app/src/main/java/me/rerere/rikkahub/ui/pages/chat/ChatPage.kt'


def fail(msg, dump_text=''):
    body = str(msg)[:800]
    if dump_text:
        body = body + ' || DUMP: ' + str(dump_text)[:1500]
    print('::error file=' + CP + '::batch86c ' + body)
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


text = (ROOT / CP).read_text(encoding='utf-8')
if MARK in text:
    print('batch86c: already applied')
    sys.exit(0)

lines = text.split(NL)
bal0 = balance(text)
applied = []

# -------------------------------------------------------------------------
# 1. 昵称编辑状态 —— 插在 ChatPageContent 里预览模式状态行之前(锚唯一)
# -------------------------------------------------------------------------
STATE_ANCHOR = 'var previewMode by rememberSaveable { mutableStateOf(false) }'
hits = [i for i, ln in enumerate(lines) if ln.strip() == STATE_ANCHOR]
if len(hits) != 1:
    fail('previewMode state anchor count=' + str(len(hits)), dump_str(lines, 0, len(lines)))
si = hits[0]
d = ind(lines[si])
state_block = [
    '// ' + MARK + ': 用户昵称编辑状态(对话页为唯一编辑入口)',
    'val nicknameEditState = useEditState<String> { newNickname ->',
    '    vm.updateSettings(',
    '        setting.copy(',
    '            displaySetting = setting.displaySetting.copy(userNickname = newNickname)',
    '        )',
    '    )',
    '}',
    '',
]
for j, b in enumerate(state_block):
    lines.insert(si + j, d + b)
applied.append('state')

# -------------------------------------------------------------------------
# 2. ChatList 调用 +2 具名实参(配平定位 + 尾逗号前置条件 + 位置断言)
# -------------------------------------------------------------------------
cl_hits = [i for i, ln in enumerate(lines) if ln.strip() == 'ChatList(']
if len(cl_hits) != 1:
    fail('ChatList( anchor count=' + str(len(cl_hits)), dump_str(lines, 0, len(lines)))
ci = cl_hits[0]
close = paren_close(lines, ci)
if close < 0:
    fail('ChatList( parens never balance', dump_str(lines, ci, ci + 60))
if close <= ci:
    fail('ChatList close<=start ' + str(close) + '<=' + str(ci))

comma = ensure_trailing_comma(lines, close - 1)
d = ind(lines[ci])
args = [
    '// ' + MARK,
    'onChangeUserAvatar = { newAvatar ->',
    '    vm.updateSettings(',
    '        setting.copy(',
    '            displaySetting = setting.displaySetting.copy(userAvatar = newAvatar)',
    '        )',
    '    )',
    '},',
    'onEditUserNickname = {',
    '    nicknameEditState.open(setting.displaySetting.userNickname)',
    '},',
]
for j, r in enumerate(args):
    lines.insert(close + j, d + r)

# 位置断言(铁律 29)
if not lines[close - 1].rstrip().endswith(','):
    fail('ChatList prev line missing comma: ' + repr(lines[close - 1].rstrip()),
         dump_str(lines, close - 3, close + 14))
if any(ln.strip().startswith('.') for ln in lines[close:close + len(args)]):
    fail('inserted region has chained-dot line', dump_str(lines, close - 3, close + 14))
found = False
for i in range(close + len(args), min(close + len(args) + 4, len(lines))):
    st = lines[i].strip()
    if st == ')' or st.startswith('),'):
        found = True
        break
if not found:
    fail('no closing paren within 4 lines after ChatList insert',
         dump_str(lines, ci, min(close + len(args) + 6, len(lines))))
applied.append('args' + ('+comma' if comma else ''))

# -------------------------------------------------------------------------
# 3. 昵称改名对话框 —— 插在 ChatList(...) 整个调用之后
#    (关闭行 close + len(args) 即 ')';在其后插入对话框)
# -------------------------------------------------------------------------
dlg_ins = close + len(args) + 1
if dlg_ins > len(lines):
    fail('dialog insert index out of range')
d = ind(lines[si])
dialog_block = [
    '',
    '// ' + MARK + ': 昵称编辑对话框(从抽屉搬到对话页)',
    'nicknameEditState.EditStateContent { nickname, onUpdate ->',
    '    AlertDialog(',
    '        onDismissRequest = { nicknameEditState.dismiss() },',
    '        title = { Text(stringResource(R.string.chat_page_edit_nickname)) },',
    '        text = {',
    '            OutlinedTextField(',
    '                value = nickname,',
    '                onValueChange = onUpdate,',
    '                modifier = Modifier.fillMaxWidth(),',
    '                singleLine = true,',
    '                placeholder = { Text(stringResource(R.string.chat_page_nickname_placeholder)) },',
    '            )',
    '        },',
    '        confirmButton = {',
    '            TextButton(',
    '                onClick = {',
    '                    nicknameEditState.confirm()',
    '                },',
    '                enabled = nickname.isNotBlank(),',
    "            ) { Text(stringResource(R.string.chat_page_save)) }",
    '        },',
    '        dismissButton = {',
    '            TextButton(onClick = { nicknameEditState.dismiss() }) {',
    '                Text(stringResource(R.string.chat_page_cancel))',
    '            }',
    '        },',
    '    )',
    '}',
]
for j, b in enumerate(dialog_block):
    lines.insert(dlg_ins + j, d + b)
applied.append('dialog')

# -------------------------------------------------------------------------
# 自检
# -------------------------------------------------------------------------
t2 = concat(lines)
for need in [MARK,
             'val nicknameEditState = useEditState<String> { newNickname ->',
             'onChangeUserAvatar = { newAvatar ->',
             'onEditUserNickname = {',
             'nicknameEditState.EditStateContent { nickname, onUpdate ->',
             'nicknameEditState.confirm()']:
    if need not in t2:
        fail('selfcheck missing: ' + need, dump_str(lines, 0, len(lines)))
if balance(t2) != bal0:
    fail('balance changed ' + str(bal0) + ' -> ' + str(balance(t2)))
# 位置断言:状态行必须早于 ChatList 调用
st_i = [i for i, ln in enumerate(lines) if ln.strip().startswith('val nicknameEditState')][0]
cl_i = [i for i, ln in enumerate(lines) if ln.strip() == 'ChatList('][0]
if st_i > cl_i:
    fail('state declared after ChatList call')
(ROOT / CP).write_text(t2, encoding='utf-8')
print('batch86c: OK (' + ', '.join(applied) + ')')

#!/usr/bin/env python3
'''batch89: 覆盖恢复崩溃修复 —— alreadyCurrent 判定不得要求 fork 独有列

根因(logcat 实证):覆盖恢复后重启崩溃,
  SQLiteException: duplicate column name: custom_system_prompt
  ALTER TABLE `ConversationEntity` ADD COLUMN `custom_system_prompt` ...
即 Room 把已是最新列的文件当成旧版本,重放 24->25 migration 撞已有列。

为什么没 stamp:reconcileDatabaseFile 的 alreadyCurrent 判定是
  isCurrentSharedSchema(sentinel) && REQUIRED_CONVERSATION_COLUMNS.all(...)
而 REQUIRED 含 chat_model_id —— 这是 fork v30 才加的列,官方/老备份没有。
于是 alreadyCurrent=false,不 stamp user_version,文件停在 v24,重启迁移撞列。
合并正常是因为 merge 不 stamp、也不让 Room 迁移 staged 文件,只逐条 INSERT。

修法:alreadyCurrent 判定的 REQUIRED 部分排除 fork 独有列(只看官方会有的列),
fork 独有的 chat_model_id 由 alreadyCurrent 分支里已有的补列逻辑负责补。
新增 FORK_ONLY_CONVERSATION_COLUMNS 常量,REQUIRED 仍被引用(避免 unused)。

五查:
1. import 清单:无新增 import
2. 同文件冲突:ImportedDatabaseReconciler.kt 冷门,无在链 patch 碰过
3. 作用域:常量插在 object 内与 REQUIRED 同级;判定在 reconcileDatabaseFile 函数内
4. 括号配对:setOf(...) 配平;(REQUIRED - FORK_ONLY).all(...) 配平
5. 函数签名:不改任何签名

Python 三查:双引号仅在 Python 单引号字符串内 / 无未定义引用 / 无 f-string / 无 join
锚点按仓库形态(此文件无在链 patch 修改),找不到即 fail-loud + dump 现场行。
'''
from pathlib import Path

NL = chr(10)
MARK = 'batch89FixAlreadyCurrent'
ROOT = Path.cwd()
F = 'app/src/main/java/me/rerere/rikkahub/data/db/ImportedDatabaseReconciler.kt'


def fail(msg, lines=None, around=-1):
    s = 'batch89 ' + str(msg)
    if lines is not None and 0 <= around < len(lines):
        lo = max(0, around - 3)
        hi = min(len(lines), around + 4)
        ctx = NL.join(str(i) + ': ' + lines[i] for i in range(lo, hi))
        s = s + ' || ctx: ' + ctx
    print('::error file=' + F + '::' + s[:1400])
    raise SystemExit(1)


text = (ROOT / F).read_text(encoding='utf-8')
if MARK in text:
    print('batch89: already applied, skip')
    raise SystemExit(0)
lines = text.split(NL)

# --- edit 1: 在 REQUIRED_CONVERSATION_COLUMNS 定义后插入 FORK_ONLY 常量 ---
anchor1 = -1
for i, line in enumerate(lines):
    if 'lorebook_ids' in line and 'chat_model_id' in line and line.strip().endswith(','):
        if anchor1 >= 0:
            fail('ambiguous REQUIRED set last-element line', lines, i)
        anchor1 = i
if anchor1 < 0:
    fail('REQUIRED set last-element line not found', lines, 0)
if lines[anchor1 + 1].strip() != ')':
    fail('REQUIRED set closing paren not where expected', lines, anchor1 + 1)
insert_at = anchor1 + 2
new_const = [
    '',
    '    // ' + MARK + ': columns the fork adds on top of any upstream schema.',
    '    // An upstream v24 file legitimately lacks chat_model_id, so it must be',
    '    // backfilled by the alreadyCurrent branch below, not required up front.',
    '    private val FORK_ONLY_CONVERSATION_COLUMNS = setOf("chat_model_id")',
]
lines[insert_at:insert_at] = new_const

# --- edit 2: alreadyCurrent 判定排除 fork 独有列 ---
anchor2 = -1
for i, line in enumerate(lines):
    if line.strip() == 'isCurrentSharedSchema(conversationColumns) &&':
        if anchor2 >= 0:
            fail('ambiguous isCurrentSharedSchema call', lines, i)
        anchor2 = i
if anchor2 < 0:
    fail('isCurrentSharedSchema(conversationColumns) && not found', lines, 0)
idx_req = anchor2 + 1
if idx_req >= len(lines) or lines[idx_req].strip() != 'REQUIRED_CONVERSATION_COLUMNS.all(conversationColumns::contains)':
    fail('REQUIRED.all not immediately after isCurrentSharedSchema', lines, min(idx_req, len(lines) - 1))
indent = lines[idx_req][:len(lines[idx_req]) - len(lines[idx_req].lstrip())]
lines[idx_req] = indent + '(REQUIRED_CONVERSATION_COLUMNS - FORK_ONLY_CONVERSATION_COLUMNS).all(conversationColumns::contains) // ' + MARK

# --- 自检 ---
new_text = NL.join(lines)
if 'FORK_ONLY_CONVERSATION_COLUMNS = setOf("chat_model_id")' not in new_text:
    fail('FORK_ONLY constant missing after edit')
if '(REQUIRED_CONVERSATION_COLUMNS - FORK_ONLY_CONVERSATION_COLUMNS)' not in new_text:
    fail('relaxed judgement missing after edit')
(ROOT / F).write_text(new_text, encoding='utf-8')
print('batch89: OK - alreadyCurrent no longer gated on fork-only chat_model_id')

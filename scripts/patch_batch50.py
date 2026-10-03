#!/usr/bin/env python3
'''batch50: 上游易做项合组 A（77a58c2c 统计页崩溃修复，唯一入选项）

计划文档：workspace《上游移植-易做项计划.md》。取证结论：
- A(77a58c2c, 2.5.1): json_each() 遇到损坏行导致整个统计查询失败 →
  用 CASE json_valid() 把无效 JSON 当空数组。fork 与上游基准一致，
  且 fork 自有 USAGE_SUMMARY_SQL 也有同样的裸 json_each(mn.messages) ——
  同修 3 处（上游只修了 2 处）。
- B(4391d5a5): 剔除——fork 的 sanitizeForGeminiSchema 已是白名单架构，
  propertyNames 已被自动过滤，无对应锚点（黑名单路径在 fork 不存在）。

锚点来源：fork MessageNodeDAO.kt 0-5500 字节逐字节读取（2026-10-03）。
铁律执行：零反斜杠（chr(10)+三引号）；自检断言新内容在场+旧裸调用消失。
'''
from pathlib import Path

ROOT = Path.cwd()
DAO = 'app/src/main/java/me/rerere/rikkahub/data/db/dao/MessageNodeDAO.kt'
NL = chr(10)
MARK = 'rhDaoStatsFix'

BARE = 'json_each(mn.messages)'


def fail(msg):
    print('::error file=' + DAO + '::batch50 ' + str(msg)[:1500])
    raise SystemExit(1)


t = (ROOT / DAO).read_text(encoding='utf-8')
if MARK in t:
    print('batch50: already applied')
    raise SystemExit(0)

# --- 1. 定义 VALID 常量（插在 TOKEN_STATS_SQL 前，锚点=注释行已验证）---
ANCHOR_CONST = ('// SQLite json_each() 展开 messages JSON 数组，json_extract() 提取 Token 字段并聚合' + NL +
                'private val TOKEN_STATS_SQL = SimpleSQLiteQuery(')
CONST_BLOCK = (
    '// ' + MARK + ' (upstream 77a58c2c): 在 json_each() 参数内校验 JSON，损坏行按空数组处理，' + NL +
    '// 避免一行坏数据炸掉整个统计查询。使用 CASE 而非依赖 WHERE 求值顺序。' + NL +
    'private const val VALID_MESSAGES_JSON = "CASE WHEN json_valid(mn.messages) THEN mn.messages ELSE ' + "'[]'" + ' END"' + NL +
    NL
)
if ANCHOR_CONST not in t:
    fail('const insertion anchor not found')
t = t.replace(ANCHOR_CONST, CONST_BLOCK + ANCHOR_CONST, 1)

# --- 2. 三处裸调用替换（TOKEN_STATS / countPerDay / USAGE_SUMMARY）---
n = t.count(BARE)
if n != 3:
    fail('expect 3 bare json_each calls, found ' + str(n))
t = t.replace(BARE, 'json_each(' + '$' + 'VALID_MESSAGES_JSON)')

# --- 3. 自检：新内容在场 + 裸调用消失 ---
for need in [MARK, 'VALID_MESSAGES_JSON', 'json_valid(mn.messages)']:
    if need not in t:
        fail('selfcheck missing: ' + need)
if BARE in t:
    fail('selfcheck: bare json_each(mn.messages) must be gone (found ' +
         str(t.count(BARE)) + ')')
if t.count('json_each(' + '$' + 'VALID_MESSAGES_JSON)') != 3:
    fail('selfcheck: expect 3 wrapped calls, found ' +
         str(t.count('json_each(' + '$' + 'VALID_MESSAGES_JSON)')))

(ROOT / DAO).write_text(t, encoding='utf-8')
print('batch50: OK (3 json_each sites wrapped with json_valid CASE)')

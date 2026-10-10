#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch141 v2: ImportedDatabaseReconciler 跟上 v36 workspace schema（shell 列回归后）

v2 修复: v1 的 expressions 锚点引号构造漏了一层——Kotlin 代码里
  column == "tool_approvals" -> "'{}'"
是【双引号+单引号+{}+单引号+双引号】结构, 我构造时丢了外层双引号。
同样 shell_status 新分支也应是 -> "'DISABLED'" (双引号包单引号)。
v2 修正 OLD_EX / NEW_EX 的引号构造。其余不变。

背景：shell 恢复后 workspaces 表从 7 列变成 9 列（+shell_status +shell_compatibility_mode）。
Reconciler 是裁剪版时代写的，它的“当前 workspace schema”判定写死了“绝不能有 shell_status”，
并且 createWorkspaceTable / rebuildWorkspaceTable 建的还是 7 列表。

当前流程不会出事（v36 备份 version>34 在入口就被 untouched 放行），
但这个判定一旦将来被触发就会把 shell 列删掉 —— 定时炸弹，趁现在拆掉。

改动（单文件 ImportedDatabaseReconciler.kt，4 处）：
1. isCurrentWorkspaceSchema: 去掉 && "shell_status" !in columns（允许 shell 列存在）
2. CURRENT_WORKSPACE_COLUMNS 上方注释更新
3. createWorkspaceTable 与 rebuildWorkspaceTable 的 CREATE TABLE 各加 2 列
4. rebuildWorkspaceTable 的 targetColumns 加 2 列 + expressions 加 2 个默认值分支

EXPECTED_VERSION 不动：它停在 34 是合理的（stamp 后由 Room 迁移链 34->35->36 补齐）。

五查:
1. import 清单: 无新增
2. 同文件冲突: 本文件在链 patch 只有 batch89（改 FORK_ONLY 与 alreadyCurrent 行），区域不相交
3. 作用域: object 内修改
4. 括号配对: 插入行自平衡；全文 balance 前后一致
5. 函数签名: 不改签名

Python 三查: 引号用 Q/SQ/BQ 构造且同一字面量只拼一次; NL 手写 concat 禁 f-string; helper 先定义后用, 失败显式 exit(1)+::error
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
SQ = chr(39)
BQ = chr(96)
MARK = 'rhReconcilerShellCols'
F = 'app/src/main/java/me/rerere/rikkahub/data/db/ImportedDatabaseReconciler.kt'


def fail(msg):
    print('::error file=' + F + '::batch141 ' + str(msg)[:1400])
    sys.stdout.flush()
    sys.exit(1)


def balance(text):
    return text.count('(') - text.count(')') + (text.count('{') - text.count('}'))


t = (ROOT / F).read_text(encoding='utf-8')
if MARK in t:
    print('batch141: already applied')
    sys.exit(0)

bal0 = balance(t)

# ---- 1. isCurrentWorkspaceSchema 判定放宽 ----
OLD_JUDGE = '    internal fun isCurrentWorkspaceSchema(columns: Set<String>): Boolean =' + NL + '        CURRENT_WORKSPACE_COLUMNS.all(columns::contains) && ' + Q + 'shell_status' + Q + ' !in columns'
NEW_JUDGE = '    // ' + MARK + ': shell 列(v36+)允许存在; 判定只看 7 个基础列是否齐全' + NL + '    internal fun isCurrentWorkspaceSchema(columns: Set<String>): Boolean =' + NL + '        CURRENT_WORKSPACE_COLUMNS.all(columns::contains)'
if OLD_JUDGE not in t:
    fail('judge anchor not found')
if t.count(OLD_JUDGE) != 1:
    fail('judge anchor not unique')
t = t.replace(OLD_JUDGE, NEW_JUDGE, 1)

# ---- 2. CURRENT_WORKSPACE_COLUMNS 注释更新 ----
OLD_CMT = '/** The current slim workspace table: the removed shell_status column must never be present. */'
NEW_CMT = '/** The workspace table base columns. shell_status / shell_compatibility_mode (v36+) may also be present. */'
if OLD_CMT not in t:
    fail('comment anchor not found')
t = t.replace(OLD_CMT, NEW_CMT, 1)

# ---- 3. 两个 CREATE TABLE 各加 2 列（tool_approvals 行后，共 2 处） ----
TA_LINE = '                ' + BQ + 'tool_approvals' + BQ + ' TEXT NOT NULL DEFAULT ' + SQ + '{}' + SQ + ','
ADD_LINES = (
    '                ' + BQ + 'shell_status' + BQ + ' TEXT NOT NULL DEFAULT ' + SQ + 'DISABLED' + SQ + ',' + NL +
    '                ' + BQ + 'shell_compatibility_mode' + BQ + ' INTEGER NOT NULL DEFAULT 0,'
)
hits = t.count(TA_LINE)
if hits != 2:
    fail('tool_approvals DDL anchor count=' + str(hits) + ' (expected 2: createWorkspaceTable + rebuildWorkspaceTable)')
t = t.replace(TA_LINE, TA_LINE + NL + ADD_LINES)

# ---- 4. rebuild 的 targetColumns + expressions ----
OLD_TC = '    val targetColumns = listOf(' + Q + 'id' + Q + ', ' + Q + 'name' + Q + ', ' + Q + 'root' + Q + ', ' + Q + 'created_at' + Q + ', ' + Q + 'updated_at' + Q + ', ' + Q + 'last_access_at' + Q + ', ' + Q + 'tool_approvals' + Q + ')'
NEW_TC = '    val targetColumns = listOf(' + Q + 'id' + Q + ', ' + Q + 'name' + Q + ', ' + Q + 'root' + Q + ', ' + Q + 'created_at' + Q + ', ' + Q + 'updated_at' + Q + ', ' + Q + 'last_access_at' + Q + ', ' + Q + 'tool_approvals' + Q + ', ' + Q + 'shell_status' + Q + ', ' + Q + 'shell_compatibility_mode' + Q + ')'
if OLD_TC not in t:
    fail('targetColumns anchor not found')
t = t.replace(OLD_TC, NEW_TC, 1)

# Kotlin 代码: column == "tool_approvals" -> "'{}'"  (双引号包单引号包内容)
OLD_EX = '            column == ' + Q + 'tool_approvals' + Q + ' -> ' + Q + SQ + '{}' + SQ + Q
NEW_EX = (
    OLD_EX + NL +
    '            column == ' + Q + 'shell_status' + Q + ' -> ' + Q + SQ + 'DISABLED' + SQ + Q + NL +
    '            column == ' + Q + 'shell_compatibility_mode' + Q + ' -> ' + Q + '0' + Q
)
if OLD_EX not in t:
    fail('expressions anchor not found')
if t.count(OLD_EX) != 1:
    fail('expressions anchor not unique')
t = t.replace(OLD_EX, NEW_EX, 1)

# ---- 自检 ----
if (Q + 'shell_status' + Q + ' !in columns') in t:
    fail('old judge still present')
if t.count(BQ + 'shell_status' + BQ + ' TEXT NOT NULL DEFAULT') != 2:
    fail('shell_status DDL count != 2')
if t.count(BQ + 'shell_compatibility_mode' + BQ + ' INTEGER NOT NULL DEFAULT 0') != 2:
    fail('shell_compatibility_mode DDL count != 2')
if NEW_TC not in t:
    fail('targetColumns not updated')
if ('column == ' + Q + 'shell_compatibility_mode' + Q + ' -> ' + Q + '0' + Q) not in t:
    fail('expressions branch missing')
if ('column == ' + Q + 'shell_status' + Q + ' -> ' + Q + SQ + 'DISABLED' + SQ + Q) not in t:
    fail('shell_status expressions branch missing')
if balance(t) != bal0:
    fail('balance changed')

(ROOT / F).write_text(t, encoding='utf-8')
print('::notice::batch141 v2 OK - reconciler accepts shell columns (judge relaxed, DDL 9 cols, rebuild keeps shell cols)')

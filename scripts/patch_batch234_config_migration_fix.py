#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch234: P0 崩溃修复 —— 补 ConversationEntity.config 列的迁移

崩溃报告(用户装机 run444 启动即崩, 安全模式):
  IllegalStateException: Migration didn't properly handle: ConversationEntity
  Expected: 有 config 列(TEXT NOT NULL DEFAULT '')
  Found:    没有 config 列

根因(CI 真形态≠仓库态 铁律的典型案例):
  并行会话 A2(batch230_conversation_config_db)给 ConversationEntity 加了 config 列,
  其迁移写法基于仓库态锚点 `version = 34` → `version = 35` + AutoMigration(34,35)。
  但 CI 形态早已被 batch55_1/133 提到 36 → version 锚点失配 → A2 的 db 部分静默 skip
  (warn-only 吞掉)。结果: 实体定义有 config 列, 迁移链没有任何一步加 config。
  用户手机 run402 装机时 DB=v36(无 config), 装 run444 → Room 校验 v37 实体 vs 实际表
  → config 缺失 → 崩溃。
  (编译绿是因为编译只查语法不验证迁移链完整性; AutoMigration(34,35)从未进代码,
  否则 Room 编译会报与手写 Migration_34_35 的冲突——run444 编译绿反证它不存在。)

修复: 在 Migration_36_37(我 batch230 v3 加的, 覆盖用户实际 v36→v37 路径)的 migrate 里
  补上 config 列。所有设备的 conversationentity 均无 config(AutoMigration 从未生效),
  直接 ADD COLUMN 不会 duplicate。用户当前崩溃设备 DB 是事务回滚后的干净 v36, 修复版
  装上即正常迁移, 数据不丢。

五查:
1. import 清单: 无新 import(只用已有 SupportSQLiteDatabase)
2. 同文件冲突: AppDatabase.kt 被我(230 v3 加了 Migration_36_37)和并行(A2 动 version/
   autoMigrations 但 skip 未生效)都碰过; 我的锚点在 Migration_36_37 类内, 与 A2 区域不相交
3. 作用域: migrate 函数体内加一行 execSQL
4. 括号配对: 插入行自平衡; 全文 balance 前后一致
5. 函数签名: 不变

Python 三查: Q/NL 变量构造; 无 f-string/join/walrus; fail-loud + ::error
'''
import sys
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
Q = chr(34)
MARK = 'rhConfigMig234'
F = 'app/src/main/java/me/rerere/rikkahub/data/db/AppDatabase.kt'


def fail(msg):
    print('::error::batch234 ' + str(msg)[:1400])
    sys.stdout.flush()
    sys.exit(1)


def balance(text):
    return (text.count('(') - text.count(')')
            + text.count('{') - text.count('}')
            + text.count('[') - text.count(']'))


def main():
    p = ROOT / F
    if not p.exists():
        fail('AppDatabase.kt missing')
    t = p.read_text(encoding='utf-8')
    if MARK in t:
        print('batch234: already applied')
        sys.exit(0)
    bal0 = balance(t)

    # 锚点: Migration_36_37 的 memoryentity execSQL 行(我 230 v3 写的, 全文唯一)
    old = ('        db.execSQL(' + Q + 'ALTER TABLE memoryentity ADD COLUMN conversation_id TEXT NOT NULL DEFAULT ' + chr(39) + chr(39) + Q + ')' + NL
           + '    }' + NL
           + '}')
    new = ('        db.execSQL(' + Q + 'ALTER TABLE memoryentity ADD COLUMN conversation_id TEXT NOT NULL DEFAULT ' + chr(39) + chr(39) + Q + ')' + NL
           + '        // ' + MARK + ': A2(batch230_conversation_config_db) 的 config 列迁移(AutoMigration 34->35)' + NL
           + '        // 因 version 锚点(仓库态34 vs CI态36)失配被静默 skip, 实体有 config 列而迁移链没有,' + NL
           + '        // v36 设备升级 v37 时 Room 校验崩溃。所有设备均无 config(AutoMigration 从未生效), 直接加列。' + NL
           + '        db.execSQL(' + Q + 'ALTER TABLE conversationentity ADD COLUMN config TEXT NOT NULL DEFAULT ' + chr(39) + chr(39) + Q + ')' + NL
           + '    }' + NL
           + '}')
    n = t.count(old)
    if n != 1:
        fail('anchor count=' + str(n) + ' (expected 1)')
    t = t.replace(old, new, 1)

    if balance(t) != bal0:
        fail('balance changed')
    if t.count('ADD COLUMN config') != 1:
        fail('config ALTER missing after write')
    p.write_text(t, encoding='utf-8')
    print('::notice::batch234 OK - config column added to Migration_36_37 (v36->v37 crash fix)')


main()

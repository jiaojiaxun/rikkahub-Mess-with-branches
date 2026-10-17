#!/usr/bin/env python3
# -*- coding: utf-8 -*-
'''batch230: A2 —— ConversationConfig 落库（DB 列 + 迁移 34→35 + 仓储编解码）

A 移植第二批。A1(batch229) 只加了内存态数据类, 没落库。本批让它持久化:
  1. ConversationEntity.kt: 加 `config` TEXT 列(存 ConversationConfig 的 JSON),
     锚点 `val chatModelId: String = "",` 之后。
  2. AppDatabase.kt: version 34→35 + autoMigrations 加 AutoMigration(34, 35)
     (纯加列带 defaultValue, Room 自动生成 ALTER TABLE; 35.json 由 ksp 编译期生成)。
  3. ConversationRepository.kt: 实体↔领域双向映射
     conversationToConversationEntity 加 config=encodeConversationConfig(...),
     conversationEntityToConversation 加 config=decodeConversationConfig(...),
     末尾追加 encode/decodeConversationConfig 两个顶层函数,
     import 加 me.rerere.rikkahub.data.model.ConversationConfig(精确行插在 Conversation import 后)。

注意: 合并/备份的 MergeDecisionApplier 手写 ContentValues 列清单, 本批不含 config ——
  合并时 config 不落库(留待后续批次), 不崩不丢, 只是合并不带它。

幂等 marker rhConversationConfigDb; 三文件锚点均要求唯一; warn-only; 括号差值断言。
'''
from pathlib import Path
import sys

ROOT = Path.cwd()
NL = chr(10)
BATCH = 'batch230'
MARK = 'rhConversationConfigDb'

ENT = 'app/src/main/java/me/rerere/rikkahub/data/db/entity/ConversationEntity.kt'
DB = 'app/src/main/java/me/rerere/rikkahub/data/db/AppDatabase.kt'
REPO = 'app/src/main/java/me/rerere/rikkahub/data/repository/ConversationRepository.kt'

HELPERS = NL + NL + '''/** [batch230] 会话级固定配置的编解码: ConversationConfig? ↔ config 列的 JSON 字符串。 */
internal fun encodeConversationConfig(config: ConversationConfig?): String =
    config?.let { JsonInstant.encodeToString(it) } ?: ""

internal fun decodeConversationConfig(stored: String): ConversationConfig? =
    if (stored.isBlank()) null
    else runCatching { JsonInstant.decodeFromString<ConversationConfig>(stored) }.getOrNull()
'''

applied = []
skipped = []


def joinlist(items):
    t = ''
    for i, s in enumerate(items):
        if i > 0:
            t += ','
        t += s
    return t


def read(path):
    p = ROOT / path
    if not p.exists():
        return None
    try:
        return p.read_text(encoding='utf-8')
    except Exception:
        return None


def write(path, text):
    p = ROOT / path
    if not p.parent.exists():
        p.parent.mkdir(parents=True)
    p.write_text(text, encoding='utf-8')


def balance(text):
    return (text.count('(') - text.count(')')) + (text.count('{') - text.count('}'))


def replace_once(src, old, new, tag):
    n = src.count(old)
    if n != 1:
        skipped.append(tag + '-count=' + str(n))
        return None
    return src.replace(old, new, 1)


def main():
    # ======== 1. ConversationEntity: 加 config 列 ========
    ent = read(ENT)
    if ent is None:
        skipped.append('ent-missing')
        print('::error::' + BATCH + ' SKIP ent missing')
        return
    if MARK not in ent:
        old = '''    @ColumnInfo("chat_model_id", defaultValue = "")
    val chatModelId: String = "",'''
        new = old + NL + '''    @ColumnInfo("config", defaultValue = "")
    val config: String = "", // ''' + MARK
        out = replace_once(ent, old, new, 'ent')
        if out is None:
            print('::error::' + BATCH + ' SKIP ent anchor')
            return
        if balance(out) != balance(ent):
            skipped.append('ent-balance')
            print('::error::' + BATCH + ' SKIP ent balance')
            return
        write(ENT, out)
        applied.append('ent')
    else:
        applied.append('ent-exists')

    # ======== 2. AppDatabase: 版本 34→35 + AutoMigration ========
    db = read(DB)
    if db is None:
        skipped.append('db-missing')
        print('::error::' + BATCH + ' SKIP db missing')
        return
    if MARK not in db:
        db1 = replace_once(db, '    version = 34,', '    version = 35,', 'db-ver')
        if db1 is None:
            print('::error::' + BATCH + ' SKIP db version anchor')
            return
        db2 = replace_once(
            db1,
            '        AutoMigration(from = 29, to = 30, spec = Migration_29_30::class),',
            '        AutoMigration(from = 29, to = 30, spec = Migration_29_30::class),' + NL +
            '        AutoMigration(from = 34, to = 35), // ' + MARK,
            'db-mig',
        )
        if db2 is None:
            print('::error::' + BATCH + ' SKIP db migration anchor')
            return
        if balance(db2) != balance(db):
            skipped.append('db-balance')
            print('::error::' + BATCH + ' SKIP db balance')
            return
        write(DB, db2)
        applied.append('db')
    else:
        applied.append('db-exists')

    # ======== 3. ConversationRepository: 编解码映射 ========
    repo = read(REPO)
    if repo is None:
        skipped.append('repo-missing')
        print('::error::' + BATCH + ' SKIP repo missing')
        return
    if MARK not in repo:
        # 3a. import
        r1 = replace_once(
            repo,
            'import me.rerere.rikkahub.data.model.Conversation\n',
            'import me.rerere.rikkahub.data.model.Conversation' + NL +
            'import me.rerere.rikkahub.data.model.ConversationConfig' + NL,
            'repo-import',
        )
        if r1 is None:
            print('::error::' + BATCH + ' SKIP repo import anchor')
            return
        # 3b. domain → entity
        r2 = replace_once(
            r1,
            '            chatModelId = encodeChatModelId(conversation.chatModelId),',
            '            chatModelId = encodeChatModelId(conversation.chatModelId),' + NL +
            '            config = encodeConversationConfig(conversation.config), // ' + MARK,
            'repo-enc',
        )
        if r2 is None:
            print('::error::' + BATCH + ' SKIP repo encode anchor')
            return
        # 3c. entity → domain
        r3 = replace_once(
            r2,
            '            chatModelId = decodeChatModelId(conversationEntity.chatModelId),',
            '            chatModelId = decodeChatModelId(conversationEntity.chatModelId),' + NL +
            '            config = decodeConversationConfig(conversationEntity.config), // ' + MARK,
            'repo-dec',
        )
        if r3 is None:
            print('::error::' + BATCH + ' SKIP repo decode anchor')
            return
        # 3d. 末尾追加编解码 helper
        r4 = r3.rstrip() + HELPERS
        if balance(r4) != balance(repo):
            skipped.append('repo-balance')
            print('::error::' + BATCH + ' SKIP repo balance')
            return
        for need in ('encodeConversationConfig', 'decodeConversationConfig', 'import me.rerere.rikkahub.data.model.ConversationConfig'):
            if need not in r4:
                skipped.append('repo-selfcheck:' + need)
                print('::error::' + BATCH + ' SKIP repo selfcheck ' + need)
                return
        write(REPO, r4)
        applied.append('repo')
    else:
        applied.append('repo-exists')

    print('::error::' + BATCH + ' applied=[' + joinlist(applied) + '] skipped=[' + joinlist(skipped) + ']')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('::error::' + BATCH + ' crashed: ' + str(exc)[:300])
    sys.exit(0)
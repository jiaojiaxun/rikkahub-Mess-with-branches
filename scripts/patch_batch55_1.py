#!/usr/bin/env python3
'''batch55-1: 子代理审批三件套·数据层（方案 A：parentChatId + DB schema 35）

五个文件，全部原始形态锚点（前置 patch 链勘测：五文件均无人碰过）。

1. Conversation.kt: 加 parentChatId: Uuid? = null（folderId 行后）
2. ConversationEntity.kt: 加 parent_chat_id 列（照 folder_id 模式）
3. AppDatabase.kt: version 34→35 + Migration_34_35 类（照 Migration_33_34 模板）
4. DataSourceModule.kt: import + addMigrations 链尾注册
5. ConversationDAO.kt: 加 getChildrenOf 查询（折叠树用）

schema 35.json 由 CI 编译时 Gradle 自动导出（room.schemaLocation 已启用）——无需手写。
表名核对：@Entity 无 tableName → 表名 = ConversationEntity。'''
from pathlib import Path

ROOT = Path.cwd()
NL = chr(10)
MARK = 'rhParentChat'


def fail(path, msg):
    print('::error file=' + path + '::batch55-1 ' + str(msg)[:1500])
    raise SystemExit(1)


# ============================================================
# 1. Conversation.kt — 加 parentChatId 字段
# ============================================================
CV = 'app/src/main/java/me/rerere/rikkahub/data/model/Conversation.kt'
t = (ROOT / CV).read_text(encoding='utf-8')
if 'parentChatId' not in t:
    OLD_1 = (
        '    // 所属文件夹（助手内分组），null 表示未归入任何文件夹' + NL +
        '    val folderId: Uuid? = null,'
    )
    NEW_1 = (
        '    // 所属文件夹（助手内分组），null 表示未归入任何文件夹' + NL +
        '    val folderId: Uuid? = null,' + NL +
        '    // ' + MARK + ' (batch55): 子代理对话的父对话 id；null 表示普通对话。' + NL +
        '    // 子代理由 SubAgentEngine 创建，折叠树/审批继承都靠它关联父对话。' + NL +
        '    val parentChatId: Uuid? = null,'
    )
    if OLD_1 not in t:
        fail(CV, 'folderId anchor not found')
    if t.count(OLD_1) != 1:
        fail(CV, 'folderId anchor not unique')
    t = t.replace(OLD_1, NEW_1, 1)
    (ROOT / CV).write_text(t, encoding='utf-8')
    print('batch55-1: Conversation OK')
else:
    print('batch55-1: Conversation already applied')

# ============================================================
# 2. ConversationEntity.kt — 加 parent_chat_id 列
# ============================================================
CE = 'app/src/main/java/me/rerere/rikkahub/data/db/entity/ConversationEntity.kt'
e = (ROOT / CE).read_text(encoding='utf-8')
if 'parent_chat_id' not in e:
    OLD_2 = (
        '    @ColumnInfo("chat_model_id", defaultValue = "")' + NL +
        '    val chatModelId: String = "",' + NL +
        ')'
    )
    NEW_2 = (
        '    @ColumnInfo("chat_model_id", defaultValue = "")' + NL +
        '    val chatModelId: String = "",' + NL +
        '    // ' + MARK + ' (batch55): 子代理对话的父对话 id；空串表示普通对话（folder_id 同模式）。' + NL +
        '    @ColumnInfo("parent_chat_id", defaultValue = "")' + NL +
        '    val parentChatId: String = "",' + NL +
        ')'
    )
    if OLD_2 not in e:
        fail(CE, 'chatModelId anchor not found')
    if e.count(OLD_2) != 1:
        fail(CE, 'chatModelId anchor not unique')
    e = e.replace(OLD_2, NEW_2, 1)
    (ROOT / CE).write_text(e, encoding='utf-8')
    print('batch55-1: ConversationEntity OK')
else:
    print('batch55-1: ConversationEntity already applied')

# ============================================================
# 3. AppDatabase.kt — version 35 + Migration_34_35 类
# ============================================================
DB = 'app/src/main/java/me/rerere/rikkahub/data/db/AppDatabase.kt'
d = (ROOT / DB).read_text(encoding='utf-8')
if 'Migration_34_35' not in d:
    # 3a. version
    OLD_3A = '    version = 34,'
    NEW_3A = '    version = 35,'
    if OLD_3A not in d:
        fail(DB, 'version anchor not found')
    if d.count(OLD_3A) != 1:
        fail(DB, 'version anchor not unique')
    d = d.replace(OLD_3A, NEW_3A, 1)

    # 3b. Migration_34_35 类（文件尾 Migration_33_34 类后——锚=TokenUsageConverter 前）
    OLD_3B = (
        'object TokenUsageConverter {'
    )
    NEW_3B = (
        '// ' + MARK + ' (batch55): v35 adds parent_chat_id to ConversationEntity for the' + NL +
        '// sub-agent folding tree. Pure column addition with a default, mirroring the' + NL +
        '// folder_id column added in v27.' + NL +
        'class Migration_34_35 : Migration(34, 35) {' + NL +
        '    override fun migrate(db: SupportSQLiteDatabase) {' + NL +
        '        db.execSQL("ALTER TABLE ConversationEntity ADD COLUMN parent_chat_id TEXT NOT NULL DEFAULT ' + chr(39) + chr(39) + '")' + NL +
        '    }' + NL +
        '}' + NL + NL +
        'object TokenUsageConverter {'
    )
    if OLD_3B not in d:
        fail(DB, 'TokenUsageConverter anchor not found')
    if d.count(OLD_3B) != 1:
        fail(DB, 'TokenUsageConverter anchor not unique')
    d = d.replace(OLD_3B, NEW_3B, 1)
    (ROOT / DB).write_text(d, encoding='utf-8')
    print('batch55-1: AppDatabase OK')
else:
    print('batch55-1: AppDatabase already applied')

# ============================================================
# 4. DataSourceModule.kt — import + addMigrations 注册
# ============================================================
DM = 'app/src/main/java/me/rerere/rikkahub/di/DataSourceModule.kt'
m = (ROOT / DM).read_text(encoding='utf-8')
if 'Migration_34_35' not in m:
    # 4a. import（Migration_33_34 import 行后）
    OLD_4A = 'import me.rerere.rikkahub.data.db.Migration_33_34'
    NEW_4A = 'import me.rerere.rikkahub.data.db.Migration_33_34' + NL + 'import me.rerere.rikkahub.data.db.Migration_34_35'
    if OLD_4A not in m:
        fail(DM, 'Migration_33_34 import anchor not found')
    m = m.replace(OLD_4A, NEW_4A, 1)

    # 4b. addMigrations 链尾
    OLD_4B = 'Migration_32_33(), Migration_33_34())'
    NEW_4B = 'Migration_32_33(), Migration_33_34(), Migration_34_35())'
    if OLD_4B not in m:
        fail(DM, 'addMigrations chain anchor not found')
    if m.count(OLD_4B) != 1:
        fail(DM, 'addMigrations chain anchor not unique')
    m = m.replace(OLD_4B, NEW_4B, 1)
    (ROOT / DM).write_text(m, encoding='utf-8')
    print('batch55-1: DataSourceModule OK')
else:
    print('batch55-1: DataSourceModule already applied')

# ============================================================
# 5. ConversationDAO.kt — getChildrenOf 查询
# ============================================================
CD = 'app/src/main/java/me/rerere/rikkahub/data/db/dao/ConversationDAO.kt'
c = (ROOT / CD).read_text(encoding='utf-8')
if 'getChildrenOf' not in c:
    # 锚：文件头 package 行后（最稳——DAO 文件结构未读，用 package 声明做锚）
    # 先校验 package 行存在且唯一
    PKG = 'package me.rerere.rikkahub.data.db.dao'
    if PKG not in c:
        fail(CD, 'package anchor not found')
    # DAO 接口体开头——用 @Dao 声明锚
    DAO_ANCHOR = '@Dao' + NL + 'interface ConversationDAO {'
    if DAO_ANCHOR not in c:
        fail(CD, 'Dao interface anchor not found')
    NEW_QUERY = (
        '@Dao' + NL +
        'interface ConversationDAO {' + NL + NL +
        '    // ' + MARK + ' (batch55): 按父对话查子代理对话（折叠树/审批继承用）' + NL +
        '    @Query("SELECT * FROM ConversationEntity WHERE parent_chat_id = :parentId ORDER BY update_at DESC")' + NL +
        '    suspend fun getChildrenOf(parentId: String): List<ConversationEntity>'
    )
    c = c.replace(DAO_ANCHOR, NEW_QUERY, 1)
    (ROOT / CD).write_text(c, encoding='utf-8')
    print('batch55-1: ConversationDAO OK')
else:
    print('batch55-1: ConversationDAO already applied')

# ============================================================
# 自检（全文件存在性 + 关键 token）
# ============================================================
checks = [
    (CV, ['parentChatId: Uuid? = null']),
    (CE, ['parent_chat_id', 'val parentChatId: String = ""']),
    (DB, ['version = 35', 'class Migration_34_35', 'ALTER TABLE ConversationEntity ADD COLUMN parent_chat_id']),
    (DM, ['Migration_34_35()', 'import me.rerere.rikkahub.data.db.Migration_34_35']),
    (CD, ['getChildrenOf', 'parent_chat_id = :parentId']),
]
for path, needs in checks:
    body = (ROOT / path).read_text(encoding='utf-8')
    for need in needs:
        if need not in body:
            fail(path, 'final selfcheck missing: ' + need)

print('batch55-1: OK (5 files, schema 35 auto-exported by Gradle)')

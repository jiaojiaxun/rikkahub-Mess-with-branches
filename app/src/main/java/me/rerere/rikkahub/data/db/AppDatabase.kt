package me.rerere.rikkahub.data.db

import androidx.room.AutoMigration
import androidx.room.migration.AutoMigrationSpec
import androidx.room.Database
import androidx.room.DeleteTable
import androidx.room.migration.Migration
import androidx.sqlite.db.SupportSQLiteDatabase
import androidx.room.RoomDatabase
import androidx.room.TypeConverter
import androidx.room.TypeConverters
import me.rerere.ai.core.TokenUsage
import me.rerere.rikkahub.data.db.dao.ConversationDAO
import me.rerere.rikkahub.data.db.dao.ConversationCompactionDAO
import me.rerere.rikkahub.data.db.dao.FavoriteDAO
import me.rerere.rikkahub.data.db.dao.FolderDAO
import me.rerere.rikkahub.data.db.dao.GenMediaDAO
import me.rerere.rikkahub.data.db.dao.ManagedFileDAO
import me.rerere.rikkahub.data.db.dao.MemoryDAO
import me.rerere.rikkahub.data.db.dao.MessageNodeDAO
import me.rerere.rikkahub.data.db.dao.WorkspaceDAO
import me.rerere.rikkahub.data.db.entity.ConversationEntity
import me.rerere.rikkahub.data.db.entity.ConversationCompactionEntity
import me.rerere.rikkahub.data.db.entity.FavoriteEntity
import me.rerere.rikkahub.data.db.entity.FolderEntity
import me.rerere.rikkahub.data.db.entity.GenMediaEntity
import me.rerere.rikkahub.data.db.entity.ManagedFileEntity
import me.rerere.rikkahub.data.db.entity.MemoryEntity
import me.rerere.rikkahub.data.db.entity.MessageNodeEntity
import me.rerere.rikkahub.data.db.entity.WorkspaceEntity
import me.rerere.rikkahub.data.db.migrations.Migration_16_17
import me.rerere.rikkahub.data.db.migrations.Migration_20_21
import me.rerere.rikkahub.data.db.migrations.Migration_21_22
import me.rerere.rikkahub.data.db.migrations.Migration_22_23
import me.rerere.rikkahub.data.db.migrations.Migration_8_9
import me.rerere.rikkahub.utils.JsonInstant

@Database(
    entities = [
        ConversationEntity::class,
        ConversationCompactionEntity::class,
        MemoryEntity::class,
        GenMediaEntity::class,
        MessageNodeEntity::class,
        ManagedFileEntity::class,
        FavoriteEntity::class,
        WorkspaceEntity::class,
        FolderEntity::class,
    ],
    version = 34,
    autoMigrations = [
        AutoMigration(from = 1, to = 2),
        AutoMigration(from = 2, to = 3),
        AutoMigration(from = 3, to = 4),
        AutoMigration(from = 4, to = 5),
        AutoMigration(from = 5, to = 6),
        AutoMigration(from = 7, to = 8),
        AutoMigration(from = 8, to = 9, spec = Migration_8_9::class),
        AutoMigration(from = 9, to = 10),
        AutoMigration(from = 10, to = 11),
        AutoMigration(from = 12, to = 13),
        AutoMigration(from = 16, to = 17, spec = Migration_16_17::class),
        AutoMigration(from = 17, to = 18),
        AutoMigration(from = 18, to = 19),
        AutoMigration(from = 19, to = 20),
        AutoMigration(from = 20, to = 21, spec = Migration_20_21::class),
        AutoMigration(from = 21, to = 22, spec = Migration_21_22::class),
        AutoMigration(from = 22, to = 23, spec = Migration_22_23::class),
        // v25: upstream 2.2.6 added conversation-level custom_system_prompt / mode_injection_ids
        // / lorebook_ids columns (all carry defaultValue, so a plain auto-migration suffices).
        AutoMigration(from = 24, to = 25),
        // v26: the 2.3.1 merge brings upstream's workspaces table (WorkspaceEntity). Existing
        // fork users never had it, so Room auto-creates the table on this step.
        AutoMigration(from = 25, to = 26),
        // v27: upstream 2.4.x added conversation folders (FolderEntity -> conversation_folder
        // table) plus a folder_id column on ConversationEntity (defaultValue ""). Both are pure
        // additions; upstream numbered it as their v24, folded into the fork's version space here.
        AutoMigration(from = 26, to = 27),
        // v28: indices only. Conversation listing, assistant memory lookup, the enabled-job
        // scan and per-job run history were all full table scans; see each entity for which
        // query shape its index covers. Pure additions, so Room generates the CREATE INDEX
        // statements itself.
        AutoMigration(from = 27, to = 28),
        // v29: the conversation_compaction table backing automatic context compaction. The
        // table is a pure addition and the original message nodes are left untouched, so Room
        // creates it outright. Numbered 29 rather than 28 because the fork's v28 was already
        // taken by the index migration above.
        AutoMigration(from = 28, to = 29),
        // v30: a chat_model_id column on ConversationEntity so a per-conversation model
        // override survives ChatService.initializeConversation reloading the conversation
        // from Room. Nullable-equivalent (empty string default, matching folder_id), so a plain
        // auto-migration suffices.
        AutoMigration(from = 29, to = 30, spec = Migration_29_30::class),
    ]
)
@TypeConverters(TokenUsageConverter::class)
abstract class AppDatabase : RoomDatabase() {
    abstract fun conversationDao(): ConversationDAO

    abstract fun conversationCompactionDao(): ConversationCompactionDAO

    abstract fun memoryDao(): MemoryDAO

    abstract fun genMediaDao(): GenMediaDAO

    abstract fun messageNodeDao(): MessageNodeDAO

    abstract fun managedFileDao(): ManagedFileDAO

    abstract fun favoriteDao(): FavoriteDAO

    abstract fun workspaceDao(): WorkspaceDAO

    abstract fun folderDao(): FolderDAO
}

@DeleteTable.Entries(
    DeleteTable(tableName = "workflows"),
    DeleteTable(tableName = "workflow_runs"),
)
class Migration_29_30 : AutoMigrationSpec

class Migration_30_31 : Migration(30, 31) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("DROP TABLE IF EXISTS workflows")
        db.execSQL("DROP TABLE IF EXISTS workflow_runs")
        db.execSQL("DROP TABLE IF EXISTS ssh_hosts")
        db.execSQL("DROP TABLE IF EXISTS telegram_chats")
    }
}

class Migration_31_32 : Migration(31, 32) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("DROP TABLE IF EXISTS agent_runs")
    }
}

class Migration_32_33 : Migration(32, 33) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("DROP TABLE IF EXISTS scheduled_jobs")
        db.execSQL("DROP TABLE IF EXISTS scheduled_job_runs")
    }
}

class Migration_33_34 : Migration(33, 34) {
    override fun migrate(db: SupportSQLiteDatabase) {
        db.execSQL("""
            CREATE TABLE IF NOT EXISTS workspaces_new (
                id TEXT NOT NULL,
                name TEXT NOT NULL,
                root TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                last_access_at INTEGER,
                tool_approvals TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY(id)
            )
        """.trimIndent())
        db.execSQL("""
            INSERT OR REPLACE INTO workspaces_new (id, name, root, created_at, updated_at, last_access_at, tool_approvals)
            SELECT id, name, root, created_at, updated_at, last_access_at, tool_approvals
            FROM workspaces
        """.trimIndent())
        db.execSQL("DROP TABLE workspaces")
        db.execSQL("ALTER TABLE workspaces_new RENAME TO workspaces")
        db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS index_workspaces_root ON workspaces(root)")
        db.execSQL("CREATE INDEX IF NOT EXISTS index_workspaces_updated_at ON workspaces(updated_at)")
    }
}

object TokenUsageConverter {
    @TypeConverter
    fun fromTokenUsage(usage: TokenUsage?): String {
        return JsonInstant.encodeToString(usage)
    }

    @TypeConverter
    fun toTokenUsage(usage: String): TokenUsage? {
        return JsonInstant.decodeFromString(usage)
    }
}

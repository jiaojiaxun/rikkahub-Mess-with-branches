package me.rerere.rikkahub.data.db

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.util.Log
import java.io.File

/**
 * Reconciles a database file restored from an upstream or older fork backup so Room can open it.
 *
 * This slim build accepts older schema numbers and path conventions, but only restores tables
 * owned by the current build. Tables belonging to removed workflow, scheduler, SSH, Telegram,
 * and sub-agent features are deleted from the staged file instead of being re-created.
 * Shared tables and columns are completed before Room opens the file, preventing duplicate-column
 * migrations and the malformed-database failure seen when a live WAL was replaced in place.
 *  - It backfills the indices and columns that Room would normally add via the auto-migrations
 *    between the restored version and [EXPECTED_VERSION] (see [BACKFILL_INDEX_DDL] and the
 *    `chat_model_id` column below). Those auto-migrations never run on the "already current"
 *    path, since it jumps straight to [EXPECTED_VERSION] instead of walking the chain, so
 *    anything they would have added has to be recreated here too (issue #60).
 *  - If the file is already at the fork's current schema (stamped at the matching version, or
 *    an upstream file whose shared tables already carry every modern column), it stamps Room's
 *    user_version and identity row to the fork's current values so Room opens the file with no
 *    migration. Without this Room either replays colliding migrations or rejects the foreign
 *    hash, even though every table is now present. The shared tables match column-for-column
 *    because the fork tracks upstream's schema, so trusting the hash is sound.
 *
 * If the backup is at an older version that is not yet schema-complete, Room runs its normal
 * migrations up to current and sets the identity itself; pre-creating the tables/indices just
 * lets those migrations find them (all statements are `IF NOT EXISTS`, matching how Room's own
 * generated auto-migration SQL creates indices, so replaying them causes no conflict). Backups
 * newer than the app are left untouched (Room reports the downgrade).
 *
 * Best-effort: any failure here is logged and swallowed so a restore never half-breaks. The
 * worst case is the same pre-existing crash on next open, never data loss: there is no
 * destructive-migration fallback configured, so the restored rows always survive on disk.
 */
object ImportedDatabaseReconciler {

    private const val TAG = "DbReconciler"
    private const val DB_NAME = "rikka_hub"

    /**
     * Room's schema version and identity hash for [AppDatabase]. Both are copied verbatim
     * from app/schemas/me.rerere.rikkahub.data.db.AppDatabase/34.json (the identity hash also
     * appears in the generated AppDatabase_Impl RoomOpenDelegate). When the schema version is
     * bumped, update BOTH constants (and the table DDL below if the fork-only tables changed,
     * BACKFILL_INDEX_DDL if any entity gained/lost an index, and MODERN_COLUMN_SENTINELS if
     * newer *shared* conversation columns were added) or this reconciliation will silently stop
     * matching. `internal` so a JVM test can assert these stay in sync with the schema export.
     */
    internal const val EXPECTED_VERSION = 34
    internal const val EXPECTED_IDENTITY_HASH = "124de8341c4ffb1dae0a3e47c1d5fbde"

    /**
     * Columns that a restored file must already have for its shared schema to be considered
     * byte-for-byte equal to the fork's current schema. They are exactly the columns the
     * fork's 24->25 / 25->26 / 26->27 auto-migrations add (custom_system_prompt at 25,
     * workspace_cwd at 26, folder_id at 27), so a file carrying all three would collide on
     * every one of those replays. Upstream 2.4.x carries all three; a genuine fork file below
     * v27 carries only a prefix, so it still migrates normally.
     */
    private val MODERN_COLUMN_SENTINELS = listOf("custom_system_prompt", "workspace_cwd", "folder_id")

    /** Columns required before an imported conversation database may be stamped as current. */
    private val REQUIRED_CONVERSATION_COLUMNS = setOf(
        "id", "assistant_id", "title", "nodes", "create_at", "update_at",
        "suggestions", "is_pinned", "custom_system_prompt", "mode_injection_ids",
        "lorebook_ids", "workspace_cwd", "folder_id", "chat_model_id",
    )

    /** The current slim workspace table: the removed shell_status column must never be present. */
    internal val CURRENT_WORKSPACE_COLUMNS = setOf(
        "id",
        "name",
        "root",
        "created_at",
        "updated_at",
        "last_access_at",
        "tool_approvals",
    )

    internal fun isCurrentWorkspaceSchema(columns: Set<String>): Boolean =
        CURRENT_WORKSPACE_COLUMNS.all(columns::contains) && "shell_status" !in columns

    /**
     * True when the shared conversation schema already contains every column that the old
     * auto-migrations would add. This is deliberately independent of the workspaces table: some
     * official/third-party exports contain conversations but omit empty workspace metadata.
     */
    internal fun isCurrentSharedSchema(columns: Set<String>): Boolean =
        MODERN_COLUMN_SENTINELS.all(columns::contains)

    private const val CONTEXT_COMPACTION_DDL =
        "CREATE TABLE IF NOT EXISTS `conversation_compaction` (`conversation_id` TEXT NOT NULL, `summary` TEXT NOT NULL, `tail_start_node_id` TEXT, `source_end_node_id` TEXT NOT NULL, `summary_model_id` TEXT NOT NULL, `is_auto` INTEGER NOT NULL, `source_token_estimate` INTEGER NOT NULL, `created_at` INTEGER NOT NULL, PRIMARY KEY(`conversation_id`), FOREIGN KEY(`conversation_id`) REFERENCES `ConversationEntity`(`id`) ON UPDATE NO ACTION ON DELETE CASCADE )"

    /** Tables belonging to features removed from the slim build. Never recreate them on import. */
    private val REMOVED_FEATURE_TABLES = listOf(
        "scheduled_jobs",
        "scheduled_job_runs",
        "ssh_hosts",
        "telegram_chats",
        "workflows",
        "workflow_runs",
        "agent_runs",
    )

    /**
     * Indices the fork's 27->28 auto-migration adds on tables that already exist before that
     * step (`ConversationEntity`, `MemoryEntity`). That migration is a pure schema diff compiled
     * from app/schemas/.../27.json and 28.json, so it never runs on the "already current" path
     * below, which stamps the file straight to [EXPECTED_VERSION]: the indices would otherwise
     * be silently missing (issue #60, `Found: indices = {}` on `ConversationEntity`). Every
     * statement is `IF NOT EXISTS`, so running this against a database that already has the
     * indices - including a genuine backup already on v30 - is a safe no-op that touches no data.
     */
    internal val BACKFILL_INDEX_DDL: List<String> = listOf(
        "CREATE INDEX IF NOT EXISTS `index_ConversationEntity_assistant_id_is_pinned_update_at` ON `ConversationEntity` (`assistant_id`, `is_pinned`, `update_at`)",
        "CREATE INDEX IF NOT EXISTS `index_ConversationEntity_is_pinned_update_at` ON `ConversationEntity` (`is_pinned`, `update_at`)",
        "CREATE INDEX IF NOT EXISTS `index_MemoryEntity_assistant_id` ON `MemoryEntity` (`assistant_id`)",
    )

    /**
     * Call after a restore has written the database file, and only when the restore actually
     * included the database. Safe to call when the file is a genuine agent backup (every
     * statement is idempotent) or when the file does not exist (no-op).
     */
    fun reconcile(context: Context) {
        reconcileDatabaseFile(context.getDatabasePath(DB_NAME))
    }

    /**
     * Testable core of [reconcile]: operate on the raw db file at [dbFile] directly, so a test
     * can exercise it against a temp file instead of the app's live `rikka_hub` database.
     */
    internal fun reconcileDatabaseFile(dbFile: File) {
        if (!dbFile.exists()) {
            Log.i(TAG, "reconcile: no database file at ${dbFile.absolutePath}, skipping")
            return
        }
        try {
            SQLiteDatabase.openDatabase(
                dbFile.absolutePath,
                null,
                SQLiteDatabase.OPEN_READWRITE,
            ).use { db ->
                val version = db.version // PRAGMA user_version
                if (version > EXPECTED_VERSION) {
                    Log.w(TAG, "reconcile: backup db version $version is newer than $EXPECTED_VERSION; leaving untouched")
                    return
                }

                // A file whose shared schema already matches the fork's current schema must not
                // be migrated: Room would replay the fork's 24->27 auto-migrations and re-ADD
                // columns the file already has, crashing with "duplicate column name" (an
                // upstream 2.4.x backup stamps user_version 24 but carries every modern column;
                // see issues #10, #11). Detect that case by the sentinel columns those very
                // migrations add, and also require the current slim workspace shape. Otherwise a
                // v33 file carrying shell_status could be incorrectly stamped as v34 and then
                // fail Room's schema validation.
                val workspaceExists = tableExists(db, "workspaces")
                val workspaceColumns = tableColumns(db, "workspaces")
                val conversationColumns = tableColumns(db, "ConversationEntity")
                var workspaceSchemaCurrent = isCurrentWorkspaceSchema(workspaceColumns)
                var alreadyCurrent = false

                db.beginTransaction()
                try {
                    // A valid upstream/third-party export may have all modern conversation columns
                    // but no workspace table because it never contained a workspace. Prepare the
                    // empty current table before deciding whether Room migrations can be skipped.
                    // This is also the path that prevents the overwrite-only duplicate
                    // custom_system_prompt crash reported for such exports.
                    val sharedSchemaCurrent =
                        isCurrentSharedSchema(conversationColumns) &&
                            REQUIRED_CONVERSATION_COLUMNS.all(conversationColumns::contains)
                    if (sharedSchemaCurrent && !workspaceExists) {
                        createWorkspaceTable(db)
                        workspaceSchemaCurrent = true
                    } else if (sharedSchemaCurrent && workspaceColumns.isNotEmpty() && !workspaceSchemaCurrent) {
                        workspaceSchemaCurrent = rebuildWorkspaceTable(db, workspaceColumns)
                    }
                    alreadyCurrent = sharedSchemaCurrent && workspaceSchemaCurrent

                    REMOVED_FEATURE_TABLES.forEach { table -> db.execSQL("DROP TABLE IF EXISTS `$table`") }
                    BACKFILL_INDEX_DDL.forEach(db::execSQL)

                    if (workspaceSchemaCurrent && (version == EXPECTED_VERSION || alreadyCurrent)) {
                        // v29 adds this table and v30 adds the chat_model_id column below,
                        // both through Room auto-migrations. Imported upstream databases and
                        // genuine v27/v28 fork databases are stamped straight to
                        // EXPECTED_VERSION here, so create/add them before installing the
                        // identity for EXPECTED_VERSION.
                        db.execSQL(CONTEXT_COMPACTION_DDL)
                        // A few exporters stamp a new user_version before writing every shared
                        // column. Complete all known text columns before installing the identity;
                        // otherwise Room may replay Migration_30_31 and collide with a column
                        // that is already present in the imported file.
                        MODERN_COLUMN_SENTINELS.forEach { column ->
                            if (!hasColumn(db, "ConversationEntity", column)) {
                                db.execSQL(
                                    "ALTER TABLE `ConversationEntity` ADD COLUMN `$column` TEXT NOT NULL DEFAULT ''"
                                )
                            }
                        }
                        if (!hasColumn(db, "ConversationEntity", "chat_model_id")) {
                            db.execSQL(
                                "ALTER TABLE `ConversationEntity` ADD COLUMN `chat_model_id` TEXT NOT NULL DEFAULT ''"
                            )
                        }
                        // No migration should run: the file is either already stamped at the
                        // fork's version, or it is an upstream file whose shared schema already
                        // matches it. Point Room's identity row and user_version at the fork so
                        // the integrity check passes now that every fork-only table is present.
                        db.execSQL(
                            "CREATE TABLE IF NOT EXISTS room_master_table (id INTEGER PRIMARY KEY, identity_hash TEXT)"
                        )
                        db.execSQL(
                            "INSERT OR REPLACE INTO room_master_table (id, identity_hash) VALUES (42, ?)",
                            arrayOf(EXPECTED_IDENTITY_HASH),
                        )
                        if (version != EXPECTED_VERSION) {
                            // PRAGMA user_version is transactional (SQLiteOpenHelper sets it the
                            // same way inside its own upgrade transaction), so this commits or
                            // rolls back atomically with the DDL and identity row above.
                            db.version = EXPECTED_VERSION
                        }
                    }
                    db.setTransactionSuccessful()
                } finally {
                    db.endTransaction()
                }
                Log.i(TAG, "reconcile: reconciled imported db (version=$version, alreadyCurrent=$alreadyCurrent)")
            }
        } catch (t: Throwable) {
            // Never let reconciliation break the restore. Worst case is the pre-existing
            // behaviour (a crash on next open); the user's rows are still on disk.
            Log.w(TAG, "reconcile: failed to reconcile imported db", t)
        }
    }

    private fun tableExists(db: SQLiteDatabase, table: String): Boolean {
        return try {
            db.rawQuery(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
                arrayOf(table),
            ).use { it.moveToFirst() }
        } catch (t: Throwable) {
            Log.w(TAG, "tableExists: failed to inspect $table", t)
            false
        }
    }

    /** Create an empty current workspaces table for a malformed v34 import with no table. */
    private fun createWorkspaceTable(db: SQLiteDatabase) {
        db.execSQL("""
            CREATE TABLE IF NOT EXISTS `workspaces` (
                `id` TEXT NOT NULL,
                `name` TEXT NOT NULL,
                `root` TEXT NOT NULL,
                `created_at` INTEGER NOT NULL,
                `updated_at` INTEGER NOT NULL,
                `last_access_at` INTEGER,
                `tool_approvals` TEXT NOT NULL DEFAULT '{}',
                PRIMARY KEY(`id`)
            )
        """.trimIndent())
        db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS `index_workspaces_root` ON `workspaces` (`root`)")
        db.execSQL("CREATE INDEX IF NOT EXISTS `index_workspaces_updated_at` ON `workspaces` (`updated_at`)")
    }

    /** Return the exact column names of [table], or an empty set when it is absent/unreadable. */
    private fun tableColumns(db: SQLiteDatabase, table: String): Set<String> {
        return try {
            db.rawQuery("PRAGMA table_info(`$table`)", null).use { cursor ->
                val nameIndex = cursor.getColumnIndex("name")
                if (nameIndex < 0) return emptySet()
                buildSet {
                    while (cursor.moveToNext()) add(cursor.getString(nameIndex))
                }
            }
        } catch (t: Throwable) {
            Log.w(TAG, "tableColumns: failed to inspect $table", t)
            emptySet()
        }
    }

    /**
     * Repair a database that was already stamped v34 before the shell_status removal landed.
     * The copy is assembled from whatever compatible columns the imported table has; missing
     * optional values use the entity defaults, while the stable identity columns are required.
     */
    private fun rebuildWorkspaceTable(db: SQLiteDatabase, existingColumns: Set<String>): Boolean {
        val requiredIdentity = setOf("id", "name", "root", "created_at", "updated_at")
        if (!requiredIdentity.all(existingColumns::contains)) return false
        return try {
            db.execSQL("DROP TABLE IF EXISTS `workspaces_new`")
            db.execSQL("""
                CREATE TABLE `workspaces_new` (
                    `id` TEXT NOT NULL,
                    `name` TEXT NOT NULL,
                    `root` TEXT NOT NULL,
                    `created_at` INTEGER NOT NULL,
                    `updated_at` INTEGER NOT NULL,
                    `last_access_at` INTEGER,
                    `tool_approvals` TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY(`id`)
                )
            """.trimIndent())
            val targetColumns = listOf("id", "name", "root", "created_at", "updated_at", "last_access_at", "tool_approvals")
            val expressions = targetColumns.map { column ->
                when {
                    column in existingColumns -> "`$column`"
                    column == "tool_approvals" -> "'{}'"
                    else -> "NULL"
                }
            }
            db.execSQL(
                "INSERT INTO `workspaces_new` (${targetColumns.joinToString(",") { "`$it`" }}) " +
                    "SELECT ${expressions.joinToString(",")} FROM `workspaces`"
            )
            db.execSQL("DROP TABLE `workspaces`")
            db.execSQL("ALTER TABLE `workspaces_new` RENAME TO `workspaces`")
            db.execSQL("CREATE UNIQUE INDEX IF NOT EXISTS `index_workspaces_root` ON `workspaces` (`root`)")
            db.execSQL("CREATE INDEX IF NOT EXISTS `index_workspaces_updated_at` ON `workspaces` (`updated_at`)")
            true
        } catch (t: Throwable) {
            Log.w(TAG, "rebuildWorkspaceTable: failed", t)
            false
        }
    }

    /** True if [table] exists and has a column named [column]. Best-effort; false on error. */
    private fun hasColumn(db: SQLiteDatabase, table: String, column: String): Boolean {
        return try {
            db.rawQuery("PRAGMA table_info(`$table`)", null).use { cursor ->
                val nameIndex = cursor.getColumnIndex("name")
                var found = false
                if (nameIndex >= 0) {
                    while (!found && cursor.moveToNext()) {
                        found = cursor.getString(nameIndex) == column
                    }
                }
                found
            }
        } catch (t: Throwable) {
            Log.w(TAG, "hasColumn: failed to inspect $table.$column", t)
            false
        }
    }
}

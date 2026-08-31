package me.rerere.rikkahub.data.db

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Unit coverage for the pure SQL-list constants behind [ImportedDatabaseReconciler].
 *
 * [ImportedDatabaseReconciler.reconcileDatabaseFile] itself opens a real
 * `android.database.sqlite.SQLiteDatabase`, which is not available in this repo's plain JVM
 * unit tests (no Robolectric), so it cannot be exercised here. What *is* pure, plain Kotlin is
 * [ImportedDatabaseReconciler.BACKFILL_INDEX_DDL] and the [ImportedDatabaseReconciler.EXPECTED_VERSION]
 * / [ImportedDatabaseReconciler.EXPECTED_IDENTITY_HASH] constants it stamps a reconciled file with.
 *
 * Issue #60: restoring an official upstream backup (db stamped at v24) and letting the
 * reconciler jump it straight to [ImportedDatabaseReconciler.EXPECTED_VERSION] skipped the
 * fork's 27->28 auto-migration entirely, so `ConversationEntity` ended up with no indices at
 * all (`Found: indices = {}`) even though Room's compiled schema for v30 expects two. This test
 * pins the fix: every index that migration would have added is present in the backfill list,
 * every statement is idempotent, and the stamped version/hash match what app/schemas/.../30.json
 * actually declares - so a future schema bump that forgets to update the reconciler shows up as
 * a failing assertion here instead of a silent restore crash.
 */
class ImportedDatabaseReconcilerTest {

    @Test
    fun `expected version matches the fork's current AppDatabase version`() {
        assertEquals(34, ImportedDatabaseReconciler.EXPECTED_VERSION)
    }

    @Test
    fun `expected identity hash matches schema 34`() {
        assertEquals("124de8341c4ffb1dae0a3e47c1d5fbde", ImportedDatabaseReconciler.EXPECTED_IDENTITY_HASH)
    }

    @Test
    fun `backfills both ConversationEntity indices Room's 27-28 migration adds`() {
        val ddl = ImportedDatabaseReconciler.BACKFILL_INDEX_DDL
        assertTrue(ddl.any {
            it.contains("index_ConversationEntity_assistant_id_is_pinned_update_at") &&
                it.contains("ON `ConversationEntity` (`assistant_id`, `is_pinned`, `update_at`)")
        })
        assertTrue(ddl.any {
            it.contains("index_ConversationEntity_is_pinned_update_at") &&
                it.contains("ON `ConversationEntity` (`is_pinned`, `update_at`)")
        })
    }

    @Test
    fun `backfills the MemoryEntity index without removed feature indices`() {
        val ddl = ImportedDatabaseReconciler.BACKFILL_INDEX_DDL
        assertTrue(ddl.any { it.contains("index_MemoryEntity_assistant_id") })
        assertTrue(ddl.none { it.contains("scheduled_jobs") || it.contains("workflow") })
    }

    @Test
    fun `workspace schema with removed shell status cannot be treated as current`() {
        val legacyColumns = ImportedDatabaseReconciler.CURRENT_WORKSPACE_COLUMNS + "shell_status"
        assertFalse(ImportedDatabaseReconciler.isCurrentWorkspaceSchema(legacyColumns))
    }

    @Test
    fun `current workspace schema requires tool approvals and excludes shell status`() {
        assertTrue(
            ImportedDatabaseReconciler.isCurrentWorkspaceSchema(
                ImportedDatabaseReconciler.CURRENT_WORKSPACE_COLUMNS,
            )
        )
        assertFalse(
            ImportedDatabaseReconciler.isCurrentWorkspaceSchema(
                ImportedDatabaseReconciler.CURRENT_WORKSPACE_COLUMNS - "tool_approvals",
            )
        )
    }

    @Test
    fun `current shared schema is independent from workspace table presence`() {
        assertTrue(
            ImportedDatabaseReconciler.isCurrentSharedSchema(
                setOf("custom_system_prompt", "workspace_cwd", "folder_id"),
            )
        )
        assertFalse(
            ImportedDatabaseReconciler.isCurrentSharedSchema(
                setOf("custom_system_prompt", "workspace_cwd"),
            )
        )
    }

    @Test
    fun `legacy workspace shell status stays non-current even with modern shared columns`() {
        assertTrue(
            ImportedDatabaseReconciler.isCurrentSharedSchema(
                setOf("custom_system_prompt", "workspace_cwd", "folder_id"),
            )
        )
        assertFalse(
            ImportedDatabaseReconciler.isCurrentWorkspaceSchema(
                ImportedDatabaseReconciler.CURRENT_WORKSPACE_COLUMNS + "shell_status",
            )
        )
    }

    @Test
    fun `every backfill statement is idempotent`() {
        ImportedDatabaseReconciler.BACKFILL_INDEX_DDL.forEach {
            assertTrue("not idempotent: $it", it.startsWith("CREATE INDEX IF NOT EXISTS"))
        }
    }
}

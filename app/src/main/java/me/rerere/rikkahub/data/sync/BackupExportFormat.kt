package me.rerere.rikkahub.data.sync

/** The local export targets exposed by the backup page. */
enum class BackupExportFormat {
    /**
     * Everything this build has. The archive is a superset of [OFFICIAL]: its root holds the
     * RikkaHub 2.4.14-compatible core (so the official app can import it), and the fork's raw
     * database and settings live under [AGENT_FULL_PREFIX], which the official app skips and
     * this app prefers.
     */
    FULL,

    /**
     * RikkaHub 2.4.14-compatible layout (shown as "兼容导出（宽松）"). Fork-only fields inside
     * otherwise official data are kept; the official app ignores them.
     */
    OFFICIAL,

    /**
     * Same pipeline as [OFFICIAL], then everything RikkaHub 2.4.14 does not know is removed
     * (tables, columns, settings keys, provider / tool / message part types). See
     * [me.rerere.rikkahub.data.sync.webdav.OfficialPurifier].
     */
    PURE_OFFICIAL,
}

/**
 * All names start with `backup_`: RikkaHub 2.4.14 lists only `backup_*.zip` on WebDAV / S3,
 * so any other prefix makes the backup invisible to the official app.
 */
fun BackupExportFormat.fileName(timestamp: String): String = when (this) {
    BackupExportFormat.FULL -> "backup_${timestamp}_agent.zip"
    BackupExportFormat.OFFICIAL -> "backup_${timestamp}_official.zip"
    BackupExportFormat.PURE_OFFICIAL -> "backup_${timestamp}_pure.zip"
}

/** Folder inside a FULL archive for data the official app cannot read. */
const val AGENT_FULL_PREFIX = "rikkahub_agent/"

/** Standalone snapshot of this build's database (current schema, all fork tables). */
const val AGENT_FULL_DB_ENTRY = "rikkahub_agent/agent_rikka_hub.db"

/** This build's unfiltered settings (all provider types). */
const val AGENT_FULL_SETTINGS_ENTRY = "rikkahub_agent/agent_settings.json"

/**
 * True for backup archives this app can list and restore: upstream RikkaHub names
 * (`backup_<ts>.zip`), current names (see [fileName]) and older fork names
 * (`rikkahub_agent_backup_<ts>.zip`, `rikkahub_official_backup_<ts>.zip`).
 */
fun isBackupArchiveName(name: String): Boolean {
    val lower = name.lowercase()
    return lower.endsWith(".zip") && (lower.startsWith("backup_") || lower.contains("_backup_"))
}

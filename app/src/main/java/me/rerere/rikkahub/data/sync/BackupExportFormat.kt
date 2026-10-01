package me.rerere.rikkahub.data.sync

/** The two local export targets exposed by the backup page. */
enum class BackupExportFormat {
    /** Raw current slim-build data, including current fork extensions. */
    FULL,

    /** RikkaHub 2.4.14-compatible database/files layout. */
    OFFICIAL,
}

fun BackupExportFormat.fileName(timestamp: String): String = when (this) {
    BackupExportFormat.FULL -> "rikkahub_agent_backup_$timestamp.zip"
    BackupExportFormat.OFFICIAL -> "rikkahub_official_backup_$timestamp.zip"
}

/**
 * True for backup archives this app can list and restore: upstream RikkaHub names
 * (`backup_<ts>.zip`) and this fork's names (see [fileName]). Remote list filters must use
 * this instead of a hard-coded prefix, otherwise freshly uploaded backups are hidden.
 */
fun isBackupArchiveName(name: String): Boolean {
    val lower = name.lowercase()
    return lower.endsWith(".zip") && (lower.startsWith("backup_") || lower.contains("_backup_"))
}

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

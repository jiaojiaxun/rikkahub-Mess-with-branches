package me.rerere.rikkahub.data.sync

/**
 * How a database-bearing backup is applied.
 * OVERWRITE replaces the current database after Room is closed; MERGE reads a staged database
 * and writes records into the live Room database without replacing its file.
 */
enum class BackupRestoreMode {
    OVERWRITE,
    MERGE,
}

fun BackupRestoreMode.displayName(): String = when (this) {
    BackupRestoreMode.OVERWRITE -> "覆盖现有数据"
    BackupRestoreMode.MERGE -> "合并到现有数据"
}

fun BackupRestoreMode.description(): String = when (this) {
    BackupRestoreMode.OVERWRITE -> "备份中的数据库和文件将替换当前同类数据。"
    BackupRestoreMode.MERGE -> "新增内容会加入；同 ID 无分叉时采用较新的备份，有分叉时保留为新对话。"
}

fun BackupRestoreMode.shortName(): String = when (this) {
    BackupRestoreMode.OVERWRITE -> "覆盖"
    BackupRestoreMode.MERGE -> "合并"
}

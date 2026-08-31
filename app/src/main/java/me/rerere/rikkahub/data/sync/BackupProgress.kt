package me.rerere.rikkahub.data.sync

/**
 * User-visible progress for backup, restore, import, export and WebDAV operations.
 * [completed] and [total] are bytes when known, otherwise entries/stages.
 */
data class BackupProgress(
    val phase: String,
    val completed: Long = 0L,
    val total: Long = 0L,
    val detail: String = "",
    /** Describes what [completed]/[total] measure; ZIP generation uses pre-compression input bytes. */
    val totalLabel: String = "数据量",
) {
    val fraction: Float?
        get() = total.takeIf { it > 0L }?.let {
            (completed.toFloat() / it.toFloat()).coerceIn(0f, 1f)
        }

    val percent: Int?
        get() = fraction?.let { (it * 100f).toInt().coerceIn(0, 100) }
}

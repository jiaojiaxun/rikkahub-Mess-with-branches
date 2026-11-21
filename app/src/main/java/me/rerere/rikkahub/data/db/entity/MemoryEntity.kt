package me.rerere.rikkahub.data.db.entity

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

@Entity(indices = [Index(value = ["assistant_id"])])
data class MemoryEntity(
    @PrimaryKey(true)
    val id: Int = 0,
    @ColumnInfo("assistant_id")
    val assistantId: String,
    @ColumnInfo("content")
    val content: String = "",
    // rhShortMem: 短期记忆归属的会话 id; 空串 = 长期/全局记忆
    @ColumnInfo("conversation_id")
    val conversationId: String = "",
)

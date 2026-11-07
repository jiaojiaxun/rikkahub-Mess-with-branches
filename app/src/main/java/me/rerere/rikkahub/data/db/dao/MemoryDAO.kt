package me.rerere.rikkahub.data.db.dao

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.Query
import androidx.room.Update
import kotlinx.coroutines.flow.Flow
import me.rerere.rikkahub.data.db.entity.MemoryEntity

@Dao
interface MemoryDAO {
    // rhShortMem: 长期/全局查询只看 conversation_id 为空的记录, 会话私有记忆不走这里
    @Query("SELECT * FROM memoryentity WHERE assistant_id = :assistantId AND conversation_id = ''")
    fun getMemoriesOfAssistantFlow(assistantId: String): Flow<List<MemoryEntity>>

    @Query("SELECT * FROM memoryentity WHERE assistant_id = :assistantId AND conversation_id = ''")
    suspend fun getMemoriesOfAssistant(assistantId: String): List<MemoryEntity>

    // rhShortMem: 单个会话的短期记忆(生成时注入用)
    @Query("SELECT * FROM memoryentity WHERE assistant_id = :assistantId AND conversation_id = :conversationId")
    fun getMemoriesOfConversationFlow(assistantId: String, conversationId: String): Flow<List<MemoryEntity>>

    @Query("SELECT * FROM memoryentity WHERE assistant_id = :assistantId AND conversation_id = :conversationId")
    suspend fun getMemoriesOfConversation(assistantId: String, conversationId: String): List<MemoryEntity>

    // rhShortMem: 该助手名下全部短期记忆(管理页按会话分组用)
    @Query("SELECT * FROM memoryentity WHERE assistant_id = :assistantId AND conversation_id != ''")
    fun getSessionMemoriesOfAssistantFlow(assistantId: String): Flow<List<MemoryEntity>>

    @Query("SELECT * FROM memoryentity")
    fun getAllMemoriesFlow(): Flow<List<MemoryEntity>>

    @Query("SELECT * FROM memoryentity")
    suspend fun getAllMemories(): List<MemoryEntity>

    @Query("SELECT * FROM memoryentity WHERE id = :id")
    suspend fun getMemoryById(id: Int): MemoryEntity?

    @Insert
    suspend fun insertMemory(memory: MemoryEntity): Long

    @Update
    suspend fun updateMemory(memory: MemoryEntity)

    @Query("DELETE FROM memoryentity WHERE id = :id")
    suspend fun deleteMemory(id: Int)

    @Query("DELETE FROM memoryentity WHERE assistant_id = :assistantId")
    suspend fun deleteMemoriesOfAssistant(assistantId: String)
}

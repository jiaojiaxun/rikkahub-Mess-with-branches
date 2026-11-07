package me.rerere.rikkahub.data.repository

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import me.rerere.rikkahub.data.db.dao.MemoryDAO
import me.rerere.rikkahub.data.db.entity.MemoryEntity
import me.rerere.rikkahub.data.model.AssistantMemory

class MemoryRepository(private val memoryDAO: MemoryDAO) {
    companion object {
        const val GLOBAL_MEMORY_ID = "__global__"
    }

    fun getMemoriesOfAssistantFlow(assistantId: String): Flow<List<AssistantMemory>> =
        memoryDAO.getMemoriesOfAssistantFlow(assistantId)
            .map { entities ->
                entities.map { AssistantMemory(it.id, it.content, it.conversationId) }
            }

    suspend fun getMemoriesOfAssistant(assistantId: String): List<AssistantMemory> {
        return memoryDAO.getMemoriesOfAssistant(assistantId)
            .map { AssistantMemory(it.id, it.content, it.conversationId) }
    }

    fun getGlobalMemoriesFlow(): Flow<List<AssistantMemory>> =
        memoryDAO.getMemoriesOfAssistantFlow(GLOBAL_MEMORY_ID)
            .map { entities ->
                entities.map { AssistantMemory(it.id, it.content, it.conversationId) }
            }

    suspend fun getGlobalMemories(): List<AssistantMemory> {
        return memoryDAO.getMemoriesOfAssistant(GLOBAL_MEMORY_ID)
            .map { AssistantMemory(it.id, it.content, it.conversationId) }
    }

    suspend fun deleteMemoriesOfAssistant(assistantId: String) {
        memoryDAO.deleteMemoriesOfAssistant(assistantId)
    }

    suspend fun updateContent(id: Int, content: String): AssistantMemory {
        val old = memoryDAO.getMemoryById(id) ?: error("Memory record #$id not found")
        val newMemory = old.copy(
            content = content
        )
        memoryDAO.updateMemory(newMemory)
        return AssistantMemory(
            id = newMemory.id,
            content = newMemory.content,
            conversationId = newMemory.conversationId,
        )
    }

    suspend fun addMemory(assistantId: String, content: String, conversationId: String = ""): AssistantMemory {
        val memory = AssistantMemory(
            id = 0,
            content = content,
            conversationId = conversationId,
        )
        val newMemory = memory.copy(
            id = memoryDAO.insertMemory(
                MemoryEntity(
                    assistantId = assistantId,
                    content = memory.content,
                    conversationId = conversationId,
                )
            ).toInt()
        )
        return newMemory
    }

    // rhShortMem: 单个会话的短期记忆
    fun getMemoriesOfConversationFlow(assistantId: String, conversationId: String): Flow<List<AssistantMemory>> =
        memoryDAO.getMemoriesOfConversationFlow(assistantId, conversationId)
            .map { entities ->
                entities.map { AssistantMemory(it.id, it.content, it.conversationId) }
            }

    suspend fun getMemoriesOfConversation(assistantId: String, conversationId: String): List<AssistantMemory> {
        return memoryDAO.getMemoriesOfConversation(assistantId, conversationId)
            .map { AssistantMemory(it.id, it.content, it.conversationId) }
    }

    // rhShortMem: 该助手名下全部短期记忆(管理页按会话分组用)
    fun getSessionMemoriesOfAssistantFlow(assistantId: String): Flow<List<AssistantMemory>> =
        memoryDAO.getSessionMemoriesOfAssistantFlow(assistantId)
            .map { entities ->
                entities.map { AssistantMemory(it.id, it.content, it.conversationId) }
            }

    suspend fun deleteMemory(id: Int) {
        memoryDAO.deleteMemory(id)
    }
}

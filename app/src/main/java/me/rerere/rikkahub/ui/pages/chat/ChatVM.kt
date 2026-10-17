package me.rerere.rikkahub.ui.pages.chat

import android.app.Application
import android.content.Context
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.tooling.preview.Preview
import androidx.core.net.toUri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import me.rerere.ai.provider.Model
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart
import me.rerere.ai.ui.isEmptyInputMessage
import me.rerere.rikkahub.R
import me.rerere.rikkahub.data.datastore.Settings
import me.rerere.rikkahub.data.datastore.SettingsStore
import me.rerere.rikkahub.data.export.SharedConversationCodec
import me.rerere.rikkahub.data.datastore.getAssistantById
import me.rerere.rikkahub.data.datastore.getCurrentAssistant
import me.rerere.rikkahub.data.datastore.getCurrentChatModel
import me.rerere.rikkahub.data.files.FilesManager
import me.rerere.rikkahub.data.model.Assistant
import me.rerere.rikkahub.data.model.Avatar
import me.rerere.rikkahub.data.model.Conversation
import me.rerere.rikkahub.data.translation.TranslationMode
import me.rerere.rikkahub.data.model.MessageNode
import me.rerere.rikkahub.data.model.NodeFavoriteTarget
import me.rerere.rikkahub.data.repository.ConversationRepository
import me.rerere.rikkahub.data.repository.FavoriteRepository
import me.rerere.rikkahub.service.ChatError
import me.rerere.rikkahub.service.ChatService
import me.rerere.rikkahub.ui.hooks.writeStringPreference
import me.rerere.rikkahub.ui.hooks.ChatInputState
import me.rerere.rikkahub.utils.UiState
import me.rerere.rikkahub.utils.UpdateChecker
import java.util.Locale
import kotlin.uuid.Uuid

private const val TAG = "ChatVM"

class ChatVM(
    id: String,
    private val context: Application,
    private val settingsStore: SettingsStore,
    private val conversationRepo: ConversationRepository,
    private val chatService: ChatService,
    val updateChecker: UpdateChecker,
    private val filesManager: FilesManager,
    private val favoriteRepository: FavoriteRepository,
) : ViewModel() {
    private val _conversationId: Uuid = Uuid.parse(id)
    val conversation: StateFlow<Conversation> = chatService.getConversationFlow(_conversationId)
    var chatListInitialized by mutableStateOf(false) // 聊天列表是否已经滚动到底部

    // 聊天输入状态 - 保存在 ViewModel 中避免 TransactionTooLargeException
    val inputState = ChatInputState()

    // 任务N4 v3：消息排队发送——触发生成的消息统一入队，单一 pump 串行放行，
    // 避免生成期间并发 sendMessage。队列仅存内存（VM 生命周期）。
    private val pendingMessages = java.util.concurrent.ConcurrentLinkedQueue<List<me.rerere.ai.ui.UIMessagePart>>()
    private val pendingMessageCountState = androidx.compose.runtime.mutableStateOf(0)
    val pendingMessageCount: androidx.compose.runtime.State<Int> = pendingMessageCountState
    private val pendingPumpMutex = Mutex()

    init {
        // 本会话生成完成 → 尝试放行下一条（generationDoneFlow 是全局流，
        // 发出的是 conversationId，必须过滤，否则跨会话误触发）
        viewModelScope.launch {
            chatService.generationDoneFlow.collect { doneConversationId ->
                if (doneConversationId == _conversationId) {
                    drainOnePendingMessage()
                }
            }
        }
    }

    /** 放行一条排队消息：等本会话空闲后发送（读服务端真相流，无 stateIn 竞态）。 */
    private fun drainOnePendingMessage() {
        viewModelScope.launch {
            pendingPumpMutex.withLock {
                if (pendingMessages.isEmpty()) return@withLock
                chatService.getGenerationJobStateFlow(_conversationId).first { it == null }
                val next = pendingMessages.poll() ?: return@withLock
                pendingMessageCountState.value = pendingMessages.size
                chatService.sendMessage(_conversationId, next, true)
            }
        }
    }

    // 异步任务 (从ChatService获取，响应式)
    val conversationJob: StateFlow<Job?> =
        chatService
            .getGenerationJobStateFlow(_conversationId)
            .stateIn(viewModelScope, SharingStarted.Eagerly, null)

    val processingStatus: StateFlow<String?> =
        chatService
            .getProcessingStatusFlow(_conversationId)

    val conversationJobs = chatService
        .getConversationJobs()
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptyMap())

    init {
        // 添加对话引用
        chatService.addConversationReference(_conversationId)
        // rhTavernMode: 从独立 Store 读当前会话的酒馆状态,交给输入组件
        inputState.tavernMode = me.rerere.rikkahub.data.datastore.TavernModeStore.isEnabled(context, _conversationId.toString())
        inputState.onToggleTavernMode = { enabled -> setTavernMode(enabled) }
        // rhSqueezeWire: 榨干 token 接线(会话级)
        inputState.squeezeTokenEnabled = me.rerere.rikkahub.data.datastore.TavernModeStore.isSqueezeTokenEnabled(context, _conversationId.toString())
        inputState.onToggleSqueezeToken = { enabled -> setSqueezeTokenMode(enabled) }

        // 初始化对话
        viewModelScope.launch {
            chatService.initializeConversation(_conversationId)
        }

        // 记住对话ID, 方便下次启动恢复
        context.writeStringPreference("lastConversationId", _conversationId.toString())
    }

    override fun onCleared() {
        super.onCleared()
        // 移除对话引用
        chatService.removeConversationReference(_conversationId)
    }

    // 用户设置
    val settings: StateFlow<Settings> =
        settingsStore.settingsFlow.stateIn(viewModelScope, SharingStarted.Eagerly, Settings.dummy())

    // 网络搜索(每个助手独立)
    val enableWebSearch = settings.map {
        it.getCurrentAssistant().enableWebSearch
    }.stateIn(viewModelScope, SharingStarted.Eagerly, false)

    // 当前模型
    val currentChatModel = settings.map { settings ->
        settings.getCurrentChatModel()
    }.stateIn(viewModelScope, SharingStarted.Lazily, null)

    // 错误状态
    val errors: StateFlow<List<ChatError>> = chatService.errors

    fun dismissError(id: Uuid) = chatService.dismissError(id)

    fun clearAllErrors() = chatService.clearAllErrors()

    // 生成完成
    val generationDoneFlow: SharedFlow<Uuid> = chatService.generationDoneFlow

    // MCP管理器
    val mcpManager = chatService.mcpManager

    // 更新设置
    fun updateSettings(newSettings: Settings): Job {
        return viewModelScope.launch {
            val oldSettings = settings.value
            // 检查用户头像是否有变化，如果有则删除旧头像
            checkUserAvatarDelete(oldSettings, newSettings)
            settingsStore.update(newSettings)
        }
    }

    // 检查用户头像删除
    private fun checkUserAvatarDelete(oldSettings: Settings, newSettings: Settings) {
        val oldAvatar = oldSettings.displaySetting.userAvatar
        val newAvatar = newSettings.displaySetting.userAvatar

        if (oldAvatar is Avatar.Image && oldAvatar != newAvatar) {
            filesManager.deleteChatFiles(listOf(oldAvatar.url.toUri()))
        }
    }

    // 设置聊天模型
    fun setChatModel(assistant: Assistant, model: Model) {
        viewModelScope.launch {
            // [batch234] A4: 写当前会话自己的 config.chatModelId, 不动助手(会话级)
            chatService.setConversationModel(_conversationId, model.id)
        }
    }

    // Update checker
    val updateState = settingsStore.settingsFlow
        .map { settings ->
            !settings.init &&
                settings.displaySetting.updateCheckDisabledUntilEpochMillis <= System.currentTimeMillis()
        }
        .distinctUntilChanged()
        .flatMapLatest { enabled ->
            if (enabled) updateChecker.checkUpdate() else flowOf(UiState.Loading)
        }
        .stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(stopTimeoutMillis = 5_000),
            UiState.Loading,
        )

    /**
     * 处理消息发送
     *
     * @param content 消息内容
     * @param answer 是否触发消息生成，如果为false，则仅添加消息到消息列表中
     */
        fun handleMessageSend(content: List<UIMessagePart>,answer: Boolean = true, quotedMessageId: Uuid? = null) {
        if (content.isEmptyInputMessage()) return
        // answer=false 的插入型消息不排队直接执行；触发生成的统一入队，
        // 由 drainOnePendingMessage 串行放行（cap 20，超出丢弃防内存膨胀）
        if (!answer) {
            chatService.sendMessage(_conversationId, content, false, quotedMessageId)
            return
        }
        if (pendingMessages.size >= 20) return
        pendingMessages.add(content)
        pendingMessageCountState.value = pendingMessages.size
        drainOnePendingMessage()
    }

    /** 丢弃全部排队消息（用户在排队时点停止生成）。 */
    fun clearPendingMessages() {
        pendingMessages.clear()
        pendingMessageCountState.value = 0
    }

    suspend fun importSharedConversation(text: String): Conversation {
        val incoming = SharedConversationCodec.decode(text)
        val currentSettings = settingsStore.settingsFlow.first()
        val assistantId = currentSettings.getAssistantById(incoming.assistantId)?.id
            ?: currentSettings.getCurrentAssistant().id
        val imported = incoming.copy(
            id = Uuid.random(),
            assistantId = assistantId,
            chatModelId = null,
            folderId = null,
            messageNodes = incoming.messageNodes.map { node ->
                node.copy(id = Uuid.random())
            },
        )
        conversationRepo.insertConversation(imported)
        return imported
    }


    fun handleMessageEdit(parts: List<UIMessagePart>, messageId: Uuid) {
        if (parts.isEmptyInputMessage()) return

        viewModelScope.launch {
            chatService.editMessage(_conversationId, messageId, parts)
        }
    }

        fun handleCompressContext(additionalPrompt: String, targetTokens: Int, keepRecentMessages: Int): Job {
        return chatService.compressConversationAsync(
            conversationId = _conversationId,
            conversation = conversation.value,
            additionalPrompt = additionalPrompt,
            targetTokens = targetTokens,
            keepRecentMessages = keepRecentMessages,
        )
    }

    /**
     * rh-batch8:truncate-only - delete the older messages instead of summarising them.
     * No compression model is contacted, so this cannot hang or produce repeated requests.
     */
    fun handleTruncateContext(keepRecentMessages: Int): Job {
        return chatService.truncateConversationToRecentAsync(
            conversationId = _conversationId,
            keepRecentMessages = keepRecentMessages,
        )
    }

    suspend fun forkMessage(message: UIMessage): Conversation {
        return chatService.forkConversationAtMessage(_conversationId, message.id)
    }

    fun deleteMessage(message: UIMessage) {
        viewModelScope.launch {
            chatService.deleteMessage(_conversationId, message)
        }
    }

    fun showDeleteBlockedWhileGeneratingError() {
        chatService.addError(
            error = IllegalStateException(context.getString(R.string.chat_stop_generation_before_delete)),
            conversationId = _conversationId,
            title = context.getString(R.string.error_title_operation)
        )
    }

    fun regenerateAtMessage(
        message: UIMessage,
        regenerateAssistantMsg: Boolean = true
    ) {
        chatService.regenerateAtMessage(_conversationId, message, regenerateAssistantMsg)
    }

    /** Re-run the latest failed turn and replace its assistant tail in place. */
    fun retryLastTurnOverwrite() {
        chatService.retryLastTurnOverwrite(_conversationId)
    }

    fun handleToolApproval(
        toolCallId: String,
        approved: Boolean,
        reason: String = "",
        scope: me.rerere.rikkahub.service.ChatService.ApprovalScope =
            me.rerere.rikkahub.service.ChatService.ApprovalScope.Once,
        toolName: String? = null,
    ) {
        chatService.handleToolApproval(
            conversationId = _conversationId,
            toolCallId = toolCallId,
            approved = approved,
            reason = reason,
            scope = scope,
            toolName = toolName,
        )
    }

    fun handleToolAnswer(
        toolCallId: String,
        answer: String,
    ) {
        chatService.handleToolApproval(_conversationId, toolCallId, approved = true, answer = answer)
    }

    suspend fun rerunTool(toolCallId: String): me.rerere.rikkahub.service.ChatService.RerunToolResult =
        chatService.rerunTool(_conversationId, toolCallId)

    fun stopGeneration() {
        // 任务N4：停止生成同时丢弃排队消息，避免停止后队列被 done 事件自动放行
        clearPendingMessages()
        viewModelScope.launch {
            chatService.stopGeneration(_conversationId)
        }
    }

    fun saveConversationAsync() {
        viewModelScope.launch {
            chatService.saveConversation(_conversationId, conversation.value)
        }
    }

    fun updateTitle(title: String) {
        viewModelScope.launch {
            val updatedConversation = conversation.value.copy(title = title)
            chatService.saveConversation(_conversationId, updatedConversation)
        }
    }

    fun deleteConversation(conversation: Conversation): Job =
        viewModelScope.launch {
            conversationRepo.deleteConversation(conversation)
        }

    fun updatePinnedStatus(conversation: Conversation) {
        viewModelScope.launch {
            conversationRepo.togglePinStatus(conversation.id)
        }
    }

    fun moveConversationToAssistant(conversation: Conversation, targetAssistantId: Uuid) {
        viewModelScope.launch {
            val conversationFull = conversationRepo.getConversationById(conversation.id) ?: return@launch
            // Folders are per-assistant groupings; after switching assistant the old folder is
            // not visible under the new one, so clear the assignment to avoid losing the chat.
            val updatedConversation = conversationFull.copy(
                assistantId = targetAssistantId,
                folderId = null,
            )
            // Drop any "Allow for this chat" grants the user gave the previous assistant.
            // The grants apply to a tool surface the new assistant may use very differently
            // (different prompt, different tool list), and the user authorised them under
            // the old persona's behaviour, not this one's. Persistent "Always Allow" grants
            // stay (they were granted globally) but ChatScope is reset.
            me.rerere.rikkahub.data.ai.tools.ToolApprovalAllowList.clearChat(conversation.id)
            if (conversation.id == _conversationId) {
                chatService.saveConversation(_conversationId, updatedConversation)
                settingsStore.updateAssistant(targetAssistantId)
            } else {
                conversationRepo.updateConversation(updatedConversation)
            }
        }
    }

    fun translateMessage(
        message: UIMessage,
        targetLanguage: Locale,
        mode: TranslationMode = TranslationMode.AI,
    ) {
        chatService.translateMessage(_conversationId, message, targetLanguage, mode)
    }

    fun generateTitle(conversation: Conversation, force: Boolean = false) {
        viewModelScope.launch {
            val conversationFull = conversationRepo.getConversationById(conversation.id) ?: return@launch
            chatService.generateTitle(_conversationId, conversationFull, force)
        }
    }

    fun generateSuggestion(conversation: Conversation) {
        viewModelScope.launch {
            chatService.generateSuggestion(_conversationId, conversation)
        }
    }

    fun clearTranslationField(messageId: Uuid) {
        chatService.clearTranslationField(_conversationId, messageId)
    }

    fun updateConversation(newConversation: Conversation) {
        chatService.updateConversationState(_conversationId) {
            newConversation
        }
    }

    /** rhTavernMode: 会话级酒馆模式开关(只影响当前会话,不改助手)。 */
    fun setTavernMode(enabled: Boolean) {
        inputState.tavernMode = enabled
        me.rerere.rikkahub.data.datastore.TavernModeStore.setEnabled(context, _conversationId.toString(), enabled)
    }

    /** rhSqueezeWire: 榨干 token 开关(会话级,自动续跑)。 */
    fun setSqueezeTokenMode(enabled: Boolean) {
        inputState.squeezeTokenEnabled = enabled
        me.rerere.rikkahub.data.datastore.TavernModeStore.setSqueezeTokenEnabled(context, _conversationId.toString(), enabled)
    }

    fun toggleMessageFavorite(node: MessageNode) {
        viewModelScope.launch {
            val currentlyFavorited = favoriteRepository.isNodeFavorited(_conversationId, node.id)
            if (currentlyFavorited) {
                favoriteRepository.removeNodeFavorite(_conversationId, node.id)
            } else {
                favoriteRepository.addNodeFavorite(
                    NodeFavoriteTarget(
                        conversationId = _conversationId,
                        conversationTitle = conversation.value.title,
                        nodeId = node.id,
                        node = node
                    )
                )
            }

            chatService.updateConversationState(_conversationId) { currentConversation ->
                currentConversation.copy(
                    messageNodes = currentConversation.messageNodes.map { existingNode ->
                        if (existingNode.id == node.id) {
                            existingNode.copy(isFavorite = !currentlyFavorited)
                        } else {
                            existingNode
                        }
                    }
                )
            }
        }
    }

}

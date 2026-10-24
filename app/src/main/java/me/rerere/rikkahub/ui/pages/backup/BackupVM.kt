package me.rerere.rikkahub.ui.pages.backup

import android.util.Log
import androidx.lifecycle.ViewModel
import androidx.core.net.toUri
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import me.rerere.rikkahub.data.datastore.Settings
import me.rerere.rikkahub.data.datastore.SettingsStore
import me.rerere.rikkahub.AppScope
import me.rerere.rikkahub.data.files.FileFolders
import me.rerere.rikkahub.data.files.FilesManager
import me.rerere.rikkahub.data.datastore.WebDavConfig
import me.rerere.rikkahub.data.repository.ConversationRepository
import me.rerere.rikkahub.data.sync.BackupExportFormat
import me.rerere.rikkahub.data.sync.BackupProgress
import me.rerere.rikkahub.data.sync.BackupRestoreMode
import me.rerere.rikkahub.data.sync.importer.ChatboxImporter
import me.rerere.rikkahub.data.sync.importer.CherryStudioProviderImporter
import me.rerere.rikkahub.data.sync.webdav.WebDavBackupItem
import me.rerere.rikkahub.data.sync.webdav.WebDavSync
import me.rerere.rikkahub.data.sync.merge.ConversationMergeDecision
import me.rerere.rikkahub.data.sync.merge.SettingsItemKind
import me.rerere.rikkahub.data.sync.merge.ConversationMergeRelation
import me.rerere.rikkahub.data.sync.merge.MergePlan
import me.rerere.rikkahub.data.sync.merge.SettingsItemCategory
import me.rerere.rikkahub.data.sync.merge.SettingsItemDecision
import me.rerere.rikkahub.data.sync.webdav.StagedMergeBackup
import me.rerere.rikkahub.data.sync.S3BackupItem
import me.rerere.rikkahub.data.sync.S3Sync
import me.rerere.rikkahub.utils.UiState
import java.io.File

private const val TAG = "BackupVM"

class BackupVM(
    private val settingsStore: SettingsStore,
    private val webDavSync: WebDavSync,
    private val s3Sync: S3Sync,
    private val conversationRepository: ConversationRepository,
    private val filesManager: FilesManager,
    private val appScope: AppScope,  // rhBgBackup
) : ViewModel() {
    val settings = settingsStore.settingsFlow.stateIn(
        scope = viewModelScope,
        started = SharingStarted.Eagerly,
        initialValue = Settings.dummy()
    )

    val webDavBackupItems = MutableStateFlow<UiState<List<WebDavBackupItem>>>(UiState.Idle)
    val s3BackupItems = MutableStateFlow<UiState<List<S3BackupItem>>>(UiState.Idle)
    val progress = MutableStateFlow<BackupProgress?>(null)
    val isBackingUp = MutableStateFlow(false)  // rhBgBackup

    fun reportProgress(value: BackupProgress?) {
        progress.value = value
    }

    init {
        loadBackupFileItems()
        loadS3BackupFileItems()
    }

    fun updateSettings(settings: Settings) {
        viewModelScope.launch {
            settingsStore.update(settings)
        }
    }

    fun loadBackupFileItems() {
        viewModelScope.launch {
            runCatching {
                webDavBackupItems.emit(UiState.Loading)
                webDavBackupItems.emit(
                    value = UiState.Success(
                        data = webDavSync.listBackupFiles(
                            config = settings.value.webDavConfig
                        ).sortedByDescending { it.lastModified }
                    )
                )
            }.onFailure {
                webDavBackupItems.emit(UiState.Error(it))
            }
        }
    }

    suspend fun testWebDav() {
        webDavSync.testConnection(settings.value.webDavConfig)
    }

    fun backup() {  // rhBgBackup: 改用 AppScope,切页面继续传
        isBackingUp.value = true
        appScope.launch {
            try {
                runWithProgress { report ->
                    webDavSync.backup(settings.value.webDavConfig, report)
                }
                recordBackupTime()
            } finally {
                isBackingUp.value = false
            }
        }
    }

    fun restore(
        item: WebDavBackupItem,
        mode: BackupRestoreMode = BackupRestoreMode.OVERWRITE,
    ) {  // rhBgBackup
        isBackingUp.value = true
        appScope.launch {
            try {
                runWithProgress { report ->
                    webDavSync.restore(config = settings.value.webDavConfig, item = item, mode = mode, onProgress = report)
                }
            } finally {
                isBackingUp.value = false
            }
        }
    }

    suspend fun deleteWebDavBackupFile(item: WebDavBackupItem) {
        webDavSync.deleteBackupFile(settings.value.webDavConfig, item)
    }

    suspend fun exportToFile(format: BackupExportFormat = BackupExportFormat.FULL): File {
        val file = runWithProgress { report ->
            webDavSync.prepareBackupFile(
                settings.value.webDavConfig.copy(items = WebDavConfig.BackupItem.entries),
                report,
                format = format,
            )
        }
        recordBackupTime()
        return file
    }

    suspend fun restoreFromLocalFile(
        file: File,
        mode: BackupRestoreMode = BackupRestoreMode.OVERWRITE,
    ) {
        runWithProgress { report ->
            webDavSync.restoreFromLocalFile(
                file,
                settings.value.webDavConfig.copy(items = WebDavConfig.BackupItem.entries),
                mode = mode,
                onProgress = report,
            )
        }
    }

    suspend fun restoreFromChatBox(file: File): ChatboxRestoreResult {
        var importedConversations = 0
        var skippedExistingConversations = 0
        val result = ChatboxImporter.importStreaming(
            file = file,
            assistantId = settings.value.assistantId,
            providers = settings.value.providers,
            saveImage = { image ->
                val safeName = image.fileName
                    .substringAfterLast('/')
                    .replace(Regex("[^A-Za-z0-9._-]"), "_")
                    .ifBlank { "chatbox_image" }
                    .take(120)
                val entity = filesManager.saveManagedFromBytes(
                    folder = FileFolders.IMAGES,
                    bytes = image.bytes,
                    displayName = safeName,
                    mimeType = image.mimeType,
                )
                filesManager.getFile(entity).toUri().toString()
            },
            onConversation = { conversation ->
                if (conversationRepository.existsConversationById(conversation.id)) {
                    skippedExistingConversations++
                } else {
                    conversationRepository.insertConversation(conversation)
                    importedConversations++
                }
            }
        )

        val targetAssistantId = settings.value.assistantId
        settingsStore.update(
            settings.value.copy(
                providers = result.providers + settings.value.providers,
                assistants = settings.value.assistants.map { assistant ->
                    if (result.hasConversationSystemPrompt && assistant.id == targetAssistantId) {
                        assistant.copy(allowConversationSystemPrompt = true)
                    } else {
                        assistant
                    }
                }
            )
        )

        Log.i(
            TAG,
            "restoreFromChatBox: import ${result.providers.size} providers, " +
                "$importedConversations conversations, skip $skippedExistingConversations existing, " +
                "drop ${result.skippedImageParts} images"
        )
        return ChatboxRestoreResult(
            importedProviders = result.providers.size,
            importedConversations = importedConversations,
            skippedExistingConversations = skippedExistingConversations,
            skippedImageParts = result.skippedImageParts,
            skippedEmptyMessages = result.skippedEmptyMessages,
        )
    }

    fun restoreFromCherryStudio(file: File) {
        val importProviders = CherryStudioProviderImporter.importProviders(file)

        if (importProviders.isEmpty()) {
            throw IllegalArgumentException("No importable providers found in Cherry Studio backup")
        }

        Log.i(TAG, "restoreFromCherryStudio: import ${importProviders.size} providers: $importProviders")

        updateSettings(
            settings.value.copy(
                providers = importProviders + settings.value.providers,
            )
        )
    }

    // S3 Backup methods
    fun loadS3BackupFileItems() {
        viewModelScope.launch {
            runCatching {
                s3BackupItems.emit(UiState.Loading)
                s3BackupItems.emit(
                    value = UiState.Success(
                        data = s3Sync.listBackupFiles(
                            config = settings.value.s3Config
                        )
                    )
                )
            }.onFailure {
                s3BackupItems.emit(UiState.Error(it))
            }
        }
    }

    suspend fun testS3() {
        s3Sync.testS3(settings.value.s3Config)
    }

    fun backupToS3() {  // rhBgBackup
        isBackingUp.value = true
        appScope.launch {
            try {
                runWithProgress { report ->
                    s3Sync.backupToS3(settings.value.s3Config, report)
                }
                recordBackupTime()
            } finally {
                isBackingUp.value = false
            }
        }
    }

    fun restoreFromS3(
        item: S3BackupItem,
        mode: BackupRestoreMode = BackupRestoreMode.OVERWRITE,
    ) {  // rhBgBackup
        isBackingUp.value = true
        appScope.launch {
            try {
                runWithProgress { report ->
                    s3Sync.restoreFromS3(
                        config = settings.value.s3Config,
                        item = item,
                        mode = mode,
                        onProgress = report,
                    )
                }
            } finally {
                isBackingUp.value = false
            }
        }
    }

    suspend fun deleteS3BackupFile(item: S3BackupItem) {
        s3Sync.deleteS3BackupFile(settings.value.s3Config, item)
    }


    // ------------------------------------------------------------ [batch156] 两阶段合并状态机

    sealed interface MergeUiState {
        data object Idle : MergeUiState
        data object Preparing : MergeUiState
        data class AwaitingDecision(val plan: MergePlan) : MergeUiState
        data object Applying : MergeUiState
        data class Done(val summary: String) : MergeUiState
        data class Failed(val message: String) : MergeUiState
    }

    val mergeUiState = MutableStateFlow<MergeUiState>(MergeUiState.Idle)

    private data class PendingMerge(
        val staged: StagedMergeBackup,
        val plan: MergePlan,
        val sourceFile: File?,
    )

    private var pendingMerge: PendingMerge? = null

    /** 本地文件：选"合并"后的入口。 */
    fun beginLocalMerge(file: File) {
        viewModelScope.launch {
            mergeUiState.value = MergeUiState.Preparing
            runCatching {
                webDavSync.beginMergeRestore(
                    file,
                    settings.value.webDavConfig.copy(items = WebDavConfig.BackupItem.entries),
                ) { p -> reportProgress(p) }
            }.onSuccess { (staged, plan) ->
                pendingMerge = PendingMerge(staged, plan, file)
                mergeUiState.value = MergeUiState.AwaitingDecision(plan)
            }.onFailure { error ->
                file.delete()
                mergeUiState.value = MergeUiState.Failed(error.message ?: "备份扫描失败")
            }
            reportProgress(null)
        }
    }

    /** WebDAV：选"合并"后的入口（先下载再扫描）。 */
    fun beginWebDavMerge(item: WebDavBackupItem) {
        viewModelScope.launch {
            mergeUiState.value = MergeUiState.Preparing
            var downloaded: File? = null
            runCatching {
                val f = webDavSync.downloadBackupForMerge(settings.value.webDavConfig, item) { p -> reportProgress(p) }
                downloaded = f
                webDavSync.beginMergeRestore(f, settings.value.webDavConfig) { p -> reportProgress(p) }
            }.onSuccess { (staged, plan) ->
                pendingMerge = PendingMerge(staged, plan, downloaded)
                mergeUiState.value = MergeUiState.AwaitingDecision(plan)
            }.onFailure { error ->
                downloaded?.delete()
                mergeUiState.value = MergeUiState.Failed(error.message ?: "备份扫描失败")
            }
            reportProgress(null)
        }
    }

    /** S3：选"合并"后的入口（先下载再扫描）。 */
    fun beginS3Merge(item: S3BackupItem) {
        viewModelScope.launch {
            mergeUiState.value = MergeUiState.Preparing
            var downloaded: File? = null
            runCatching {
                val f = s3Sync.downloadBackupForMerge(settings.value.s3Config, item) { p -> reportProgress(p) }
                downloaded = f
                webDavSync.beginMergeRestore(
                    f,
                    settings.value.webDavConfig.copy(items = WebDavConfig.BackupItem.entries),
                ) { p -> reportProgress(p) }
            }.onSuccess { (staged, plan) ->
                pendingMerge = PendingMerge(staged, plan, downloaded)
                mergeUiState.value = MergeUiState.AwaitingDecision(plan)
            }.onFailure { error ->
                downloaded?.delete()
                mergeUiState.value = MergeUiState.Failed(error.message ?: "备份扫描失败")
            }
            reportProgress(null)
        }
    }

    fun updateConversationDecision(conversationId: String, decision: ConversationMergeDecision) {
        val state = mergeUiState.value as? MergeUiState.AwaitingDecision ?: return
        mergeUiState.value = state.copy(
            plan = state.plan.copy(
                conversations = state.plan.conversations.map { item ->
                    if (item.conversationId == conversationId) item.copy(decision = decision) else item
                },
            ),
        )
    }

    fun updateSettingsItemDecision(category: SettingsItemCategory, id: String, decision: SettingsItemDecision) {
        val state = mergeUiState.value as? MergeUiState.AwaitingDecision ?: return
        val settingsDiff = state.plan.settings ?: return
        mergeUiState.value = state.copy(
            plan = state.plan.copy(
                settings = settingsDiff.copy(
                    items = settingsDiff.items.map { item ->
                        if (item.category == category && item.id == id) item.copy(decision = decision) else item
                    },
                ),
            ),
        )
    }

    fun toggleScalarAdoption(fieldKey: String) {
        val state = mergeUiState.value as? MergeUiState.AwaitingDecision ?: return
        val settingsDiff = state.plan.settings ?: return
        mergeUiState.value = state.copy(
            plan = state.plan.copy(
                settings = settingsDiff.copy(
                    scalarFields = settingsDiff.scalarFields.map { field ->
                        if (field.fieldKey == fieldKey) field.copy(adoptBackup = !field.adoptBackup) else field
                    },
                ),
            ),
        )
    }


    /** [batch216] 一键全部采用备份（对话+设置条目+标量偏好都用备份侧），之后仍可逐项微调。 */
    fun mergeAllUseBackup() {
        val state = mergeUiState.value as? MergeUiState.AwaitingDecision ?: return
        val plan = state.plan
        val convs = plan.conversations.map { item ->
            val d = when (item.relation) {
                ConversationMergeRelation.NEW -> ConversationMergeDecision.IMPORT
                ConversationMergeRelation.SAME -> ConversationMergeDecision.KEEP_LOCAL
                else -> ConversationMergeDecision.USE_BACKUP
            }
            item.copy(decision = d)
        }
        val settings = plan.settings?.let { s ->
            s.copy(
                items = s.items.map { item ->
                    item.copy(decision = when (item.kind) {
                        SettingsItemKind.ADDED_IN_BACKUP -> SettingsItemDecision.IMPORT
                        SettingsItemKind.DELETED_LOCALLY -> SettingsItemDecision.IMPORT
                        SettingsItemKind.REMOVED_IN_BACKUP -> SettingsItemDecision.DELETE
                        SettingsItemKind.MODIFIED -> SettingsItemDecision.USE_BACKUP
                    })
                },
                scalarFields = s.scalarFields.map { it.copy(adoptBackup = true) },
            )
        }
        mergeUiState.value = state.copy(plan = plan.copy(conversations = convs, settings = settings))
    }

    /** [batch216] 一键全部保留本地（重置为扫描时的默认决策）。 */
    fun mergeAllKeepLocal() {
        val state = mergeUiState.value as? MergeUiState.AwaitingDecision ?: return
        val plan = state.plan
        val convs = plan.conversations.map { it.copy(decision = it.defaultDecision) }
        val settings = plan.settings?.let { s ->
            s.copy(
                items = s.items.map { it.copy(decision = it.defaultDecision) },
                scalarFields = s.scalarFields.map { it.copy(adoptBackup = false) },
            )
        }
        mergeUiState.value = state.copy(plan = plan.copy(conversations = convs, settings = settings))
    }
    fun confirmMerge() {
        val pending = pendingMerge ?: return
        val state = mergeUiState.value as? MergeUiState.AwaitingDecision ?: return
        viewModelScope.launch {
            mergeUiState.value = MergeUiState.Applying
            runCatching {
                webDavSync.applyMergeRestore(pending.staged, state.plan) { p -> reportProgress(p) }
            }.onSuccess { result ->
                mergeUiState.value = MergeUiState.Done(result.summary())
            }.onFailure { error ->
                mergeUiState.value = MergeUiState.Failed(error.message ?: "合并失败")
            }
            pending.sourceFile?.delete()
            pendingMerge = null
            reportProgress(null)
        }
    }

    fun cancelMerge() {
        pendingMerge?.let { pending ->
            runCatching { webDavSync.discardMergeRestore(pending.staged) }
            pending.sourceFile?.delete()
        }
        pendingMerge = null
        mergeUiState.value = MergeUiState.Idle
        reportProgress(null)
    }

    override fun onCleared() {
        pendingMerge?.let { pending ->
            runCatching { webDavSync.discardMergeRestore(pending.staged) }
            pending.sourceFile?.delete()
        }
        pendingMerge = null
        super.onCleared()
    }

    private suspend fun <T> runWithProgress(block: suspend ((BackupProgress) -> Unit) -> T): T {
        val first = BackupProgress("准备操作", detail = "正在开始")
        progress.value = first
        return try {
            block { value -> progress.value = value }
        } finally {
            progress.value = null
        }
    }

    private suspend fun recordBackupTime() {
        settingsStore.update { settings ->
            settings.copy(
                backupReminderConfig = settings.backupReminderConfig.copy(
                    lastBackupTime = System.currentTimeMillis()
                )
            )
        }
    }
}

data class ChatboxRestoreResult(
    val importedProviders: Int,
    val importedConversations: Int,
    val skippedExistingConversations: Int,
    val skippedImageParts: Int,
    val skippedEmptyMessages: Int,
)

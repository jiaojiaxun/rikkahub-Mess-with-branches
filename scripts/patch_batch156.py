#!/usr/bin/env python3
# batch156: 备份合并改造 7/10 —— WebDavSync / S3Sync / BackupVM 两阶段接线
# 变更:
#   1) WebDavSync.kt: +2 import; resolveCacheFile 前插入
#      downloadBackupForMerge / beginMergeRestore / applyMergeRestore / discardMergeRestore
#   2) S3Sync.kt: toWebDavConfig 前插入 downloadBackupForMerge
#   3) BackupVM.kt: +5 import; runWithProgress 前插入 MergeUiState 状态机
#      (beginLocalMerge/beginWebDavMerge/beginS3Merge/updateConversationDecision/
#       updateSettingsItemDecision/toggleScalarAdoption/confirmMerge/cancelMerge/onCleared)
# 锚点: 仓库态精确行; batch135 只改 VM 的 backup/restore/backupToS3/restoreFromS3 与
#       AppScope import/构造参数/isBackingUp, 不动 runWithProgress 与 WebDavSync import 行。
# 幂等: 命中 [batch156] 标记即跳过; 锚点失配 fail-loud + dump 现场。

import io
import sys

NL = chr(10)
MARK = "[batch156]"

WEBDAV = "app/src/main/java/me/rerere/rikkahub/data/sync/webdav/WebDavSync.kt"
S3 = "app/src/main/java/me/rerere/rikkahub/data/sync/S3Sync.kt"
VM = "app/src/main/java/me/rerere/rikkahub/ui/pages/backup/BackupVM.kt"

WEBDAV_IMPORT_ANCHOR = "import me.rerere.rikkahub.data.sync.BackupRestoreMode"
WEBDAV_IMPORTS = (
    WEBDAV_IMPORT_ANCHOR + NL +
    "import me.rerere.rikkahub.data.sync.merge.MergeApplyResult" + NL +
    "import me.rerere.rikkahub.data.sync.merge.MergePlan"
)

WEBDAV_METHOD_ANCHOR = "    private fun resolveCacheFile(displayName: String): File? {"

WEBDAV_METHODS = r'''
    // ------------------------------------------------------------ [batch156] 两阶段合并

    /** 两阶段合并：仅下载到缓存（调用方负责删除返回的文件）。 */
    suspend fun downloadBackupForMerge(
        config: WebDavConfig,
        item: WebDavBackupItem,
        onProgress: (BackupProgress) -> Unit = {},
    ): File = withContext(Dispatchers.IO) {
        val backupFile = resolveCacheFile(item.displayName)
            ?: throw IllegalArgumentException("不安全的备份文件名")
        val client = getClient(config)
        onProgress(BackupProgress("下载备份", total = item.size, detail = item.displayName))
        client.downloadToFile(item.displayName, backupFile) { completed, total ->
            onProgress(
                BackupProgress(
                    phase = "下载备份",
                    completed = completed,
                    total = total.takeIf { it > 0L } ?: item.size,
                    detail = "已下载 ${completed.fileSizeToString()}",
                    totalLabel = "实际 ZIP 文件",
                )
            )
        }.getOrThrow()
        backupFile
    }

    /** 阶段一：解压 + 扫描差异（不写库）。 */
    suspend fun beginMergeRestore(
        backupFile: File,
        config: WebDavConfig,
        onProgress: (BackupProgress) -> Unit = {},
    ): Pair<StagedMergeBackup, MergePlan> = withContext(Dispatchers.IO) {
        BackupArchiveRestorer(
            context = context,
            json = json,
            settingsStore = settingsStore,
            appDatabase = appDatabase,
            workspaceManager = workspaceManager,
        ).stageForMerge(backupFile, config, onProgress)
    }

    /** 阶段二：按用户确认的决策应用合并。 */
    suspend fun applyMergeRestore(
        staged: StagedMergeBackup,
        plan: MergePlan,
        onProgress: (BackupProgress) -> Unit = {},
    ): MergeApplyResult = withContext(Dispatchers.IO) {
        BackupArchiveRestorer(
            context = context,
            json = json,
            settingsStore = settingsStore,
            appDatabase = appDatabase,
            workspaceManager = workspaceManager,
        ).applyStagedMerge(staged, plan, onProgress)
    }

    /** 放弃合并：清理 staging。 */
    fun discardMergeRestore(staged: StagedMergeBackup) {
        staged.stagingDir.deleteRecursively()
    }

'''

S3_METHOD_ANCHOR = "    private fun S3Config.toWebDavConfig(): WebDavConfig = WebDavConfig("

S3_METHOD = r'''
    // [batch156] 两阶段合并：仅下载到缓存（调用方负责删除返回的文件）
    suspend fun downloadBackupForMerge(
        config: S3Config,
        item: S3BackupItem,
        onProgress: (BackupProgress) -> Unit = {},
    ): File = withContext(Dispatchers.IO) {
        val displayName = item.displayName
        require(displayName.isNotBlank() && File(displayName).name == displayName) { "不安全的 S3 备份文件名" }
        val backupFile = File(context.cacheDir, displayName)
        val client = getS3Client(config)
        onProgress(BackupProgress("下载备份", 0L, item.size, displayName))
        client.downloadObjectToFile(item.key, backupFile) { completed, total ->
            onProgress(
                BackupProgress(
                    phase = "下载备份",
                    completed = completed,
                    total = total.takeIf { it > 0L } ?: item.size,
                    detail = "已下载 ${completed.fileSizeToString()}",
                    totalLabel = "实际 ZIP 文件",
                )
            )
        }.getOrThrow()
        backupFile
    }

'''

VM_IMPORT_ANCHOR = "import me.rerere.rikkahub.data.sync.webdav.WebDavSync"
VM_IMPORTS = (
    VM_IMPORT_ANCHOR + NL +
    "import me.rerere.rikkahub.data.sync.merge.ConversationMergeDecision" + NL +
    "import me.rerere.rikkahub.data.sync.merge.MergePlan" + NL +
    "import me.rerere.rikkahub.data.sync.merge.SettingsItemCategory" + NL +
    "import me.rerere.rikkahub.data.sync.merge.SettingsItemDecision" + NL +
    "import me.rerere.rikkahub.data.sync.webdav.StagedMergeBackup"
)

VM_METHOD_ANCHOR = "    private suspend fun <T> runWithProgress("

VM_METHODS = r'''
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

'''


def fail(msg):
    print("::error::" + msg)
    sys.exit(1)


def dump_lines(src, needle, radius):
    lines = src.split(NL)
    hit = -1
    for i in range(len(lines)):
        if needle in lines[i]:
            hit = i
            break
    if hit < 0:
        return "(no line contains " + needle + ")"
    lo = max(0, hit - radius)
    hi = min(len(lines), hit + radius + 1)
    out = ""
    for k in range(lo, hi):
        if out:
            out = out + " | "
        out = out + str(k + 1) + ": " + lines[k]
    return out


def balance(text):
    return (text.count("{") - text.count("}"), text.count("(") - text.count(")"))


def patch_file(path, import_anchor, import_block, method_anchor, method_block, checks):
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            src = f.read()
    except Exception as exc:
        fail("batch156: read failed :: " + path + " :: " + str(exc))
    if MARK in src:
        print("batch156: already applied, skip " + path)
        return

    out = src
    if import_anchor is not None:
        if out.count(import_anchor) != 1:
            fail("batch156: import anchor count=" + str(out.count(import_anchor)) + " in " + path + " :: " + dump_lines(out, import_anchor[:50], 3))
        out = out.replace(import_anchor, import_block, 1)
    if out.count(method_anchor) != 1:
        fail("batch156: method anchor count=" + str(out.count(method_anchor)) + " in " + path + " :: " + dump_lines(out, method_anchor[:50], 3))
    bal_before = balance(src)
    out = out.replace(method_anchor, method_block + method_anchor, 1)

    expected = (
        bal_before[0] + balance(method_block)[0],
        bal_before[1] + balance(method_block)[1],
    )
    if balance(out) != expected:
        fail("batch156: balance failed in " + path + " :: before=" + str(bal_before) + " after=" + str(balance(out)))
    for needle in checks:
        if needle not in out:
            fail("batch156: post-check missing in " + path + " :: " + needle)

    try:
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(out)
    except Exception as exc:
        fail("batch156: write failed :: " + path + " :: " + str(exc))
    print("batch156: patched " + path)


def main():
    patch_file(
        WEBDAV,
        WEBDAV_IMPORT_ANCHOR, WEBDAV_IMPORTS,
        WEBDAV_METHOD_ANCHOR, WEBDAV_METHODS,
        ("suspend fun downloadBackupForMerge(", "suspend fun beginMergeRestore(", "suspend fun applyMergeRestore(", "fun discardMergeRestore("),
    )
    patch_file(
        S3,
        None, None,
        S3_METHOD_ANCHOR, S3_METHOD,
        ("suspend fun downloadBackupForMerge(",),
    )
    patch_file(
        VM,
        VM_IMPORT_ANCHOR, VM_IMPORTS,
        VM_METHOD_ANCHOR, VM_METHODS,
        ("sealed interface MergeUiState", "fun beginLocalMerge(", "fun beginWebDavMerge(", "fun beginS3Merge(", "fun confirmMerge()", "fun cancelMerge()", "override fun onCleared()"),
    )
    print("batch156: WebDavSync + S3Sync + BackupVM wired for two-phase merge")


if __name__ == "__main__":
    main()

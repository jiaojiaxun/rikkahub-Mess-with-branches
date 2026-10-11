#!/usr/bin/env python3
# batch155: 备份合并改造 6/10 —— BackupArchiveRestorer 两阶段方法
# 变更(唯一修改文件: BackupArchiveRestorer.kt):
#   1) import 块追加 merge 包与 kotlinx.json 相关 import
#   2) companion object 前插入三个新方法:
#      - stageForMerge     阶段一: 解压+校验+reconcile+差异扫描(不写库), 含 batch4 的 agent 优先逻辑
#      - applyStagedMerge  阶段二: 按用户确认的 MergePlan 应用(设置->对话->文件), 清理 staging
#      - discardStagedMerge 放弃合并: 清理 staging
#      另含 readFolderIds/applyMergeSettings/mergeItemArray/reconcileDeletedIds 四个私有辅助(P5 修复)
#   3) 文件尾追加 StagedMergeBackup 顶层类
# 锚点: 按仓库态原文核对(2026-10-11); batch4 只改 restore() 内部与 normalizeEntryName,
#       不动 import 锚点行与 companion object。
# 幂等: 命中 [batch155] 标记即跳过; 锚点失配 fail-loud + dump 现场。

import io
import sys

NL = chr(10)
MARK = "[batch155]"
RESTORER = "app/src/main/java/me/rerere/rikkahub/data/sync/webdav/BackupArchiveRestorer.kt"

IMPORT_ANCHOR = "import me.rerere.rikkahub.data.sync.BackupRestoreMode"

NEW_IMPORTS = (
    IMPORT_ANCHOR + NL +
    "import kotlinx.serialization.json.JsonElement" + NL +
    "import kotlinx.serialization.json.JsonObject" + NL +
    "import kotlinx.serialization.json.JsonPrimitive" + NL +
    "import kotlinx.serialization.json.contentOrNull" + NL +
    "import kotlinx.serialization.json.decodeFromJsonElement" + NL +
    "import kotlinx.serialization.json.encodeToJsonElement" + NL +
    "import me.rerere.rikkahub.data.sync.merge.BackupMergeScanner" + NL +
    "import me.rerere.rikkahub.data.sync.merge.MergeApplyResult" + NL +
    "import me.rerere.rikkahub.data.sync.merge.MergeDecisionApplier" + NL +
    "import me.rerere.rikkahub.data.sync.merge.MergePlan" + NL +
    "import me.rerere.rikkahub.data.sync.merge.SettingsItemCategory" + NL +
    "import me.rerere.rikkahub.data.sync.merge.SettingsItemDecision" + NL +
    "import me.rerere.rikkahub.data.sync.merge.SettingsItemDiff" + NL +
    "import me.rerere.rikkahub.data.sync.merge.SettingsMergeDiff" + NL +
    "import me.rerere.rikkahub.utils.JsonInstant"
)

METHOD_ANCHOR = "    companion object {"

NEW_METHODS = r'''
    // ------------------------------------------------------------ [batch155] 两阶段合并

    /**
     * 阶段一：解压 + 安全校验 + reconcile + 差异扫描，不写任何数据。
     * 返回的 [StagedMergeBackup] 持有 staging 目录；调用方必须在 applyStagedMerge 或
     * discardStagedMerge 中结束其生命周期。
     */
    suspend fun stageForMerge(
        archive: File,
        config: me.rerere.rikkahub.data.datastore.WebDavConfig,
        onProgress: (BackupProgress) -> Unit = {},
    ): Pair<StagedMergeBackup, MergePlan> = withContext(Dispatchers.IO) {
        require(archive.isFile && archive.canRead()) { "备份文件不存在或不可读" }

        val staging = File(context.cacheDir, "backup-merge-${System.nanoTime()}").apply { mkdirs() }
        val stagedDb = File(staging, "rikka_hub")
        val stagedWal = File(staging, "rikka_hub-wal")
        val stagedShm = File(staging, "rikka_hub-shm")
        val stagedAgentDb = File(staging, "agent_rikka_hub.db")
        var importedSettings: Settings? = null
        var agentSettings: Settings? = null
        var processedBytes = 0L
        var totalUncompressedBytes = 0L
        var entryCount = 0
        val declaredTotal = archiveUncompressedSize(archive)
        require(declaredTotal == 0L || declaredTotal <= MAX_TOTAL_UNCOMPRESSED_BYTES) { "备份展开后超过允许大小" }
        val totalBytes = declaredTotal.takeIf { it > 0L } ?: archive.length().coerceAtLeast(1L)

        fun report(phase: String, detail: String, completed: Long = processedBytes) {
            onProgress(BackupProgress(phase, completed.coerceAtLeast(0L), totalBytes, detail))
        }

        fun consumeEntry(
            input: ZipInputStream,
            maxBytes: Long,
            phase: String,
            detail: String,
            sink: (ByteArray, Int) -> Unit = { _, _ -> },
        ) {
            var entryBytes = 0L
            val buffer = ByteArray(COPY_BUFFER_SIZE)
            while (true) {
                val read = input.read(buffer)
                if (read <= 0) break
                entryBytes += read
                require(entryBytes <= maxBytes) { "ZIP 条目超过允许大小: $detail" }
                totalUncompressedBytes += read
                require(totalUncompressedBytes <= MAX_TOTAL_UNCOMPRESSED_BYTES) { "备份展开后超过允许大小" }
                sink(buffer, read)
                processedBytes = totalUncompressedBytes
                report(phase, detail)
            }
        }

        try {
            report("检查备份", archive.name, 0L)
            ZipInputStream(FileInputStream(archive)).use { input ->
                while (true) {
                    val entry = input.nextEntry ?: break
                    entryCount++
                    require(entryCount <= MAX_ENTRY_COUNT) { "备份条目数量超过允许上限" }
                    val safeName = normalizeEntryName(entry.name)
                    if (safeName == null) {
                        Log.w(TAG, "Skipping unsafe ZIP entry: ${entry.name}")
                        if (!entry.isDirectory) consumeEntry(input, MAX_ENTRY_BYTES, "检查备份", entry.name)
                        input.closeEntry()
                        continue
                    }
                    // FULL 格式的 agent 数据优先于根目录的兼容核心（与 restore() 的 batch4 逻辑一致）
                    val rawName = entry.name.replace('\\', '/').trim('/')
                    if (rawName == me.rerere.rikkahub.data.sync.AGENT_FULL_DB_ENTRY) {
                        FileOutputStream(stagedAgentDb).use { output ->
                            consumeEntry(input, MAX_ENTRY_BYTES, "准备数据库", entry.name) { bytes, count ->
                                output.write(bytes, 0, count)
                            }
                        }
                        input.closeEntry()
                        continue
                    }
                    if (rawName == me.rerere.rikkahub.data.sync.AGENT_FULL_SETTINGS_ENTRY) {
                        val rawOutput = ByteArrayOutputStream()
                        consumeEntry(input, MAX_SETTINGS_BYTES, "读取设置", entry.name) { bytes, count ->
                            rawOutput.write(bytes, 0, count)
                        }
                        agentSettings = json.decodeFromString(
                            SettingsJsonMigrator.migrate(rawOutput.toByteArray().toString(Charsets.UTF_8))
                        )
                        input.closeEntry()
                        continue
                    }
                    val target = when {
                        safeName == "settings.json" -> null
                        safeName == "rikka_hub.db" -> stagedDb
                        safeName == "rikka_hub-wal" -> stagedWal
                        safeName == "rikka_hub-shm" -> stagedShm
                        safeName.startsWith("${FileFolders.UPLOAD}/") -> resolveStagedFile(staging, safeName)
                        safeName.startsWith("${FileFolders.SKILLS}/") -> resolveStagedFile(staging, safeName)
                        safeName.startsWith("${FileFolders.FONTS}/") -> resolveStagedFile(staging, safeName)
                        safeName.startsWith("${FileFolders.IMAGES}/") -> resolveStagedFile(staging, safeName)
                        safeName.startsWith("${FileFolders.TOOL_OUTPUTS}/") -> resolveStagedFile(staging, safeName)
                        safeName.startsWith("workspaces/") -> resolveStagedFile(staging, safeName)
                        else -> null
                    }
                    when {
                        entry.isDirectory -> Log.d(TAG, "Skipping directory entry $safeName")
                        safeName == "settings.json" -> {
                            val rawOutput = ByteArrayOutputStream()
                            consumeEntry(input, MAX_SETTINGS_BYTES, "读取设置", "settings.json") { bytes, count ->
                                rawOutput.write(bytes, 0, count)
                            }
                            val raw = rawOutput.toByteArray().toString(Charsets.UTF_8)
                            importedSettings = json.decodeFromString(SettingsJsonMigrator.migrate(raw))
                        }
                        target != null -> {
                            val phase = when {
                                safeName.startsWith("workspaces/") -> "恢复工作区"
                                safeName == "rikka_hub.db" || safeName.startsWith("rikka_hub-") -> "准备数据库"
                                safeName.startsWith("${FileFolders.SKILLS}/") -> "恢复技能"
                                else -> "恢复文件"
                            }
                            target.parentFile?.mkdirs()
                            FileOutputStream(target).use { output ->
                                consumeEntry(input, MAX_ENTRY_BYTES, phase, safeName) { bytes, count ->
                                    output.write(bytes, 0, count)
                                }
                            }
                        }
                        else -> {
                            Log.i(TAG, "Skipping unknown ZIP entry $safeName")
                            consumeEntry(input, MAX_ENTRY_BYTES, "检查备份", safeName)
                        }
                    }
                    input.closeEntry()
                }
            }

            // FULL 快照优先于兼容核心（batch4 逻辑）
            if (stagedAgentDb.isFile) {
                moveReplacing(stagedAgentDb, stagedDb)
                stagedWal.delete()
                stagedShm.delete()
            }
            agentSettings?.let { importedSettings = it }

            val hasDatabase = config.items.contains(
                me.rerere.rikkahub.data.datastore.WebDavConfig.BackupItem.DATABASE
            ) && stagedDb.isFile
            if (hasDatabase) {
                ImportedDatabaseReconciler.reconcileDatabaseFile(stagedDb)
            }

            report("扫描差异", "分析对话与设置差异")
            val scanner = BackupMergeScanner(appDatabase, settingsStore)
            val plan = if (hasDatabase) {
                scanner.scan(stagedDb, importedSettings)
            } else {
                MergePlan(
                    conversations = emptyList(),
                    settings = importedSettings?.let { scanner.diffSettings(it) },
                    memoriesToAdd = 0,
                    favoritesToAdd = 0,
                    workspacesToMerge = 0,
                )
            }
            StagedMergeBackup(staging, stagedDb.takeIf { it.isFile }, importedSettings, config) to plan
        } catch (error: Throwable) {
            staging.deleteRecursively()
            throw error
        }
    }

    /** 阶段二：按用户确认后的 [MergePlan] 应用合并（先设置后对话，兜底依赖合并后的助手集合），结束后清理 staging。 */
    suspend fun applyStagedMerge(
        staged: StagedMergeBackup,
        plan: MergePlan,
        onProgress: (BackupProgress) -> Unit = {},
    ): MergeApplyResult = withContext(Dispatchers.IO) {
        try {
            if (staged.importedSettings != null && plan.settings != null) {
                onProgress(BackupProgress("合并设置", detail = "按确认结果应用供应商、助手与偏好"))
                applyMergeSettings(staged.importedSettings, plan.settings)
            }
            var result = MergeApplyResult()
            if (staged.stagedDb != null && staged.config.items.contains(
                    me.rerere.rikkahub.data.datastore.WebDavConfig.BackupItem.DATABASE
                )
            ) {
                onProgress(BackupProgress("合并数据库", detail = "按确认结果写入对话"))
                val currentSettings = settingsStore.settingsFlow.value
                result = MergeDecisionApplier(appDatabase, workspaceManager).apply(
                    stagedDatabase = staged.stagedDb,
                    plan = plan,
                    validAssistantIds = currentSettings.assistants.map { it.id.toString() }.toSet(),
                    defaultAssistantId = currentSettings.assistantId.toString(),
                    validFolderIds = readFolderIds(),
                    onProgress = { done, total, title ->
                        onProgress(BackupProgress("合并数据库", done, total.coerceAtLeast(1L), title))
                    },
                )
            }
            if (staged.config.items.contains(me.rerere.rikkahub.data.datastore.WebDavConfig.BackupItem.FILES)) {
                copyStagedFilesToApp(staged.stagingDir, onProgress)
            }
            onProgress(BackupProgress("合并完成", detail = result.summary()))
            result
        } finally {
            staged.stagingDir.deleteRecursively()
        }
    }

    /** 放弃合并：清理 staging。 */
    fun discardStagedMerge(staged: StagedMergeBackup) {
        staged.stagingDir.deleteRecursively()
    }

    private fun readFolderIds(): Set<String> = runCatching {
        appDatabase.openHelper.readableDatabase.query("SELECT id FROM conversation_folder").use { cursor ->
            buildSet { while (cursor.moveToNext()) add(cursor.getString(0)) }
        }
    }.getOrDefault(emptySet())

    /** P5 修复：设置按用户决策逐项合并（条目级 + 标量级 + 删除标记重算）。 */
    private suspend fun applyMergeSettings(incoming: Settings, diff: SettingsMergeDiff) {
        settingsStore.update { current ->
            val currentMap = JsonInstant.encodeToJsonElement(current).jsonObject.toMutableMap()
            val incomingJson = JsonInstant.encodeToJsonElement(incoming).jsonObject

            val arrayKeys = mapOf(
                "providers" to SettingsItemCategory.PROVIDER,
                "assistants" to SettingsItemCategory.ASSISTANT,
                "mcpServers" to SettingsItemCategory.MCP_SERVER,
            )
            for ((arrayKey, category) in arrayKeys) {
                currentMap[arrayKey] = mergeItemArray(
                    currentMap[arrayKey],
                    incomingJson[arrayKey],
                    diff.items.filter { it.category == category },
                )
            }
            reconcileDeletedIds(currentMap, incomingJson, "providers", listOf("deletedProviderIds", "deletedBuiltInProviderIds"))
            reconcileDeletedIds(currentMap, incomingJson, "assistants", listOf("deletedAssistantIds"))
            reconcileDeletedIds(currentMap, incomingJson, "mcpServers", listOf("deletedMcpServerIds"))

            diff.scalarFields.filter { it.adoptBackup }.forEach { field ->
                val backupValue = incomingJson[field.fieldKey]
                if (backupValue != null) currentMap[field.fieldKey] = backupValue
            }

            JsonInstant.decodeFromJsonElement(JsonObject(currentMap))
        }
    }

    private fun mergeItemArray(
        currentElement: JsonElement?,
        incomingElement: JsonElement?,
        diffs: List<SettingsItemDiff>,
    ): JsonElement {
        val currentArray = currentElement as? JsonArray ?: JsonArray(emptyList())
        val incomingArray = incomingElement as? JsonArray ?: JsonArray(emptyList())
        val result = LinkedHashMap<String, JsonObject>()
        currentArray.forEach { element ->
            val obj = element as? JsonObject ?: return@forEach
            val id = (obj["id"] as? JsonPrimitive)?.contentOrNull ?: return@forEach
            result[id] = obj
        }
        val backupById = LinkedHashMap<String, JsonObject>()
        incomingArray.forEach { element ->
            val obj = element as? JsonObject ?: return@forEach
            val id = (obj["id"] as? JsonPrimitive)?.contentOrNull ?: return@forEach
            backupById[id] = obj
        }
        diffs.forEach { itemDiff ->
            when (itemDiff.decision) {
                SettingsItemDecision.IMPORT, SettingsItemDecision.USE_BACKUP ->
                    backupById[itemDiff.id]?.let { result[itemDiff.id] = it }
                SettingsItemDecision.DELETE -> result.remove(itemDiff.id)
                SettingsItemDecision.SKIP, SettingsItemDecision.KEEP, SettingsItemDecision.KEEP_LOCAL -> Unit
            }
        }
        return JsonArray(result.values.toList())
    }

    private fun reconcileDeletedIds(
        currentMap: MutableMap<String, JsonElement>,
        incomingJson: JsonObject,
        arrayKey: String,
        deletedKeys: List<String>,
    ) {
        val finalIds = (currentMap[arrayKey] as? JsonArray)
            ?.mapNotNull { ((it as? JsonObject)?.get("id") as? JsonPrimitive)?.contentOrNull }
            ?.toSet().orEmpty()
        deletedKeys.forEach { deletedKey ->
            val currentDeleted = (currentMap[deletedKey] as? JsonArray)
                ?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }?.toSet().orEmpty()
            val backupDeleted = (incomingJson[deletedKey] as? JsonArray)
                ?.mapNotNull { (it as? JsonPrimitive)?.contentOrNull }?.toSet().orEmpty()
            currentMap[deletedKey] = JsonArray(((currentDeleted + backupDeleted) - finalIds).map { JsonPrimitive(it) })
        }
    }

'''

STAGED_CLASS = NL + r'''/** [batch155] stageForMerge 的产物：已解压、校验并完成差异扫描的备份快照，等待用户确认。 */
class StagedMergeBackup(
    val stagingDir: File,
    val stagedDb: File?,
    val importedSettings: Settings?,
    val config: me.rerere.rikkahub.data.datastore.WebDavConfig,
)
''' + NL

REQUIRED_AFTER = (
    "suspend fun stageForMerge(",
    "suspend fun applyStagedMerge(",
    "fun discardStagedMerge(",
    "class StagedMergeBackup(",
    "private suspend fun applyMergeSettings(",
)


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


def main():
    try:
        with io.open(RESTORER, "r", encoding="utf-8") as f:
            src = f.read()
    except Exception as exc:
        fail("batch155: read failed :: " + RESTORER + " :: " + str(exc))

    if MARK in src:
        print("batch155: already applied, skip")
        return

    if src.count(IMPORT_ANCHOR) != 1:
        fail("batch155: import anchor count=" + str(src.count(IMPORT_ANCHOR)) + " :: " + dump_lines(src, "BackupRestoreMode", 3))
    if src.count(METHOD_ANCHOR) != 1:
        fail("batch155: companion anchor count=" + str(src.count(METHOD_ANCHOR)) + " :: " + dump_lines(src, "companion object", 3))

    bal_before = balance(src)
    out = src.replace(IMPORT_ANCHOR, NEW_IMPORTS, 1)
    out = out.replace(METHOD_ANCHOR, NEW_METHODS + METHOD_ANCHOR, 1)
    out = out.rstrip() + STAGED_CLASS

    expected = (
        bal_before[0] + balance(NEW_METHODS)[0] + balance(STAGED_CLASS)[0],
        bal_before[1] + balance(NEW_METHODS)[1] + balance(STAGED_CLASS)[1],
    )
    if balance(out) != expected:
        fail("batch155: brace/paren balance failed :: before=" + str(bal_before) + " after=" + str(balance(out)) + " expected=" + str(expected))

    for needle in REQUIRED_AFTER:
        if needle not in out:
            fail("batch155: post-check missing :: " + needle)

    try:
        with io.open(RESTORER, "w", encoding="utf-8") as f:
            f.write(out)
    except Exception as exc:
        fail("batch155: write failed :: " + str(exc))

    print("batch155: two-phase merge methods added to BackupArchiveRestorer")


if __name__ == "__main__":
    main()

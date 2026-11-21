// [batch150] 备份合并改造：合并计划数据结构
// 扫描阶段产出 MergePlan（只读），UI 逐项展示并由用户确认决策，
// 最后由 MergeDecisionApplier 按计划执行。本批次不修改任何旧合并逻辑。
package me.rerere.rikkahub.data.sync.merge

/** 对话在备份与本地之间的语义关系。 */
enum class ConversationMergeRelation {
    /** 本地没有该对话。 */
    NEW,

    /** 语义相同（消息身份与内容一致；翻译/用量/选中版本等元数据可能有差异）。 */
    SAME,

    /** 备份 = 本地 + 尾部追加（备份更新）。 */
    BACKUP_AHEAD,

    /** 本地 = 备份 + 尾部追加（本地更新）。 */
    LOCAL_AHEAD,

    /** 共有节点上的消息版本集合发生变化（如重生成新增版本），可自动合并版本数组。 */
    VERSIONS_MODIFIED,

    /** 真分叉：两边存在互不包含的内容差异。 */
    DIVERGED,
}

/** 用户对单个对话差异的决策。 */
enum class ConversationMergeDecision {
    /** 用备份版本替换本地。 */
    USE_BACKUP,

    /** 保留本地版本，丢弃备份中的该对话。 */
    KEEP_LOCAL,

    /** 两个都保留：备份版本另存为新对话。 */
    KEEP_BOTH,

    /** 仅 NEW：导入该对话。 */
    IMPORT,

    /** 仅 NEW：不导入。 */
    SKIP,

    /** 仅 VERSIONS_MODIFIED：合并消息版本数组（并集，选中版本取较新方）。 */
    MERGE_VERSIONS,
}

/** 对话一侧（本地或备份）的展示摘要。 */
data class ConversationSideSummary(
    val nodeCount: Int,
    val messageCount: Int,
    val updateAt: Long,
    val firstUserMessagePreview: String,
    val lastMessagePreview: String,
)

/** 单个对话的合并项。 */
data class ConversationMergeItem(
    val conversationId: String,
    val title: String,
    val relation: ConversationMergeRelation,
    /** 本地摘要；NEW 时为 null。 */
    val local: ConversationSideSummary?,
    val backup: ConversationSideSummary,
    val defaultDecision: ConversationMergeDecision,
    /** 人类可读的关系说明（展示用）。 */
    val relationNote: String,
    val decision: ConversationMergeDecision = defaultDecision,
)

/** 设置条目类别。 */
enum class SettingsItemCategory { PROVIDER, ASSISTANT, MCP_SERVER }

/** 设置条目差异类型。 */
enum class SettingsItemKind {
    /** 备份有、本地没有（且本地未删除过）→ 询问是否导入。 */
    ADDED_IN_BACKUP,

    /** 备份有、本地删除标记里有 → 询问是否恢复。 */
    DELETED_LOCALLY,

    /** 本地有、备份删除标记里有 → 询问是否删除本地。 */
    REMOVED_IN_BACKUP,

    /** 两边都有但内容不同 → 询问用哪边。 */
    MODIFIED,
}

/** 设置条目决策。 */
enum class SettingsItemDecision { IMPORT, SKIP, DELETE, KEEP, USE_BACKUP, KEEP_LOCAL }

/** 单个设置条目的差异。 */
data class SettingsItemDiff(
    val category: SettingsItemCategory,
    val id: String,
    val displayName: String,
    /** 差异摘要（如 baseUrl、模型数量、提示词预览）。 */
    val detail: String,
    val kind: SettingsItemKind,
    val defaultDecision: SettingsItemDecision,
    val decision: SettingsItemDecision = defaultDecision,
)

/** 标量偏好字段差异（providers/assistants/mcpServers 之外的字段）。 */
data class ScalarFieldDiff(
    val fieldKey: String,
    val displayName: String,
    val localValuePreview: String,
    val backupValuePreview: String,
    /** 用户勾选：采用备份值覆盖本地。默认 false = 保留本地。 */
    val adoptBackup: Boolean = false,
)

/** 设置差异总表。 */
data class SettingsMergeDiff(
    val items: List<SettingsItemDiff>,
    val scalarFields: List<ScalarFieldDiff>,
)

/** 合并计划（扫描产物，只读；用户决策通过 copy 更新条目）。 */
data class MergePlan(
    val conversations: List<ConversationMergeItem>,
    val settings: SettingsMergeDiff?,
    val memoriesToAdd: Int,
    val favoritesToAdd: Int,
    val workspacesToMerge: Int,
) {
    /** 需要用户拍板的分叉对话数量。 */
    val divergedCount: Int
        get() = conversations.count { it.relation == ConversationMergeRelation.DIVERGED }

    /** 有任何差异或新增内容时为 true；false 表示备份与本地语义等价。 */
    val hasChanges: Boolean
        get() = conversations.any { it.relation != ConversationMergeRelation.SAME } ||
            (settings?.items?.isNotEmpty() == true) ||
            (settings?.scalarFields?.isNotEmpty() == true) ||
            memoriesToAdd > 0 || favoritesToAdd > 0 || workspacesToMerge > 0
}

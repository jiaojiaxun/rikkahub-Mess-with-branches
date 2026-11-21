// [batch152] 备份合并改造：设置差异分析器
// 输入为 Settings 序列化后的 JsonObject（调用方负责序列化与 deletedIds 提取），
// 因此本分析器与 Settings 数据类解耦，可以纯 JVM 单测。
// 删除标记语义：条目实体存在与否 + deletedIds 共同决定差异类型——
// "本地有、备份 deletedIds 含它" 才是备份端明确删除；"备份没有该条目" 本身不算删除
// （备份可能只是旧）。所有默认决策偏保守：不丢本地数据。
package me.rerere.rikkahub.data.sync.merge

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull

object SettingsMergeAnalyzer {

    /** 条目级数组的 JSON key → 类别。 */
    private val ITEM_ARRAY_KEYS = mapOf(
        "providers" to SettingsItemCategory.PROVIDER,
        "assistants" to SettingsItemCategory.ASSISTANT,
        "mcpServers" to SettingsItemCategory.MCP_SERVER,
    )

    /** 不参与标量 diff 的 key（条目数组 + 删除标记集合，均由条目级逻辑处理）。 */
    private val EXCLUDED_SCALAR_KEYS: Set<String> = ITEM_ARRAY_KEYS.keys + setOf(
        "deletedProviderIds",
        "deletedBuiltInProviderIds",
        "deletedAssistantIds",
        "deletedMcpServerIds",
    )

    /** 常见标量字段的中文展示名；未知字段回退为原始 key。 */
    private val FIELD_DISPLAY_NAMES = mapOf(
        "chatModelId" to "默认对话模型",
        "fastModelId" to "快速模型",
        "titleModelId" to "标题生成模型",
        "translateModelId" to "翻译模型",
        "suggestionModelId" to "建议模型",
        "ocrModelId" to "OCR 模型",
        "compressModelId" to "压缩模型",
        "imageGenerationModelId" to "图片生成模型",
        "displaySetting" to "显示设置",
        "dynamicColor" to "动态颜色",
        "themeId" to "主题",
        "customThemes" to "自定义主题",
        "developerMode" to "开发者模式",
        "webDavConfig" to "WebDAV 配置",
        "s3Config" to "S3 配置",
        "searchServices" to "搜索服务",
        "favoriteModels" to "收藏的模型",
        "modeInjections" to "模式注入",
        "lorebooks" to "世界书",
        "quickMessages" to "快捷消息",
        "assistantId" to "当前助手",
        "enableWebSearch" to "网络搜索",
        "backupReminderConfig" to "备份提醒",
        "autoEnabledDefaultSkills" to "自动启用技能记录",
        "titlePrompt" to "标题提示词",
        "translationPrompt" to "翻译提示词",
        "suggestionPrompt" to "建议提示词",
        "ocrPrompt" to "OCR 提示词",
        "compressPrompt" to "压缩提示词",
        "enableAutoCompaction" to "自动压缩",
        "learningMode" to "学习模式",
        "ttsProviders" to "TTS 供应商",
        "asrProviders" to "语音识别供应商",
        "selectedTTSProviderId" to "当前 TTS 供应商",
        "selectedASRProviderId" to "当前语音识别供应商",
    )

    private const val PREVIEW_MAX = 80
    private const val DIFF_FIELDS_MAX = 5

    /**
     * 计算设置差异。
     * @param currentJson 本地 Settings 序列化 JSON
     * @param incomingJson 备份 Settings 序列化 JSON
     * @param currentDeletedIds 本地删除标记（类别 → id 字符串集合）
     * @param backupDeletedIds 备份删除标记
     */
    fun diff(
        currentJson: JsonObject,
        incomingJson: JsonObject,
        currentDeletedIds: Map<SettingsItemCategory, Set<String>>,
        backupDeletedIds: Map<SettingsItemCategory, Set<String>>,
    ): SettingsMergeDiff {
        val items = mutableListOf<SettingsItemDiff>()
        for ((arrayKey, category) in ITEM_ARRAY_KEYS) {
            items += diffItemArray(
                category = category,
                currentArray = currentJson[arrayKey] as? JsonArray,
                backupArray = incomingJson[arrayKey] as? JsonArray,
                currentDeleted = currentDeletedIds[category].orEmpty(),
                backupDeleted = backupDeletedIds[category].orEmpty(),
            )
        }
        return SettingsMergeDiff(
            items = items,
            scalarFields = diffScalars(currentJson, incomingJson),
        )
    }

    private fun diffItemArray(
        category: SettingsItemCategory,
        currentArray: JsonArray?,
        backupArray: JsonArray?,
        currentDeleted: Set<String>,
        backupDeleted: Set<String>,
    ): List<SettingsItemDiff> {
        val currentById = indexById(currentArray)
        val backupById = indexById(backupArray)
        val result = mutableListOf<SettingsItemDiff>()

        // 备份独有的条目：新增，或本地删除过
        for ((id, backupItem) in backupById) {
            if (currentById.containsKey(id)) continue
            val kind: SettingsItemKind
            val default: SettingsItemDecision
            if (id in currentDeleted) {
                kind = SettingsItemKind.DELETED_LOCALLY
                default = SettingsItemDecision.SKIP // 尊重本地删除
            } else {
                kind = SettingsItemKind.ADDED_IN_BACKUP
                default = SettingsItemDecision.IMPORT
            }
            result += SettingsItemDiff(
                category = category,
                id = id,
                displayName = itemDisplayName(backupItem),
                detail = itemDetail(category, backupItem),
                kind = kind,
                defaultDecision = default,
            )
        }

        // 本地独有的条目：仅当备份端明确删除（在备份 deletedIds 里）才列为差异；
        // 否则只是"备份较旧、本地后来新建"，静默保留本地，不打扰用户。
        for ((id, currentItem) in currentById) {
            if (backupById.containsKey(id)) continue
            if (id in backupDeleted) {
                result += SettingsItemDiff(
                    category = category,
                    id = id,
                    displayName = itemDisplayName(currentItem),
                    detail = itemDetail(category, currentItem),
                    kind = SettingsItemKind.REMOVED_IN_BACKUP,
                    defaultDecision = SettingsItemDecision.KEEP, // 保守：默认保留本地
                )
            }
        }

        // 两边都有但内容不同
        for ((id, currentItem) in currentById) {
            val backupItem = backupById[id] ?: continue
            if (currentItem == backupItem) continue
            result += SettingsItemDiff(
                category = category,
                id = id,
                displayName = itemDisplayName(currentItem),
                detail = diffFieldNames(currentItem, backupItem),
                kind = SettingsItemKind.MODIFIED,
                defaultDecision = SettingsItemDecision.KEEP_LOCAL,
            )
        }
        return result
    }

    private fun diffScalars(currentJson: JsonObject, incomingJson: JsonObject): List<ScalarFieldDiff> {
        val allKeys = (currentJson.keys + incomingJson.keys) - EXCLUDED_SCALAR_KEYS
        return allKeys.mapNotNull { key ->
            val local = currentJson[key]
            val backup = incomingJson[key]
            if (local == backup) return@mapNotNull null
            ScalarFieldDiff(
                fieldKey = key,
                displayName = FIELD_DISPLAY_NAMES[key] ?: key,
                localValuePreview = preview(local),
                backupValuePreview = preview(backup),
            )
        }.sortedBy { it.fieldKey }
    }

    private fun indexById(array: JsonArray?): Map<String, JsonObject> {
        if (array == null) return emptyMap()
        val result = LinkedHashMap<String, JsonObject>()
        for (element in array) {
            val obj = element as? JsonObject ?: continue
            val id = (obj["id"] as? JsonPrimitive)?.contentOrNull ?: continue
            result[id] = obj
        }
        return result
    }

    private fun itemDisplayName(obj: JsonObject): String =
        (obj["name"] as? JsonPrimitive)?.contentOrNull?.takeIf { it.isNotBlank() }
            ?: (obj["id"] as? JsonPrimitive)?.contentOrNull
            ?: "未命名"

    private fun itemDetail(category: SettingsItemCategory, obj: JsonObject): String = when (category) {
        SettingsItemCategory.PROVIDER -> buildString {
            append("类型 ").append((obj["type"] as? JsonPrimitive)?.contentOrNull ?: "?")
            (obj["baseUrl"] as? JsonPrimitive)?.contentOrNull?.takeIf { it.isNotBlank() }?.let {
                append(" · ").append(it)
            }
            (obj["models"] as? JsonArray)?.let { append(" · ").append(it.size).append(" 个模型") }
        }

        SettingsItemCategory.ASSISTANT -> {
            val prompt = (obj["systemPrompt"] as? JsonPrimitive)?.contentOrNull.orEmpty()
            if (prompt.isBlank()) "无系统提示词" else "提示词：" + prompt.take(50)
        }

        SettingsItemCategory.MCP_SERVER ->
            (obj["url"] as? JsonPrimitive)?.contentOrNull.orEmpty().ifBlank { "无地址" }
    }

    /** 列出两个条目 JSON 的顶层差异字段名（用于 MODIFIED 的摘要）。 */
    private fun diffFieldNames(a: JsonObject, b: JsonObject): String {
        val changed = (a.keys + b.keys).filter { a[it] != b[it] }
        if (changed.isEmpty()) return "内容有细微差异"
        val shown = changed.take(DIFF_FIELDS_MAX).joinToString("、")
        return "差异字段：" + shown + if (changed.size > DIFF_FIELDS_MAX) " 等 ${changed.size} 项" else ""
    }

    private fun preview(element: JsonElement?): String {
        if (element == null) return "（无）"
        val raw = element.toString()
        return if (raw.length > PREVIEW_MAX) raw.take(PREVIEW_MAX) + "…" else raw
    }
}

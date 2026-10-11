#!/usr/bin/env python3
# batch152: 备份合并改造 3/10 —— 设置差异分析器（纯 JSON 层）+ 单元测试
# 设计: 输入是两个 Settings 序列化后的 JsonObject + 双方删除标记集合,
#       不依赖 Settings 数据类本身——单元测试无需构造巨大的 Settings 实例。
#       条目级(providers/assistants/mcpServers)按 id 匹配分四类:
#       ADDED_IN_BACKUP / DELETED_LOCALLY / REMOVED_IN_BACKUP / MODIFIED;
#       其余字段全部走标量 diff(含嵌套对象整体比较)。
# 变更: 仅新增两个文件, 不修改任何现有文件。
#   1) app/.../data/sync/merge/SettingsMergeAnalyzer.kt
#   2) app/src/test/.../merge/SettingsMergeAnalyzerTest.kt
# 幂等: 目标文件已存在且含 [batch152] 标记则跳过; 存在但无标记则 fail(防冲突)。

import io
import os
import sys

NL = chr(10)
MARK = "[batch152]"

ANALYZER_PATH = "app/src/main/java/me/rerere/rikkahub/data/sync/merge/SettingsMergeAnalyzer.kt"
TEST_PATH = "app/src/test/java/me/rerere/rikkahub/data/sync/merge/SettingsMergeAnalyzerTest.kt"

ANALYZER_KT = r'''// [batch152] 备份合并改造：设置差异分析器
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
'''

TEST_KT = r'''// [batch152] 备份合并改造：设置差异分析器单元测试
package me.rerere.rikkahub.data.sync.merge

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class SettingsMergeAnalyzerTest {
    private val json = Json { ignoreUnknownKeys = true }

    private fun obj(text: String): JsonObject = json.parseToJsonElement(text) as JsonObject

    private fun emptyDeleted(): Map<SettingsItemCategory, Set<String>> = emptyMap()

    @Test
    fun addedInBackupIsDetectedWithImportDefault() {
        val current = obj("""{"providers":[]}""")
        val backup = obj("""{"providers":[{"id":"p1","name":"OpenAI","type":"openai","baseUrl":"https://api.openai.com/v1","models":[]}]}""")
        val diff = SettingsMergeAnalyzer.diff(current, backup, emptyDeleted(), emptyDeleted())
        assertEquals(1, diff.items.size)
        val item = diff.items.single()
        assertEquals(SettingsItemKind.ADDED_IN_BACKUP, item.kind)
        assertEquals(SettingsItemDecision.IMPORT, item.defaultDecision)
        assertEquals("OpenAI", item.displayName)
    }

    @Test
    fun locallyDeletedIsDetectedWithSkipDefault() {
        val current = obj("""{"providers":[]}""")
        val backup = obj("""{"providers":[{"id":"p1","name":"OpenAI","type":"openai"}]}""")
        val currentDeleted = mapOf(SettingsItemCategory.PROVIDER to setOf("p1"))
        val diff = SettingsMergeAnalyzer.diff(current, backup, currentDeleted, emptyDeleted())
        val item = diff.items.single()
        assertEquals(SettingsItemKind.DELETED_LOCALLY, item.kind)
        assertEquals(SettingsItemDecision.SKIP, item.defaultDecision)
    }

    @Test
    fun removedInBackupIsDetectedWithKeepDefault() {
        val current = obj("""{"assistants":[{"id":"a1","name":"助手A","systemPrompt":"hi"}]}""")
        val backup = obj("""{"assistants":[]}""")
        val backupDeleted = mapOf(SettingsItemCategory.ASSISTANT to setOf("a1"))
        val diff = SettingsMergeAnalyzer.diff(current, backup, emptyDeleted(), backupDeleted)
        val item = diff.items.single()
        assertEquals(SettingsItemKind.REMOVED_IN_BACKUP, item.kind)
        assertEquals(SettingsItemDecision.KEEP, item.defaultDecision)
    }

    @Test
    fun localOnlyItemWithoutBackupDeleteMarkIsNotListed() {
        // 备份较旧、本地后来新建的条目：不是"备份删除"，不应出现在差异清单
        val current = obj("""{"assistants":[{"id":"a1","name":"新助手"}]}""")
        val backup = obj("""{"assistants":[]}""")
        val diff = SettingsMergeAnalyzer.diff(current, backup, emptyDeleted(), emptyDeleted())
        assertTrue(diff.items.isEmpty())
    }

    @Test
    fun modifiedItemListsChangedFields() {
        val current = obj("""{"mcpServers":[{"id":"m1","name":"fs","url":"http://a"}]}""")
        val backup = obj("""{"mcpServers":[{"id":"m1","name":"fs","url":"http://b"}]}""")
        val diff = SettingsMergeAnalyzer.diff(current, backup, emptyDeleted(), emptyDeleted())
        val item = diff.items.single()
        assertEquals(SettingsItemKind.MODIFIED, item.kind)
        assertEquals(SettingsItemDecision.KEEP_LOCAL, item.defaultDecision)
        assertTrue(item.detail.contains("url"))
    }

    @Test
    fun identicalItemsAreNotListed() {
        val current = obj("""{"providers":[{"id":"p1","name":"A","type":"openai"}]}""")
        val backup = obj("""{"providers":[{"id":"p1","name":"A","type":"openai"}]}""")
        val diff = SettingsMergeAnalyzer.diff(current, backup, emptyDeleted(), emptyDeleted())
        assertTrue(diff.items.isEmpty())
    }

    @Test
    fun scalarDiffListsChangedFieldsAndExcludesItemArrays() {
        val current = obj("""{"themeId":"a","displaySetting":{"x":1},"providers":[]}""")
        val backup = obj("""{"themeId":"b","displaySetting":{"x":1},"providers":[]}""")
        val diff = SettingsMergeAnalyzer.diff(current, backup, emptyDeleted(), emptyDeleted())
        assertEquals(1, diff.scalarFields.size)
        assertEquals("themeId", diff.scalarFields.single().fieldKey)
        assertEquals("主题", diff.scalarFields.single().displayName)
    }

    @Test
    fun nestedObjectDifferenceIsReportedAsOneField() {
        val current = obj("""{"displaySetting":{"fontSize":16}}""")
        val backup = obj("""{"displaySetting":{"fontSize":18}}""")
        val diff = SettingsMergeAnalyzer.diff(current, backup, emptyDeleted(), emptyDeleted())
        assertEquals(1, diff.scalarFields.size)
        assertEquals("displaySetting", diff.scalarFields.single().fieldKey)
        assertEquals("显示设置", diff.scalarFields.single().displayName)
    }

    @Test
    fun deletedIdKeysAreExcludedFromScalarDiff() {
        val current = obj("""{"deletedProviderIds":["p1"]}""")
        val backup = obj("""{"deletedProviderIds":[]}""")
        val diff = SettingsMergeAnalyzer.diff(current, backup, emptyDeleted(), emptyDeleted())
        assertTrue(diff.scalarFields.isEmpty())
    }

    @Test
    fun unknownFieldFallsBackToRawKey() {
        val current = obj("""{"someFutureField":1}""")
        val backup = obj("""{"someFutureField":2}""")
        val diff = SettingsMergeAnalyzer.diff(current, backup, emptyDeleted(), emptyDeleted())
        assertEquals("someFutureField", diff.scalarFields.single().displayName)
    }
}
'''

REQUIRED_SNIPPETS = (
    (ANALYZER_PATH, "object SettingsMergeAnalyzer"),
    (ANALYZER_PATH, "fun diff("),
    (TEST_PATH, "class SettingsMergeAnalyzerTest"),
)


def fail(msg):
    print("::error::" + msg)
    sys.exit(1)


def write_new_file(path, content):
    if os.path.exists(path):
        with io.open(path, "r", encoding="utf-8") as f:
            existing = f.read()
        if MARK in existing:
            print("batch152: already applied, skip " + path)
            return
        fail("batch152: target exists without mark :: " + path)
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    try:
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(content)
    except Exception as exc:
        fail("batch152: write failed :: " + path + " :: " + str(exc))
    print("batch152: wrote " + path)


def verify_file(path, needle):
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as exc:
        fail("batch152: verify read failed :: " + path + " :: " + str(exc))
    if needle not in content:
        fail("batch152: verify failed, missing " + needle + " in " + path)
    if MARK not in content:
        fail("batch152: verify failed, missing mark in " + path)


def main():
    write_new_file(ANALYZER_PATH, ANALYZER_KT)
    write_new_file(TEST_PATH, TEST_KT)
    for path, needle in REQUIRED_SNIPPETS:
        verify_file(path, needle)
    print("batch152: settings merge analyzer + tests written")


if __name__ == "__main__":
    main()

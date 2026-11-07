// [batch152] 备份合并改造：设置差异分析器单元测试
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

// rhCustomTools (batch213) — AI 自定义工具：存储层（tool.json 唯一事实源 + index.html 派生物）
package me.rerere.rikkahub.data.ai.tools.custom

import android.content.Context
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import java.io.File
import java.util.UUID

/**
 * AI 自定义工具的定义。name 是暴露给模型的工具名；parameters 是 JSON Schema object；
 * code 是 JavaScript，需定义 async function main(args) { ... return "text"; }。
 */
@Serializable
data class CustomToolDef(
    val id: String,
    val name: String,
    val description: String,
    val parameters: JsonObject,
    val code: String,
    val enabled: Boolean = true,
    val createdAt: Long = 0L,
    val updatedAt: Long = 0L,
)

/**
 * 文件型存储：每个工具一个目录（tool.json 为唯一事实源；index.html 是执行用派生物）。
 * 懒加载全局单例 —— AI 侧与设置页共享同一实例，改动即时互相可见，无需 Application 初始化。
 */
class CustomToolStore private constructor(context: Context) {

    private val appContext = context.applicationContext
    private val json = Json { ignoreUnknownKeys = true }

    private val _tools = MutableStateFlow<List<CustomToolDef>>(emptyList())
    val toolsFlow: StateFlow<List<CustomToolDef>> = _tools.asStateFlow()

    @Volatile
    private var loaded = false

    fun rootDir(): File = File(appContext.filesDir, "custom-tools").apply { mkdirs() }

    fun toolDir(id: String): File = File(rootDir(), id).apply { mkdirs() }

    private fun ensureLoaded() {
        if (loaded) return
        synchronized(this) {
            if (loaded) return
            _tools.value = scanDisk()
            loaded = true
        }
    }

    private fun scanDisk(): List<CustomToolDef> {
        val dirs = rootDir().listFiles { f -> f.isDirectory } ?: return emptyList()
        return dirs.mapNotNull { dir ->
            val f = File(dir, "tool.json")
            if (!f.isFile) return@mapNotNull null
            runCatching {
                json.decodeFromString(CustomToolDef.serializer(), f.readText())
            }.getOrNull()
        }.sortedBy { it.createdAt }
    }

    fun all(): List<CustomToolDef> {
        ensureLoaded()
        return _tools.value
    }

    fun enabled(): List<CustomToolDef> = all().filter { it.enabled }

    fun get(id: String): CustomToolDef? = all().firstOrNull { it.id == id }

    fun findByName(name: String): CustomToolDef? = all().firstOrNull { it.name == name }

    fun newId(): String = UUID.randomUUID().toString()

    fun upsert(def: CustomToolDef): CustomToolDef {
        ensureLoaded()
        val now = System.currentTimeMillis()
        val safeId = if (def.id.isBlank()) newId() else def.id
        val prev = if (def.id.isBlank()) null else get(def.id)
        val finalDef = def.copy(
            id = safeId,
            createdAt = prev?.createdAt ?: (if (def.createdAt > 0L) def.createdAt else now),
            updatedAt = now,
        )
        val dir = toolDir(finalDef.id)
        File(dir, "tool.json").writeText(json.encodeToString(CustomToolDef.serializer(), finalDef))
        writeScript(finalDef, dir)
        val list = _tools.value.toMutableList()
        val idx = list.indexOfFirst { it.id == finalDef.id }
        if (idx >= 0) {
            list[idx] = finalDef
        } else {
            list.add(finalDef)
        }
        _tools.value = list
        return finalDef
    }

    fun delete(id: String): Boolean {
        ensureLoaded()
        val existed = get(id) != null
        toolDir(id).deleteRecursively()
        _tools.value = _tools.value.filterNot { it.id == id }
        return existed
    }

    /**
     * 生成执行用 index.html：包装器在前（把模型传入的 JSON 交给 main(args)），
     * 用户代码在后（定义 main；若自行定义 ai_edge_gallery_get_result 则覆盖包装器）。
     */
    fun writeScript(def: CustomToolDef, dir: File) {
        val sb = StringBuilder()
        sb.append("<!DOCTYPE html>\n<html>\n<head><meta charset='utf-8'></head>\n<body>\n<script>\n")
        sb.append(WRAPPER_JS)
        sb.append("\n</script>\n<script>\n")
        sb.append(def.code)
        sb.append("\n</script>\n</body>\n</html>\n")
        File(dir, "index.html").writeText(sb.toString())
    }

    companion object {
        @Volatile
        private var instance: CustomToolStore? = null

        fun get(context: Context): CustomToolStore {
            instance?.let { return it }
            return synchronized(this) {
                instance ?: CustomToolStore(context.applicationContext).also { instance = it }
            }
        }

        /** 把 AI 写的 main(args) 适配到 JsSkillRunner 的执行契约。 */
        val WRAPPER_JS: String = """window.ai_edge_gallery_get_result = async function (data, secret) {
    var args = {};
    try { args = JSON.parse(data || '{}'); } catch (e) { args = { raw: String(data) }; }
    if (typeof main !== 'function') {
        return { error: 'custom tool must define: async function main(args) { ... return text; }' };
    }
    try {
        var out = await main(args);
        if (typeof out === 'string') { return { result: out }; }
        if (out === undefined || out === null) { return { result: '' }; }
        return { result: JSON.stringify(out) };
    } catch (e) {
        return { error: 'main() threw: ' + (e && e.message ? e.message : String(e)) };
    }
};"""
    }
}

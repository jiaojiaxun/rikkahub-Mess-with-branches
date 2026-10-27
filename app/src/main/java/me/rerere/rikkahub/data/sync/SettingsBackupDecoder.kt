package me.rerere.rikkahub.data.sync

import android.util.Log
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.jsonObject
import me.rerere.ai.provider.ProviderSetting
import me.rerere.asr.ASRProviderSetting
import me.rerere.rikkahub.data.ai.mcp.McpServerConfig
import me.rerere.rikkahub.data.datastore.Settings
import me.rerere.rikkahub.data.datastore.migration.SettingsJsonMigrator
import me.rerere.rikkahub.data.model.Assistant
import me.rerere.tts.provider.TTSProviderSetting

/**
 * rhBackupCompat302: decode a backup settings.json without aborting the whole restore.
 *
 * DataStore reads the providers list element by element (decodeProvidersTolerant), so one
 * unknown polymorphic type cannot wipe every saved provider. The restore path used a single
 * decodeFromString<Settings>, so an old archive carrying a provider type this build no longer
 * ships (or a renamed one) threw SerializationException before the database was applied.
 *
 * Order: strict decode, then element-level repair of the list fields, then null. A null lets
 * BackupArchiveRestorer keep restoring the database and files instead of failing the archive.
 */
object SettingsBackupDecoder {
    private const val TAG = "SettingsBackupDecoder"

    fun decode(json: Json, raw: String): Settings? {
        val migrated = runCatching { SettingsJsonMigrator.migrate(raw) }.getOrDefault(raw)
        val strict = runCatching { json.decodeFromString<Settings>(migrated) }
        strict.getOrNull()?.let { return it }
        warn("strict settings decode failed, repairing list fields", strict.exceptionOrNull())

        val root = runCatching { json.parseToJsonElement(migrated).jsonObject }.getOrNull() ?: return null
        val repaired = root.toMutableMap()
        root["providers"]?.let { repaired["providers"] = keepDecodable<ProviderSetting>(json, it) }
        root["assistants"]?.let { repaired["assistants"] = keepDecodable<Assistant>(json, it) }
        root["ttsProviders"]?.let { repaired["ttsProviders"] = keepDecodable<TTSProviderSetting>(json, it) }
        root["asrProviders"]?.let { repaired["asrProviders"] = keepDecodable<ASRProviderSetting>(json, it) }
        root["mcpServers"]?.let { repaired["mcpServers"] = keepDecodable<McpServerConfig>(json, it) }

        return runCatching { json.decodeFromJsonElement<Settings>(JsonObject(repaired)) }
            .onFailure { warn("settings.json is not decodable even after repair", it) }
            .getOrNull()
    }

    private inline fun <reified T> keepDecodable(json: Json, element: JsonElement): JsonElement {
        val array = element as? JsonArray ?: return element
        val kept = array.filter { entry ->
            runCatching { json.decodeFromJsonElement<T>(entry) }.isSuccess
        }
        return JsonArray(kept)
    }

    private fun warn(message: String, error: Throwable?) {
        runCatching {
            if (error == null) {
                Log.w(TAG, message)
            } else {
                Log.w(TAG, message, error)
            }
        }
    }
}


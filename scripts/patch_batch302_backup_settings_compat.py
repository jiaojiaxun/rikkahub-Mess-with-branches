import os

MARK = "rhBackupCompat302"
RESTORER = "app/src/main/java/me/rerere/rikkahub/data/sync/webdav/BackupArchiveRestorer.kt"
DECODER = "app/src/main/java/me/rerere/rikkahub/data/sync/SettingsBackupDecoder.kt"
TEST = "app/src/test/java/me/rerere/rikkahub/data/model/SettingsBackupDecoderTest.kt"
DIAG = "ci_diag_batch302_backup_settings_compat.txt"

Q = chr(34)
NL = chr(10)
LOG = []

DECODER_SRC = r'''package me.rerere.rikkahub.data.sync

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
        val migrated = SettingsJsonMigrator.migrate(raw)
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
'''

TEST_SRC = r'''package me.rerere.rikkahub.data.model

import me.rerere.rikkahub.data.sync.SettingsBackupDecoder
import me.rerere.rikkahub.utils.JsonInstant
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Test

/** rhBackupCompat302: old backup settings must degrade, never abort the restore. */
class SettingsBackupDecoderTest {

    @Test
    fun `empty object falls back to defaults`() {
        val settings = SettingsBackupDecoder.decode(JsonInstant, "{}")
        assertNotNull(settings)
    }

    @Test
    fun `unknown provider type is dropped without failing the whole archive`() {
        val raw = """
            {"providers":[{"type":"removed_type_xyz","id":"00000000-0000-0000-0000-000000000001","name":"old"}]}
        """.trimIndent()
        val settings = SettingsBackupDecoder.decode(JsonInstant, raw)
        assertNotNull(settings)
        assertEquals(0, settings!!.providers.size)
    }

    @Test
    fun `invalid json returns null instead of throwing`() {
        assertNull(SettingsBackupDecoder.decode(JsonInstant, "not-json"))
    }
}
'''


def write_diag():
    with open(DIAG, "w", encoding="utf-8") as f:
        f.write(NL.join(LOG) + NL)


def note(msg):
    print("::notice title=backup-compat::" + msg)
    LOG.append("OK " + msg)


def fail(msg):
    print("::error title=backup-compat::" + msg)
    LOG.append("FAIL " + msg)
    write_diag()
    raise SystemExit(1)


def write_if_missing(path, content):
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            old = f.read()
        if MARK in old:
            note("skip existing " + path)
            return
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content + NL)
    note("wrote " + path)


def patch_restorer():
    if not os.path.isfile(RESTORER):
        fail("missing " + RESTORER)
    with open(RESTORER, "r", encoding="utf-8") as f:
        src = f.read()
    if "SettingsBackupDecoder" in src:
        note("restorer already patched")
        return
    import_anchor = "import me.rerere.rikkahub.data.sync.BackupRestoreMode"
    if src.count(import_anchor) != 1:
        fail("import anchor count != 1")
    src = src.replace(
        import_anchor,
        import_anchor + NL + "import me.rerere.rikkahub.data.sync.SettingsBackupDecoder",
        1,
    )
    old_line = "importedSettings = json.decodeFromString<Settings>(SettingsJsonMigrator.migrate(raw))"
    lines = src.split(NL)
    idx = -1
    for i in range(len(lines)):
        if old_line in lines[i]:
            idx = i
            break
    if idx < 0:
        fail("settings decode line not found")
    line = lines[idx]
    indent = line[: len(line) - len(line.lstrip())]
    block = []
    block.append(indent + "importedSettings = SettingsBackupDecoder.decode(json, raw)")
    block.append(indent + "if (importedSettings == null) {")
    block.append(indent + "    Log.w(TAG, " + Q + "settings.json 无法解析，跳过设置恢复，数据库与文件仍会继续" + Q + ")")
    block.append(indent + "}")
    lines[idx : idx + 1] = block
    out = NL.join(lines)
    if out.count("SettingsBackupDecoder") < 2:
        fail("post-write marker missing")
    if out.count("(") - out.count(")") != src.count("(") - src.count(")"):
        fail("paren balance changed")
    if out.count("{") - out.count("}") != src.count("{") - src.count("}"):
        fail("brace balance changed")
    with open(RESTORER, "w", encoding="utf-8") as f:
        f.write(out)
    note("patched restorer settings decode")


def main():
    write_if_missing(DECODER, DECODER_SRC)
    write_if_missing(TEST, TEST_SRC)
    patch_restorer()
    LOG.append("compat: old providers/assistants/tts/asr/mcp entries are kept only when decodable")
    LOG.append("compat: settings decode failure no longer aborts database/file restore")
    write_diag()
    print("::notice title=backup-compat::batch302 finished")


main()

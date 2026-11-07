package me.rerere.rikkahub.data.model

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


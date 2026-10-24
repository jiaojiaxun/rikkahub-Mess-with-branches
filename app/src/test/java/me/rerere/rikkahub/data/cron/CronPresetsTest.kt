package me.rerere.rikkahub.data.cron

import me.rerere.rikkahub.data.model.CronParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** rhCronPresets: 预设必须都能被真实调度器解析，否则「预设」就是死数据。 */
class CronPresetsTest {

    @Test
    fun `every preset parses to a next run`() {
        assertTrue(CronPresets.ALL.isNotEmpty())
        CronPresets.ALL.forEach { preset ->
            assertTrue(
                "invalid cron for " + preset.id + ": " + preset.cronExpression,
                CronParser.isValid(preset.cronExpression),
            )
            assertNotNull(
                "no next run for " + preset.id,
                CronParser.parseNextRun(preset.cronExpression, 0L),
            )
        }
    }

    @Test
    fun `preset ids are unique and resolvable`() {
        val ids = CronPresets.ALL.map { it.id }
        assertEquals(ids.size, ids.distinct().size)
        CronPresets.ALL.forEach { preset ->
            assertEquals(preset.cronExpression, CronPresets.resolve(preset.id)?.cronExpression)
        }
        assertNull(CronPresets.resolve("nope"))
        assertNull(CronPresets.resolve(null))
    }

    @Test
    fun `titles and descriptions are non blank`() {
        CronPresets.ALL.forEach { preset ->
            assertTrue(preset.id, preset.title.isNotBlank())
            assertTrue(preset.id, preset.description.isNotBlank())
        }
    }
}

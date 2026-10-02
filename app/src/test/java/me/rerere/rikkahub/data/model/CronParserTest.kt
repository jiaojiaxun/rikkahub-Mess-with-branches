package me.rerere.rikkahub.data.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Calendar

class CronParserTest {

    @Test
    fun `every minute`() {
        val next = CronParser.parseNextRun("* * * * *", 0L)
        assertNotNull(next)
        assertEquals(60_000L, next)  // 下一分钟整点
    }

    @Test
    fun `every hour at minute 30`() {
        val base = 0L  // 1970-01-01 00:00:00
        val next = CronParser.parseNextRun("30 * * * *", base)
        assertNotNull(next)
        assertEquals(30 * 60_000L, next)  // 00:30:00
    }

    @Test
    fun `daily at 9 AM`() {
        val cal = Calendar.getInstance().apply {
            set(2026, 0, 1, 8, 0, 0)  // 2026-01-01 08:00:00
            set(Calendar.MILLISECOND, 0)
        }
        val next = CronParser.parseNextRun("0 9 * * *", cal.timeInMillis)
        assertNotNull(next)

        val resultCal = Calendar.getInstance().apply { timeInMillis = next!! }
        assertEquals(9, resultCal.get(Calendar.HOUR_OF_DAY))
        assertEquals(0, resultCal.get(Calendar.MINUTE))
    }

    @Test
    fun `weekly on Monday 10 AM`() {
        val cal = Calendar.getInstance().apply {
            set(2026, 0, 1, 0, 0, 0)  // 2026-01-01 (周四)
            set(Calendar.MILLISECOND, 0)
        }
        val next = CronParser.parseNextRun("0 10 * * 1", cal.timeInMillis)  // 周一10点
        assertNotNull(next)

        val resultCal = Calendar.getInstance().apply { timeInMillis = next!! }
        assertEquals(Calendar.MONDAY, resultCal.get(Calendar.DAY_OF_WEEK))
        assertEquals(10, resultCal.get(Calendar.HOUR_OF_DAY))
    }

    @Test
    fun `step values - every 15 minutes`() {
        val base = 0L
        val next = CronParser.parseNextRun("*/15 * * * *", base)
        assertNotNull(next)
        assertEquals(15 * 60_000L, next)  // 00:15:00
    }

    @Test
    fun `range values - hours 9-17`() {
        val cal = Calendar.getInstance().apply {
            set(2026, 0, 1, 8, 30, 0)  // 2026-01-01 08:30:00
            set(Calendar.MILLISECOND, 0)
        }
        val next = CronParser.parseNextRun("0 9-17 * * *", cal.timeInMillis)
        assertNotNull(next)

        val resultCal = Calendar.getInstance().apply { timeInMillis = next!! }
        assertEquals(9, resultCal.get(Calendar.HOUR_OF_DAY))  // 下一个9点
    }

    @Test
    fun `list values - specific minutes`() {
        val base = 0L
        val next = CronParser.parseNextRun("0,30 * * * *", base)
        assertNotNull(next)
        assertEquals(30 * 60_000L, next)  // 00:30:00
    }

    @Test
    fun `invalid expressions`() {
        assertFalse(CronParser.isValid("* * * *"))  // 只有4位
        assertFalse(CronParser.isValid("60 * * * *"))  // 分钟超出范围
        assertFalse(CronParser.isValid("* 25 * * *"))  // 小时超出范围
        assertFalse(CronParser.isValid("abc * * * *"))  // 非数字
        assertFalse(CronParser.isValid("* * 0 * *"))  // 日不能为0
        assertFalse(CronParser.isValid("* * * 13 *"))  // 月超出范围
    }

    @Test
    fun `valid expressions`() {
        assertTrue(CronParser.isValid("* * * * *"))
        assertTrue(CronParser.isValid("*/5 9-17 * * 1-5"))  // 工作时间每5分钟
        assertTrue(CronParser.isValid("0 0 1 * *"))  // 每月1号0点
        assertTrue(CronParser.isValid("30 4 * * 0"))  // 周日4:30
    }

    @Test
    fun `complex expression`() {
        val cal = Calendar.getInstance().apply {
            set(2026, 0, 1, 12, 0, 0)  // 2026-01-01 12:00:00
            set(Calendar.MILLISECOND, 0)
        }
        // 每月1号和15号的0点、12点
        val next = CronParser.parseNextRun("0 0,12 1,15 * *", cal.timeInMillis)
        assertNotNull(next)

        val resultCal = Calendar.getInstance().apply { timeInMillis = next!! }
        assertEquals(15, resultCal.get(Calendar.DAY_OF_MONTH))  // 本月15号
        assertEquals(12, resultCal.get(Calendar.HOUR_OF_DAY))  // 12点
    }
}

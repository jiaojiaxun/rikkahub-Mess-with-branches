package me.rerere.rikkahub.data.ai.context

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ContextUsageEstimateTest {
    @Test
    fun `unknown window has no fake ratio`() {
        val estimate = ContextUsageEstimate.create(
            estimatedInputTokens = 12_000,
            contextWindowTokens = null,
            reservedOutputTokens = 4_000,
            approximate = true,
            contextWindowSource = ContextWindowSource.Unknown,
            uncountedMultimodalParts = 0,
        )
        assertNull(estimate.usageRatio)
        assertEquals(ContextUsageLevel.Unknown, estimate.level)
    }

    @Test
    fun `risk boundaries are exact`() {
        assertEquals(ContextUsageLevel.Normal, ContextUsageLevel.fromRatio(0.59f))
        assertEquals(ContextUsageLevel.Notice, ContextUsageLevel.fromRatio(0.60f))
        assertEquals(ContextUsageLevel.Notice, ContextUsageLevel.fromRatio(0.79f))
        assertEquals(ContextUsageLevel.Warning, ContextUsageLevel.fromRatio(0.80f))
        assertEquals(ContextUsageLevel.Warning, ContextUsageLevel.fromRatio(0.94f))
        assertEquals(ContextUsageLevel.Critical, ContextUsageLevel.fromRatio(0.95f))
        assertEquals(ContextUsageLevel.Critical, ContextUsageLevel.fromRatio(1.20f))
    }

    @Test
    fun `remaining may be negative while progress is clamped`() {
        val estimate = ContextUsageEstimate.create(
            estimatedInputTokens = 140_000,
            contextWindowTokens = 128_000,
            reservedOutputTokens = 8_000,
            approximate = true,
            contextWindowSource = ContextWindowSource.ProviderMetadata,
            uncountedMultimodalParts = 0,
        )
        assertEquals(-20_000L, estimate.remainingTokens)
        assertTrue(estimate.usageRatio!! > 1f)
        assertEquals(1f, estimate.progress)
    }
}

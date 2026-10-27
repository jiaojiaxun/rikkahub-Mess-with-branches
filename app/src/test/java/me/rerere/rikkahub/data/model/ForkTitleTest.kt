package me.rerere.rikkahub.data.model

import org.junit.Assert.assertEquals
import org.junit.Test

/**
 * rh-batch14: "修复分叉对话标题序号重复叠加".
 *
 * The stacking case is the point of these assertions: forking a fork used to append another
 * suffix on top of the previous one. nextForkTitle strips every existing trailing "(n)" before
 * appending, so the suffix count never grows and the number keeps moving forward.
 */
class ForkTitleTest {
    @Test
    fun `blank parent title stays blank`() {
        assertEquals("", nextForkTitle(""))
        assertEquals("", nextForkTitle("   "))
    }

    @Test
    fun `first fork of an unnumbered title is the second copy`() {
        assertEquals("标题 (2)", nextForkTitle("标题"))
    }

    @Test
    fun `forking a fork advances the number instead of stacking`() {
        assertEquals("标题 (3)", nextForkTitle("标题 (2)"))
        assertEquals("标题 (4)", nextForkTitle("标题 (3)"))
    }

    @Test
    fun `already stacked suffixes collapse to a single number`() {
        // The regression itself: a title corrupted by an older build must not gain a third
        // suffix, and must not keep the stale one either.
        assertEquals("标题 (2)", nextForkTitle("标题 (1) (1)"))
        assertEquals("标题 (3)", nextForkTitle("标题 (1) (2)"))
    }

    @Test
    fun `suffix without a preceding space is recognised`() {
        assertEquals("标题 (8)", nextForkTitle("标题(7)"))
    }

    @Test
    fun `surrounding whitespace is trimmed`() {
        assertEquals("标题 (2)", nextForkTitle("  标题  "))
        assertEquals("标题 (3)", nextForkTitle(" 标题 (2) "))
    }

    @Test
    fun `non numeric parentheses are left intact`() {
        assertEquals("标题 (草稿) (2)", nextForkTitle("标题 (草稿)"))
    }

    @Test
    fun `a title that is only a suffix is returned unchanged`() {
        assertEquals("(1)", nextForkTitle("(1)"))
    }
}

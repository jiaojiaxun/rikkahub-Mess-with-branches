package me.rerere.rikkahub.data.ai.limits

/**
 * App-wide @Volatile runtime holder for tool execution limits that span all tool families.
 * Currently holds the per-turn wall-clock budget that was previously hardcoded in
 * GenerationHandler.kt. The values are app-scoped defaults and do not depend on optional
 * integrations.
 */
object ToolRuntimeLimits {
    @Volatile var turnBudgetMs: Long = 10L * 60L * 1_000L

    /**
     * Tool-call iterations a single turn may run before it is force-ended.
     */
    @Volatile var maxToolSteps: Int = 32
}

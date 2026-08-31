package me.rerere.rikkahub.data.ai.tools

/**
 * Phase 17 stability — context every tool factory in [LocalTools.getTools] sees about WHO
 * is invoking it. Until this layer existed, tools that needed to know the calling
 * conversation / assistant id and model capabilities had no way to read them — tools
 * shipped with placeholder defaults and silent gaps the audit caught.
 *
 * Convention: every getTools() caller MUST construct a ToolInvocationContext with the most
 * specific data it has. The default ([EMPTY]) is a no-op safe fallback used when the
 * caller doesn't track the data (legacy / one-off paths) — but factories should treat the
 * empty context as "I don't know" not "no constraints", and apply conservative defaults.
 *
 * Fields:
 *  - [callerAssistantId]: the assistant whose toggles are being dispatched. ChatService
 *    supplies this from the active assistant settings.
 *  - [callerConversationId]: the conversation UUID of the user-facing chat.
 *  - [modelCanSeeImages]: true iff the model handling this turn has image input in its
 *    modalities. `show_image` reads this so a text-only model is told plainly it cannot
 *    see the picture (and must OCR / file-process it) instead of being handed dimensions
 *    that read like "I looked at it" — the root cause of confabulated image descriptions.
 *    Defaults to `true`: the no-knowledge fallback preserves the pre-fix behaviour, and
 *    ChatService (the only LLM-driven dispatch path) always sets it explicitly.
 */
data class ToolInvocationContext(
    val callerAssistantId: String? = null,
    val callerConversationId: String? = null,
    val modelCanSeeImages: Boolean = true,
) {
    companion object {
        /** No-knowledge fallback. Factories that depend on context MUST handle this. */
        val EMPTY = ToolInvocationContext()
    }
}

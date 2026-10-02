from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MARKER = "rh-batch15"


def flat(value: str) -> str:
    return "".join(value.split())


def replace_once(source: str, old: str, new: str, label: str) -> str:
    needle = flat(old)
    compact = flat(source)
    count = compact.count(needle)
    if count != 1:
        raise RuntimeError(f"{MARKER}: {label}: expected 1 anchor, found {count}")
    start_compact = compact.index(needle)
    positions = []
    for index, char in enumerate(source):
        if not char.isspace():
            positions.append(index)
    start = positions[start_compact]
    end = positions[start_compact + len(needle) - 1] + 1
    return source[:start] + new + source[end:]


def apply_file(relative: str, edits: list[tuple[str, str, str]]) -> None:
    path = ROOT / relative
    source = path.read_text()
    if MARKER in source:
        print(f"{MARKER}: already applied {relative}")
        return
    updated = source
    try:
        for old, new, label in edits:
            updated = replace_once(updated, old, new, label)
    except Exception as error:
        print(f"::error::{error}")
        raise
    path.write_text(updated)
    print(f"{MARKER}: patched {relative}")


planner_edits = [
    (
        """import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart""",
        """import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.Tool
import me.rerere.ai.provider.Model
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart""",
        "planner imports",
    ),
    (
        """    private const val CHARS_PER_TOKEN = 3
    private const val MESSAGE_OVERHEAD_TOKENS = 8
    private const val MEDIA_PART_TOKENS = 1_024""",
        """    private const val CHARS_PER_TOKEN = 3
    private const val MESSAGE_OVERHEAD_TOKENS = 8
    private const val MEDIA_PART_TOKENS = 1_024
    /** Per-tool JSON envelope around the function declaration. */
    private const val TOOL_SCHEMA_ENVELOPE_TOKENS = 16L""",
        "planner constants",
    ),
    (
        """        thresholdTokensK: Int? = null,
        reservedTokens: Int = 0,
    ): ContextBudgetPlan {""",
        """        thresholdTokensK: Int? = null,
        reservedTokens: Int = 0,
        requestOverheadTokens: Long = 0,
    ): ContextBudgetPlan {""",
        "planner signature",
    ),
    (
        """        val estimatedInputTokens = estimateInputTokens(messages)""",
        """        val estimatedInputTokens = estimateInputTokens(messages, requestOverheadTokens)""",
        "planner estimate call",
    ),
    (
        """    fun estimateInputTokens(messages: List<UIMessage>): Int {""",
        """    fun estimateInputTokens(
        messages: List<UIMessage>,
        requestOverheadTokens: Long = 0,
    ): Int {""",
        "input estimate signature",
    ),
    (
        """        } else {
            messages.sumOf(::estimateMessageTokens)
        }""",
        """        } else {
            // No provider usage exists to anchor the estimate. Include the request material
            // that lives outside the message list, or compaction will trigger too late.
            messages.sumOf(::estimateMessageTokens) + requestOverheadTokens.coerceAtLeast(0)
        }""",
        "fallback overhead",
    ),
    (
        """    fun estimateContextTokens(messages: List<UIMessage>): Int = messages
        .sumOf(::estimateMessageTokens)
        .coerceAtMost(Int.MAX_VALUE.toLong())
        .toInt()""",
        """    fun estimateContextTokens(
        messages: List<UIMessage>,
        requestOverheadTokens: Long = 0,
    ): Int = (messages.sumOf(::estimateMessageTokens) + requestOverheadTokens.coerceAtLeast(0))
        .coerceAtMost(Int.MAX_VALUE.toLong())
        .toInt()""",
        "context estimate signature",
    ),
    (
        """    fun estimateMessageTokens(message: UIMessage): Long {""",
        """    /**
     * Estimates tokens sent outside the message list: system prompt, memory, tool prompts,
     * and each tool's JSON declaration. Provider usage already includes this for the request
     * it describes; callers must pass it for local fallback and post-compaction estimates.
     */
    fun estimateRequestOverheadTokens(
        systemPromptText: String,
        tools: List<Tool>,
        memoryText: String = "",
        modelForToolPrompts: Model? = null,
    ): Long {
        val promptTokens = estimateTextTokens(systemPromptText) + estimateTextTokens(memoryText)
        val toolTokens = tools.sumOf { tool ->
            val toolPromptTokens = modelForToolPrompts?.let { model ->
                runCatching { tool.systemPrompt(model, emptyList()) }
                    .getOrDefault("")
                    .let(::estimateTextTokens)
            } ?: 0L
            estimateTextTokens(tool.name) +
                estimateTextTokens(tool.description) +
                estimateToolSchemaTokens(tool) +
                toolPromptTokens +
                TOOL_SCHEMA_ENVELOPE_TOKENS
        }
        return promptTokens + toolTokens
    }

    private fun estimateToolSchemaTokens(tool: Tool): Long {
        val schema = runCatching { tool.parameters() }.getOrNull() as? InputSchema.Obj
            ?: return 0L
        var tokens = 0L
        schema.properties.forEach { (name, element) ->
            tokens += estimateTextTokens(name) + estimateJsonElementTokens(element)
        }
        schema.required?.let { tokens += estimateTextTokens(it.joinToString(",")) }
        return tokens
    }

    private fun estimateJsonElementTokens(element: JsonElement): Long = when (element) {
        is JsonObject -> element.keys.sumOf { estimateTextTokens(it) } +
            element.values.sumOf { estimateJsonElementTokens(it) }
        is JsonArray -> element.sumOf { estimateJsonElementTokens(it) }
        is JsonPrimitive -> estimateTextTokens(element.content)
    }

    fun estimateMessageTokens(message: UIMessage): Long {""",
        "request overhead estimator",
    ),
]

chat_edits = [
    (
        """            generationHandler.generateText(
                settings = settings,
                model = model,""",
        """            // rh-batch15: filled after the actual tools list is assembled below.
            val requestOverheadTokens = java.util.concurrent.atomic.AtomicLong(0L)
            generationHandler.generateText(
                settings = settings,
                model = model,""",
        "request overhead holder",
    ),
    (
        """                },
            ).onCompletion { completionCause ->""",
        """                }.also { assembledTools ->
                    // Measure the same tool declarations used by the request. Provider usage
                    // covers these only when it exists; fallback estimates otherwise missed them.
                    requestOverheadTokens.set(
                        ContextBudgetPlanner.estimateRequestOverheadTokens(
                            systemPromptText = buildString {
                                append(assistant.systemPrompt)
                                conversation.customSystemPrompt?.takeIf { it.isNotBlank() }?.let {
                                    appendLine()
                                    append(it)
                                }
                            },
                            memoryText = (
                                if (assistant.useGlobalMemory) {
                                    memoryRepository.getGlobalMemories()
                                } else {
                                    memoryRepository.getMemoriesOfAssistant(assistant.id.toString())
                                }
                            ).joinToString("\\n") { it.content },
                            tools = assembledTools,
                            modelForToolPrompts = model,
                        )
                    )
                },
            ).onCompletion { completionCause ->""",
        "assembled tools overhead",
    ),
    (
        """                        val nextRequestTokens = ContextBudgetPlanner
                            .estimateInputTokens(generatedMessages)""",
        """                        val nextRequestTokens = ContextBudgetPlanner
                            .estimateInputTokens(
                                generatedMessages,
                                requestOverheadTokens = requestOverheadTokens.get(),
                            )""",
        "on-after-tool estimate",
    ),
    (
        """        force: Boolean = false,
        compactEntireContext: Boolean = false,
    ): CompactedMessageView {""",
        """        force: Boolean = false,
        compactEntireContext: Boolean = false,
        requestOverheadTokens: Long = 0,
    ): CompactedMessageView {""",
        "compaction signature",
    ),
    (
        """                        ContextBudgetPlanner.estimateContextTokens(firstView.messages) >= triggerTokens""",
        """                        ContextBudgetPlanner.estimateContextTokens(
                            firstView.messages,
                            requestOverheadTokens,
                        ) >= triggerTokens""",
        "post-compaction estimate",
    ),
    (
        """                                processingStatus = session.processingStatus,
                                force = true,
                            )""",
        """                                processingStatus = session.processingStatus,
                                force = true,
                                requestOverheadTokens = requestOverheadTokens.get(),
                            )""",
        "force compaction callback",
    ),
    (
        """                    processingStatus = session.processingStatus,
                    force = true,
                    compactEntireContext = true,
                )""",
        """                    processingStatus = session.processingStatus,
                    force = true,
                    compactEntireContext = true,
                    requestOverheadTokens = requestOverheadTokens.get(),
                )""",
        "context-limit recovery",
    ),
]

apply_file("app/src/main/java/me/rerere/rikkahub/data/ai/ContextBudgetPlanner.kt", planner_edits)
apply_file("app/src/main/java/me/rerere/rikkahub/service/ChatService.kt", chat_edits)


test_path = ROOT / "app/src/test/java/me/rerere/rikkahub/data/ai/ContextBudgetPlannerOverheadTest.kt"
if test_path.exists():
    print(f"{MARKER}: already exists {test_path}")
else:
    test_path.write_text(
        '''package me.rerere.rikkahub.data.ai

import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import me.rerere.ai.core.InputSchema
import me.rerere.ai.core.MessageRole
import me.rerere.ai.core.TokenUsage
import me.rerere.ai.core.Tool
import me.rerere.ai.provider.Model
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ContextBudgetPlannerOverheadTest {
    @Test
    fun `fallback estimate adds overhead while usage estimate does not double count it`() {
        val messages = listOf(UIMessage.user("x".repeat(300)))
        assertEquals(608, ContextBudgetPlanner.estimateInputTokens(messages, 500))

        val withUsage = listOf(
            UIMessage(
                role = MessageRole.ASSISTANT,
                parts = listOf(UIMessagePart.Text("done")),
                usage = TokenUsage(promptTokens = 5_000, completionTokens = 1_000, totalTokens = 6_000),
            ),
        )
        assertEquals(6_000, ContextBudgetPlanner.estimateInputTokens(withUsage, 500))
    }

    @Test
    fun `request overhead counts prompt and tool schema fields`() {
        val tool = Tool(
            name = "get_weather",
            description = "Get current weather",
            parameters = {
                InputSchema.Obj(
                    properties = buildJsonObject {
                        put("city", buildJsonObject { put("type", "string") })
                    },
                    required = listOf("city"),
                )
            },
            execute = { emptyList<UIMessagePart>() },
        )

        assertEquals(41L, ContextBudgetPlanner.estimateRequestOverheadTokens(
            "You are helpful.",
            listOf(tool),
        ))
    }

    @Test
    fun `tool system prompt is measured and a throwing prompt cannot break accounting`() {
        val tool = Tool(
            name = "t",
            description = "",
            systemPrompt = { _, _ -> "Guidance " + "y".repeat(300) },
            execute = { emptyList<UIMessagePart>() },
        )
        assertEquals(120L, ContextBudgetPlanner.estimateRequestOverheadTokens(
            "",
            listOf(tool),
            modelForToolPrompts = Model(),
        ))

        val throwing = Tool(
            name = "t",
            description = "",
            systemPrompt = { _, messages -> error("needs ${messages.size}") },
            execute = { emptyList<UIMessagePart>() },
        )
        assertEquals(17L, ContextBudgetPlanner.estimateRequestOverheadTokens(
            "",
            listOf(throwing),
            modelForToolPrompts = Model(),
        ))
    }

    @Test
    fun `plan and post compaction estimate include overhead`() {
        val messages = listOf(UIMessage.user("x".repeat(300)))
        val noOverhead = ContextBudgetPlanner.plan(messages, 1_000, 50)
        assertFalse(noOverhead.shouldCompact)

        val withOverhead = ContextBudgetPlanner.plan(
            messages = messages,
            contextLength = 1_000,
            thresholdPercent = 50,
            requestOverheadTokens = 500,
        )
        assertEquals(500, withOverhead.triggerTokens)
        assertTrue(withOverhead.shouldCompact)
        assertEquals(608, ContextBudgetPlanner.estimateContextTokens(messages, 500))
    }

    @Test
    fun `memory text contributes to request overhead`() {
        assertEquals(
            300L,
            ContextBudgetPlanner.estimateRequestOverheadTokens(
                systemPromptText = "",
                tools = emptyList(),
                memoryText = "文".repeat(300),
            ),
        )
    }
}
'''
    )
    print(f"{MARKER}: created {test_path}")

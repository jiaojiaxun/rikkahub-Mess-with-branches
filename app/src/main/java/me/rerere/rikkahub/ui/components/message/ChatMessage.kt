package me.rerere.rikkahub.ui.components.message

import android.content.Intent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.clickable
import androidx.compose.foundation.background
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.ProvideTextStyle
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.LinkAnnotation
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withLink
import androidx.compose.ui.unit.dp
import androidx.compose.ui.util.fastAll
import androidx.compose.ui.util.fastForEach
import androidx.compose.ui.util.fastForEachIndexed
import androidx.core.content.FileProvider
import androidx.core.net.toFile
import androidx.core.net.toUri
import kotlinx.coroutines.FlowPreview
import kotlinx.coroutines.flow.debounce
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import me.rerere.ai.core.MessageRole
import me.rerere.ai.provider.Model
import me.rerere.ai.ui.ToolApprovalState
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessageAnnotation
import me.rerere.ai.ui.UIMessagePart
import me.rerere.ai.ui.isEmptyUIMessage
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.File02
import me.rerere.hugeicons.stroke.Sparkles
import me.rerere.hugeicons.stroke.MusicNote03
import me.rerere.hugeicons.stroke.Video01
import me.rerere.rikkahub.R
import me.rerere.rikkahub.Screen
import me.rerere.rikkahub.data.model.Avatar
import me.rerere.rikkahub.data.model.Assistant
import me.rerere.rikkahub.data.translation.TranslationMode
import me.rerere.rikkahub.data.model.AssistantAffectScope
import me.rerere.rikkahub.data.model.MessageNode
import me.rerere.rikkahub.data.model.replaceRegexes
import me.rerere.rikkahub.ui.components.richtext.MarkdownBlock
import me.rerere.rikkahub.ui.components.richtext.HighlightCodeBlock
import me.rerere.rikkahub.ui.components.richtext.ZoomableAsyncImage
import me.rerere.rikkahub.ui.components.richtext.buildMarkdownPreviewHtml
import me.rerere.rikkahub.ui.components.webview.WebViewContentCache
import me.rerere.rikkahub.ui.components.ui.ChainOfThought
import me.rerere.rikkahub.ui.components.ui.Favicon
import me.rerere.rikkahub.ui.context.LocalNavController
import me.rerere.rikkahub.ui.modifier.shimmer
import me.rerere.rikkahub.ui.context.LocalSettings
import me.rerere.rikkahub.ui.theme.LocalChatFontFamily
import me.rerere.rikkahub.ui.theme.rememberChatFontFamily
import me.rerere.rikkahub.ui.theme.extendColors
import me.rerere.rikkahub.utils.JsonInstant
import me.rerere.rikkahub.utils.openUrl
import me.rerere.rikkahub.utils.urlDecode
import java.util.Locale
import kotlin.time.Duration.Companion.milliseconds
import androidx.compose.foundation.layout.fillMaxSize // rhAttachCard
import androidx.compose.foundation.shape.CircleShape // rhAttachCard
import me.rerere.hugeicons.stroke.Download01 // rhAttachCard
import me.rerere.rikkahub.utils.fileSizeToString // rhAttachCard

@Composable
fun ChatMessage(
    node: MessageNode,
    // Tolerant default: node.currentMessage throws when selectIndex is stale, and a default
    // argument is evaluated before the body runs, so the guard below could never catch it.
    displayMessage: UIMessage = node.messages.getOrNull(node.selectIndex)
        ?: node.messages.lastOrNull()
        ?: UIMessage.assistant(""),
    modifier: Modifier = Modifier,
    loading: Boolean = false,
    // Whether a generation is running anywhere in this conversation, independent of
    // `loading` (which the caller narrows to this node being the last message) - see the
    // rerun-button gate in ChatMessageToolStep, which must not show while any generation
    // is in flight, not just one on this exact message.
    generationActive: Boolean = loading,
    model: Model? = null,
    estimatedContextTokens: Int? = null,
    assistant: Assistant? = null,
    lastMessage: Boolean = false,
    onFork: () -> Unit,
    onRegenerate: () -> Unit,
    onEdit: () -> Unit,
    onShare: () -> Unit,
    onDelete: () -> Unit,
    onUpdate: (MessageNode) -> Unit,
    isFavorite: Boolean = false,
    onToggleFavorite: (() -> Unit)? = null,
    onTranslate: ((UIMessage, Locale, TranslationMode) -> Unit)? = null,
    onClearTranslation: (UIMessage) -> Unit = {},
    onToolApproval: ((toolCallId: String, approved: Boolean, reason: String, scope: me.rerere.rikkahub.service.ChatService.ApprovalScope, toolName: String) -> Unit)? = null,
    onToolAnswer: ((toolCallId: String, answer: String) -> Unit)? = null,
    onRerunTool: (suspend (toolCallId: String) -> me.rerere.rikkahub.service.ChatService.RerunToolResult)? = null,
    onQuote: (() -> Unit)? = null, // rhQuoteMenu
// rhUserAvatarEdit: 点消息处头像/昵称分别弹改头像/改昵称(对话页为唯一编辑入口)
onChangeUserAvatar: ((Avatar) -> Unit)? = null,
onEditUserNickname: (() -> Unit)? = null,
) {
    // node.selectIndex can be stale (e.g. after a branch/message was removed) or the
    // node can be empty; degrade to the last message, or render nothing, instead of
    // crashing with an IndexOutOfBoundsException.
    if (node.messages.isEmpty()) return
    val message = displayMessage
    val actionMessage = node.messages.getOrNull(node.selectIndex) ?: node.messages.last()
    val settings = LocalSettings.current.displaySetting
    val chatFontFamily = LocalChatFontFamily.current ?: rememberChatFontFamily(settings)
    val textStyle = LocalTextStyle.current.copy(
        fontSize = LocalTextStyle.current.fontSize * settings.fontSizeRatio,
        lineHeight = LocalTextStyle.current.lineHeight * settings.fontSizeRatio,
        fontFamily = chatFontFamily
    )
    var showActionsSheet by remember { mutableStateOf(false) }
    var showSelectCopySheet by remember { mutableStateOf(false) }
    val navController = LocalNavController.current
    val context = LocalContext.current
    val colorScheme = MaterialTheme.colorScheme
    Column(
        modifier = modifier.fillMaxWidth(),
        horizontalAlignment = if (message.role == MessageRole.USER) Alignment.End else Alignment.Start,
        verticalArrangement = Arrangement.spacedBy(4.dp)
    ) {
        if (!message.parts.isEmptyUIMessage()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End),
            ) {
                ChatMessageAssistantAvatar(
                    message = message,
                    model = model,
                    assistant = assistant,
                    loading = loading,
                    modifier = Modifier.weight(1f)
                )
                ChatMessageUserAvatar(
                    message = message,
                    avatar = settings.userAvatar,
                    nickname = settings.userNickname,
                    modifier = Modifier.weight(1f),
                // rhUserAvatarEdit
                onChangeAvatar = onChangeUserAvatar,
                onEditNickname = onEditUserNickname,
                )
            }
        }
        // rhLiteStream (batch53): 精简流式——流式末条消息纯文本直出, 生成完成自动切回完整渲染
        if (settings.liteStreamRender && loading && lastMessage) {
            ProvideTextStyle(textStyle) {
                LiteStreamingText(parts = message.parts)
            }
        } else
        ProvideTextStyle(textStyle) {
            MessagePartsBlock(
                assistant = assistant,
                role = message.role,
                parts = message.parts,
                annotations = message.annotations,
                loading = loading,
                generationActive = generationActive,
                model = model,
                onToolApproval = onToolApproval,
                onToolAnswer = onToolAnswer,
                onRerunTool = onRerunTool,
                onUserMessageClick = if (message.role == MessageRole.USER) onEdit else null,
            )

            message.translation?.let { translation ->
                CollapsibleTranslationText(
                    content = translation,
                    onClickCitation = {}
                )
            }
        }

        val showActions = if (lastMessage) {
            !loading
        } else {
            message.parts.isEmptyUIMessage().not()
        }

        AnimatedVisibility(
            visible = showActions,
            enter = slideInVertically { it / 2 } + fadeIn(),
            exit = slideOutVertically { it / 2 } + fadeOut()
        ) {
            Column(
                modifier = Modifier.animateContentSize()
            ) {
                ChatMessageActionButtons(
                    message = actionMessage,
                    onRegenerate = onRegenerate,
                    node = node,
                    onUpdate = onUpdate,
                    onOpenActionSheet = {
                        showActionsSheet = true
                    },
                    onTranslate = onTranslate,
                    onClearTranslation = onClearTranslation
                )
            }
        }

        EditedFilesList(
            parts = message.parts,
            assistant = assistant,
        )

        ProvideTextStyle(textStyle) {
            ChatMessageNerdLine(
                message = message,
                contextLength = model?.contextLength,
                modelIdentifier = model?.modelId,
                estimatedContextTokens = estimatedContextTokens,
            )
        }

    }
    if (showActionsSheet) {
        ChatMessageActionsSheet(
            message = actionMessage,
            onEdit = onEdit,
            onDelete = onDelete,
            onShare = onShare,
            onFork = onFork,
            model = model,
            onSelectAndCopy = {
                showSelectCopySheet = true
            },
            isFavorite = isFavorite,
            onToggleFavorite = onToggleFavorite,
            onWebViewPreview = {
                val textContent = message.parts
                    .filterIsInstance<UIMessagePart.Text>()
                    .joinToString("\n\n") { it.text }
                    .trim()
                if (textContent.isNotBlank()) {
                    val htmlContent = buildMarkdownPreviewHtml(
                        context = context,
                        markdown = textContent,
                        colorScheme = colorScheme
                    )
                    val contentId = WebViewContentCache.store(context.cacheDir, htmlContent)
                    navController.navigate(Screen.WebView(contentId = contentId))
                }
            },
            onQuote = onQuote,
            onDismissRequest = {
                showActionsSheet = false
            }
        )
    }

    if (showSelectCopySheet) {
        ChatMessageCopySheet(
            message = message,
            onDismissRequest = {
                showSelectCopySheet = false
            }
        )
    }
}

@OptIn(FlowPreview::class)
@Composable
private fun LiteStreamingText(
    parts: List<UIMessagePart>,
) {
    // rhLiteStream (batch53): 最轻量流式渲染——纯 Text 直出, 跳过 Markdown
    // 解析/SelectionContainer/ChainOfThought 动画。chunk 只触发一个 Text 重绘。
    val nl = System.lineSeparator() + System.lineSeparator()
    val text = parts.filterIsInstance<UIMessagePart.Text>()
        .joinToString(nl) { it.text }
    val reasoning = parts.filterIsInstance<UIMessagePart.Reasoning>()
        .joinToString(nl) { it.reasoning }
    val combined = buildString {
        if (reasoning.isNotBlank()) {
            append(reasoning)
            append(nl)
        }
        append(text)
        append(" ...")
    }
    Text(text = combined, style = MaterialTheme.typography.bodyMedium)
}

@Composable
private fun MessagePartsBlock(
    assistant: Assistant?,
    role: MessageRole,
    model: Model?,
    parts: List<UIMessagePart>,
    annotations: List<UIMessageAnnotation>,
    loading: Boolean,
    generationActive: Boolean = loading,
    onToolApproval: ((toolCallId: String, approved: Boolean, reason: String, scope: me.rerere.rikkahub.service.ChatService.ApprovalScope, toolName: String) -> Unit)? = null,
    onToolAnswer: ((toolCallId: String, answer: String) -> Unit)? = null,
    onRerunTool: (suspend (toolCallId: String) -> me.rerere.rikkahub.service.ChatService.RerunToolResult)? = null,
    onUserMessageClick: (() -> Unit)? = null,
) {
    val context = LocalContext.current
    val contentColor = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.65f)

    // 消息输出HapticFeedback
    val hapticFeedback = LocalHapticFeedback.current
    val settings = LocalSettings.current
    val partsState by rememberUpdatedState(parts)

    val handleClickCitation: (String) -> Unit = remember {
        handler@{ citationId ->
            partsState.forEach { part ->
                if (part is UIMessagePart.Tool && part.toolName == "search_web" && part.isExecuted) {
                    val outputText = part.output.filterIsInstance<UIMessagePart.Text>().joinToString("\n") { it.text }
                    val items =
                        runCatching { JsonInstant.parseToJsonElement(outputText).jsonObject["items"]?.jsonArray }.getOrNull()
                            ?: return@forEach
                    items.forEach { item ->
                        val id = item.jsonObject["id"]?.jsonPrimitive?.content ?: return@forEach
                        val url = item.jsonObject["url"]?.jsonPrimitive?.content ?: return@forEach
                        if (citationId == id) {
                            context.openUrl(url)
                            return@handler
                        }
                    }
                }
            }
        }
    }
    LaunchedEffect(settings.displaySetting) {
        snapshotFlow { partsState }
            .debounce(50.milliseconds)
            .collect { parts ->
                if (parts.isNotEmpty() && loading && settings.displaySetting.enableMessageGenerationHapticEffect) {
                    hapticFeedback.performHapticFeedback(HapticFeedbackType.KeyboardTap)
                }
            }
    }

    // Render parts in original order (group thinking/tool as chain-of-thought)
    // Key by size + last-part identity to avoid Compose's O(N) list-comparison on every
    // recomposition. During streaming the list grows one element at a time so size alone is
    // sufficient to detect a meaningful change; the lastOrNull() hash catches in-place edits
    // on the tail part (e.g. streaming text appended to the final Text part).
    val partsKey = parts.size.toString() + (parts.lastOrNull()?.hashCode()?.toString() ?: "")
    val groupedParts = remember(partsKey) { parts.groupMessageParts() }
    groupedParts.fastForEach { block ->
        when (block) {
            is MessagePartBlock.ThinkingBlock -> {
                var showSummaryPanel by remember { mutableStateOf(false) } // rhSummaryPanel
                if (showSummaryPanel) { // rhSummaryPanel
                    ModalBottomSheet(
                        onDismissRequest = { showSummaryPanel = false },
                    ) {
                        Column( // rhBatch88
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(16.dp)
                                .verticalScroll(rememberScrollState()),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            Text(
                                text = "工具调用（共 " + block.steps.size + " 步）",
                                style = MaterialTheme.typography.titleMedium,
                            )
                            block.steps.filterIsInstance<ThinkingStep.ToolStep>().forEach { step ->
                                val tool = step.tool
                                Text(
                                    text = tool.toolName,
                                    style = MaterialTheme.typography.titleSmall,
                                    color = MaterialTheme.colorScheme.secondary,
                                )
                                HighlightCodeBlock(
                                    tool.input,
                                    "json",
                                )
                                if (tool.isExecuted) {
                                    val outputText = tool.output
                                        .filterIsInstance<UIMessagePart.Text>()
                                        .joinToString("\n") { it.text }
                                    if (outputText.isNotBlank()) {
                                        HighlightCodeBlock(
                                            outputText,
                                            "json",
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
                if (block.steps.isNotEmpty()) {
                    val isReasoningOnlyBlock = block.steps.fastAll { it is ThinkingStep.ReasoningStep }
                    // Force-expand whenever any tool step is awaiting approval. Without
                    // this, on 3+ pending tool calls only the last 2 rows are visible
                    // and the first sits hidden behind the "show more" arrow — easy to
                    // miss when the agent is asking for the user's go-ahead.
                    val hasPendingApproval = block.steps.any {
                        it is ThinkingStep.ToolStep &&
                            it.tool.approvalState is ToolApprovalState.Pending
                    }
                    // rhToolProgressBadge: 步骤完成度（N/M）—— 0/4 这样的进度一眼可见
                    val finishedSteps = block.steps.count { step ->
                        when (step) {
                            is ThinkingStep.ToolStep -> step.tool.isExecuted
                            is ThinkingStep.ServerToolStep -> step.tool.isFinished
                            is ThinkingStep.ReasoningStep -> true
                        }
                    }
                    val totalSteps = block.steps.size
                    var toolStepIndex = 0
                    // rhToolProgressBadge: 折叠态进度徽标 —— 只有正在生成或步骤>=3 时显示
                    if (loading || totalSteps >= 3) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(bottom = 2.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(6.dp),
                        ) {
                            Icon(
                                imageVector = HugeIcons.Sparkles,
                                contentDescription = null,
                                modifier = Modifier.size(14.dp),
                                tint = MaterialTheme.colorScheme.primary,
                            )
                            Text(
                                text = "$finishedSteps/$totalSteps",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.primary,
                                modifier = Modifier.shimmer(
                                    isLoading = loading && finishedSteps < totalSteps
                                ),
                            )
                        }
                    }
                    ChainOfThought(
                        modifier = Modifier.animateContentSize(),
                        steps = block.steps,
                        collapsedLabel = ToolSummaryMapper.summarize(block.steps), // rhSemanticSummary
                        collapsedAdaptiveWidth = isReasoningOnlyBlock,
                        forceExpanded = hasPendingApproval,
                        onShowSummary = { showSummaryPanel = true }, // rhSummaryPanel
                        cardColors = CardDefaults.cardColors(
                            containerColor = MaterialTheme.colorScheme.surfaceContainerHigh.copy(alpha = settings.displaySetting.bubbleOpacity),
                        ),
                    ) { step ->
                        when (step) {
                            is ThinkingStep.ReasoningStep -> {
                                key(step.reasoning.createdAt) {
                                    ChatMessageReasoningStep(
                                        reasoning = step.reasoning,
                                        model = model,
                                        assistant = assistant,
                                        collapsedAdaptiveWidth = isReasoningOnlyBlock,
                                    )
                                }
                            }

                            is ThinkingStep.ToolStep -> {
                                toolStepIndex++
                                key(step.tool.toolCallId.ifBlank { step.hashCode().toString() }) {
                                    ChatMessageToolStep(
                                        tool = step.tool,
                                        loading = loading && !step.tool.isExecuted,
                                        generationActive = generationActive,
                                        onToolApproval = onToolApproval,
                                        onToolAnswer = onToolAnswer,
                                        onRerunTool = onRerunTool,
                                        stepNumber = toolStepIndex,
                                    )
                                }
                            }

                            is ThinkingStep.ServerToolStep -> {
                                key(step.tool.toolCallId.ifBlank { step.hashCode().toString() }) {
                                    ChatMessageServerToolStep(tool = step.tool)
                                }
                            }
                        }
                    }
                }
            }

            is MessagePartBlock.ContentBlock -> key(block.index) {
                when (val part = block.part) {
                    is UIMessagePart.Text -> {
                        // A Text part may carry a `rikkahub.webview` metadata block
                        // emitted by a JS skill. When present we render a tap-to-open
                        // card that routes into BrowserActivity instead of the standard
                        // markdown ("browser as the viewer"). The card returns true on
                        // render so we skip the markdown branch. Only consider for
                        // non-user messages: user messages don't carry this metadata.
                        val renderedAsWebviewCard =
                            role != MessageRole.USER && SkillWebviewCardOrNull(part)
                        val textContent = @Composable {
                            if (role == MessageRole.USER) {
                                Surface(
                                    modifier = Modifier.animateContentSize(),
                                    shape = RoundedCornerShape(16.dp),
                                    color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = settings.displaySetting.bubbleOpacity),
                                    onClick = { onUserMessageClick?.invoke() },
                                ) {
                                    Column(modifier = Modifier.padding(8.dp)) {
                                        CollapsibleUserText(
                                    text = part.text,
                                    enabled = settings.displaySetting.collapseLongUserMessage,
                                    maxLines = settings.displaySetting.collapseUserMessageLines,
                                ) {
                                    MarkdownBlock(
                                            content = part.text.replaceRegexes(
                                                assistant = assistant,
                                                scope = AssistantAffectScope.USER,
                                                visual = true,
                                            ),
                                            onClickCitation = handleClickCitation
                                        )
                                }
                                    }
                                }
                            } else {
                                if (settings.displaySetting.showAssistantBubble) {
                                    Surface(
                                        modifier = Modifier.animateContentSize(),
                                        shape = RoundedCornerShape(16.dp),
                                        color = MaterialTheme.colorScheme.surfaceContainerHigh.copy(alpha = settings.displaySetting.bubbleOpacity),
                                    ) {
                                        Column(modifier = Modifier.padding(8.dp)) {
                                            MarkdownBlock(
                                                content = part.text.replaceRegexes(
                                                    assistant = assistant,
                                                    scope = AssistantAffectScope.ASSISTANT,
                                                    visual = true,
                                                ),
                                                onClickCitation = handleClickCitation,
                                            )
                                        }
                                    }
                                } else {
                                    MarkdownBlock(
                                        content = part.text.replaceRegexes(
                                            assistant = assistant,
                                            scope = AssistantAffectScope.ASSISTANT,
                                            visual = true,
                                        ),
                                        onClickCitation = handleClickCitation,
                                        modifier = Modifier
                                            .animateContentSize()
                                    )
                                }
                            }
                        }

                        // 流式生成期间不启用 SelectionContainer：Markdown 在不断重渲染，
                        // 内部可选择的 Text 会频繁注册/注销，与 Compose 选择工具栏在绘制阶段
                        // 对 selectable 列表的排序产生并发修改，导致 ConcurrentModificationException。
                        // 生成结束后内容稳定，再启用文本选择。
                        if (!renderedAsWebviewCard) {
                            if (loading) {
                                textContent()
                            } else {
                                SelectionContainer {
                                    textContent()
                                }
                            }
                        }
                    }

                    is UIMessagePart.Video -> {
                        // batch25 marker: Video/Audio/Document 封面提取需额外库（Coil video frame），
                        // 当前统一用 Icon 占位。Image 的 shimmer 占位已实现（isImageLoading 分支）。
                        Surface(
                            tonalElevation = 2.dp,
                            onClick = {
                                val intent = Intent(Intent.ACTION_VIEW)
                                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                                intent.data = FileProvider.getUriForFile(
                                    context,
                                    "${context.packageName}.fileprovider",
                                    part.url.toUri().toFile()
                                )
                                val chooserIndent = Intent.createChooser(intent, null)
                                context.startActivity(chooserIndent)
                            },
                            modifier = Modifier,
                            shape = RoundedCornerShape(8.dp),
                        ) {
                            Box(modifier = Modifier.size(72.dp), contentAlignment = Alignment.Center) {
                                Icon(HugeIcons.Video01, null)
                            }
                        }
                    }

                    is UIMessagePart.Audio -> {
                        Surface(
                            tonalElevation = 2.dp,
                            onClick = {
                                val intent = Intent(Intent.ACTION_VIEW)
                                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                                intent.data = FileProvider.getUriForFile(
                                    context,
                                    "${context.packageName}.fileprovider",
                                    part.url.toUri().toFile()
                                )
                                val chooserIndent = Intent.createChooser(intent, null)
                                context.startActivity(chooserIndent)
                            },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(16.dp),
                            color = MaterialTheme.colorScheme.surfaceContainerHigh,
                        ) {
                            Row(
                                modifier = Modifier.padding(12.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(12.dp),
                            ) {
                                Surface(
                                    modifier = Modifier.size(44.dp),
                                    shape = RoundedCornerShape(12.dp),
                                    color = MaterialTheme.colorScheme.surfaceContainerHigh,
                                ) {
                                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                                        Icon(imageVector = HugeIcons.MusicNote03, contentDescription = null, modifier = Modifier.size(24.dp))
                                    }
                                }
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = part.url.toUri().toFile().name,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis,
                                        style = MaterialTheme.typography.titleSmall,
                                    )
                                    Text(
                                        text = "audio · " + runCatching { part.url.toUri().toFile().length().fileSizeToString() }.getOrDefault("未知大小"),
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis,
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                                Surface(
                                    modifier = Modifier.size(36.dp),
                                    shape = CircleShape,
                                    color = MaterialTheme.colorScheme.surfaceContainerHigh,
                                ) {
                                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                                        Icon(
                                            imageVector = HugeIcons.Download01,
                                            contentDescription = null,
                                            modifier = Modifier.size(20.dp),
                                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                }
                            }
                        }
                    }

                    is UIMessagePart.Image -> {
                        val isImageLoading =
                            part.url.isBlank() || part.url.matches(Regex("^data:image/[^;]*;base64,\\s*$"))
                        if (isImageLoading) {
                            Box(
                                modifier = Modifier
                                    .size(72.dp)
                                    .clip(MaterialTheme.shapes.medium)
                                    .background(MaterialTheme.colorScheme.surfaceVariant)
                                    .shimmer(isLoading = true)
                            )
                        } else {
                            ZoomableAsyncImage(
                                model = part.url,
                                contentDescription = null,
                                modifier = Modifier
                                    .clip(MaterialTheme.shapes.medium)
                                    .height(72.dp)
                            )
                        }
                    }

                    is UIMessagePart.Document -> {
                        Surface(
                            tonalElevation = 2.dp,
                            onClick = {
                                val intent = Intent(Intent.ACTION_VIEW)
                                intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                                intent.data = FileProvider.getUriForFile(
                                    context,
                                    "${context.packageName}.fileprovider",
                                    part.url.toUri().toFile()
                                )
                                val chooserIndent = Intent.createChooser(intent, null)
                                context.startActivity(chooserIndent)
                            },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(16.dp),
                            color = MaterialTheme.colorScheme.surfaceContainerHigh,
                        ) {
                            Row(
                                modifier = Modifier.padding(12.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(12.dp),
                            ) {
                                Surface(
                                    modifier = Modifier.size(44.dp),
                                    shape = RoundedCornerShape(12.dp),
                                    color = MaterialTheme.colorScheme.surfaceContainerHigh,
                                ) {
                                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                                        Icon(imageVector = HugeIcons.File02, contentDescription = null, modifier = Modifier.size(24.dp))
                                    }
                                }
                                Column(modifier = Modifier.weight(1f)) {
                                    Text(
                                        text = part.fileName,
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis,
                                        style = MaterialTheme.typography.titleSmall,
                                    )
                                    Text(
                                        text = part.fileName.substringAfterLast('.', "file").uppercase() + " · " + runCatching { part.url.toUri().toFile().length().fileSizeToString() }.getOrDefault("未知大小"),
                                        maxLines = 1,
                                        overflow = TextOverflow.Ellipsis,
                                        style = MaterialTheme.typography.labelSmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                                Surface(
                                    modifier = Modifier.size(36.dp),
                                    shape = CircleShape,
                                    color = MaterialTheme.colorScheme.surfaceContainerHigh,
                                ) {
                                    Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                                        Icon(
                                            imageVector = HugeIcons.Download01,
                                            contentDescription = null,
                                            modifier = Modifier.size(20.dp),
                                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                }
                            }
                        }
                    }

                    else -> {
                        // Skip unknown part types (e.g., deprecated ToolCall, ToolResult, Search)
                    }
                }
            }
        }
    }

    // Annotations (always rendered at the end)
    if (annotations.isNotEmpty()) {
        Column(
            modifier = Modifier.animateContentSize(),
        ) {
            var expand by remember { mutableStateOf(false) }
            if (expand) {
                ProvideTextStyle(
                    MaterialTheme.typography.labelMedium.copy(
                        color = MaterialTheme.extendColors.gray8.copy(alpha = 0.65f)
                    )
                ) {
                    Column(
                        modifier = Modifier
                            .drawWithContent {
                                drawContent()
                                drawRoundRect(
                                    color = contentColor.copy(alpha = 0.2f),
                                    size = Size(width = 10f, height = size.height),
                                )
                            }
                            .padding(start = 16.dp)
                            .padding(4.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        annotations.fastForEachIndexed { index, annotation ->
                            when (annotation) {
                                is UIMessageAnnotation.UrlCitation -> {
                                    Row(
                                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                                    ) {
                                        Favicon(annotation.url, modifier = Modifier.size(20.dp))
                                        Text(
                                            text = buildAnnotatedString {
                                                append("${index + 1}. ")
                                                withLink(LinkAnnotation.Url(annotation.url)) {
                                                    append(annotation.title.urlDecode())
                                                }
                                            }
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
            TextButton(
                onClick = {
                    expand = !expand
                }
            ) {
                Text(stringResource(R.string.citations_count, annotations.size))
            }
        }
    }
}

/** rhQuoteBlock: 引用块——消息上方的引用预览小卡（UI-1 批 b，纯组件）。
 * 数据由调用方解析后传入；点击回调由调用方处理（跳转/高亮）。 */
@Composable
fun ChatMessageQuoteBlock(
    senderName: String,
    previewText: String,
    onClick: () -> Unit,
) {
    Surface(
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.surfaceContainerHigh,
        modifier = Modifier
            .fillMaxWidth(0.92f)
            .clickable(onClick = onClick),
    ) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
            modifier = Modifier.padding(start = 10.dp, end = 10.dp, top = 6.dp, bottom = 6.dp),
        ) {
            Box(
                modifier = Modifier
                    .size(width = 3.dp, height = 18.dp)
                    .background(MaterialTheme.colorScheme.primary),
            )
            Column {
                Text(
                    text = senderName,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                )
                Text(
                    text = previewText,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}
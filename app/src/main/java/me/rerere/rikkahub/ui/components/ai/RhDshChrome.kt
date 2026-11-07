package me.rerere.rikkahub.ui.components.ai

// rhDshChrome318 - visual replication of the dsh-go chat chrome.
// Top bar (menu key / title pill / model chip / new chat), composer keys
// (+ key, context ring, send-or-mic key) and the usage bottom sheet.
// Every control only forwards to callbacks the app already had.

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import me.rerere.ai.core.MessageRole
import me.rerere.ai.provider.Model
import me.rerere.ai.provider.ModelType
import me.rerere.ai.provider.ProviderSetting
import me.rerere.ai.ui.UIMessage
import me.rerere.ai.ui.UIMessagePart
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.Add01
import me.rerere.hugeicons.stroke.ArrowUp02
import me.rerere.hugeicons.stroke.Camera01
import me.rerere.hugeicons.stroke.Cancel01
import me.rerere.hugeicons.stroke.Files02
import me.rerere.hugeicons.stroke.Image02
import me.rerere.hugeicons.stroke.Menu03
import me.rerere.hugeicons.stroke.MusicNote03
import me.rerere.hugeicons.stroke.Video01
import me.rerere.rikkahub.R
import me.rerere.rikkahub.data.datastore.Settings
import me.rerere.rikkahub.data.datastore.findModelById
import me.rerere.rikkahub.data.model.Conversation
import me.rerere.rikkahub.data.model.ModelContextLengthResolver
import org.koin.compose.koinInject
import kotlin.math.roundToInt
import kotlin.uuid.Uuid

// ---------------------------------------------------------------- glass

@Composable
private fun rhDshDark(): Boolean = MaterialTheme.colorScheme.surface.luminance() < 0.5f

@Composable
private fun rhDshGlass(shape: Shape, fillAlpha: Float = 0.72f, shadow: Dp = 6.dp): Modifier {
    val dark = rhDshDark()
    val fill = if (dark) Color.White.copy(alpha = 0.09f) else Color.White.copy(alpha = fillAlpha)
    val line = if (dark) Color.White.copy(alpha = 0.10f) else Color.Black.copy(alpha = 0.07f)
    return Modifier
        .shadow(shadow, shape, clip = false)
        .clip(shape)
        .background(fill, shape)
        .border(1.dp, line, shape)
}

@Composable
fun rhDshKeyTint(): Color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.06f)

// ---------------------------------------------------------------- glyphs

@Composable
private fun RhDshSparkle(side: Dp, color: Color) {
    Canvas(Modifier.size(side)) {
        val cx = size.width / 2f
        val cy = size.height / 2f
        val r = size.minDimension / 2f
        val p = Path()
        p.moveTo(cx, cy - r)
        p.cubicTo(cx + r * 0.18f, cy - r * 0.30f, cx + r * 0.30f, cy - r * 0.18f, cx + r, cy)
        p.cubicTo(cx + r * 0.30f, cy + r * 0.18f, cx + r * 0.18f, cy + r * 0.30f, cx, cy + r)
        p.cubicTo(cx - r * 0.18f, cy + r * 0.30f, cx - r * 0.30f, cy + r * 0.18f, cx - r, cy)
        p.cubicTo(cx - r * 0.30f, cy - r * 0.18f, cx - r * 0.18f, cy - r * 0.30f, cx, cy - r)
        p.close()
        drawPath(p, color)
    }
}

@Composable
private fun RhDshChevron(side: Dp, color: Color) {
    Canvas(Modifier.size(side)) {
        val w = size.width
        val h = size.height
        val p = Path()
        p.moveTo(w * 0.26f, h * 0.40f)
        p.lineTo(w * 0.50f, h * 0.60f)
        p.lineTo(w * 0.74f, h * 0.40f)
        drawPath(p, color, style = Stroke(width = 1.6.dp.toPx(), cap = StrokeCap.Round))
    }
}

@Composable
private fun RhDshNewChatGlyph(color: Color) {
    Canvas(Modifier.size(22.dp)) {
        val s = size.width
        val stroke = 1.7.dp.toPx()
        drawRoundRect(
            color = color,
            topLeft = Offset(s * 0.12f, s * 0.12f),
            size = Size(s * 0.60f, s * 0.60f),
            cornerRadius = CornerRadius(s * 0.16f, s * 0.16f),
            style = Stroke(width = stroke),
        )
        val p = Path()
        p.moveTo(s * 0.52f, s * 0.82f)
        p.lineTo(s * 0.88f, s * 0.46f)
        drawPath(p, color, style = Stroke(width = stroke, cap = StrokeCap.Round))
    }
}

// ---------------------------------------------------------------- top bar

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun RhDshCircleKey(
    contentDescription: String,
    onClick: () -> Unit,
    onLongClick: (() -> Unit)? = null,
    content: @Composable () -> Unit,
) {
    Box(
        modifier = Modifier
            .size(44.dp)
            .then(rhDshGlass(RoundedCornerShape(22.dp), shadow = 4.dp))
            .combinedClickable(onClick = onClick, onLongClick = onLongClick),
        contentAlignment = Alignment.Center,
    ) {
        content()
    }
}

fun rhDshShortModelName(raw: String): String {
    var stripped = raw
    if (raw.lowercase().startsWith("deepseek")) {
        stripped = raw.substring(8)
        while (stripped.startsWith("-") || stripped.startsWith("_") || stripped.startsWith(" ")) {
            stripped = stripped.substring(1)
        }
    }
    val words = stripped.split('-', '_', ' ', '.').filter { it.isNotEmpty() }
    if (words.isEmpty()) return raw
    val mapped = words.map { w ->
        if (w.length == 1) w.uppercase() else w[0].uppercase() + w.substring(1)
    }
    return mapped.joinToString(" ")
}

@Composable
fun RhDshTopBar(
    title: String,
    statusLabel: String,
    loading: Boolean,
    settings: Settings,
    modelId: Uuid?,
    previewMode: Boolean,
    onMenuClick: () -> Unit,
    onNewChat: () -> Unit,
    onUpdateTitle: (String) -> Unit,
    onImportSharedConversation: () -> Unit,
    onSelectModel: (Model) -> Unit,
    onTogglePreview: () -> Unit,
) {
    var menuOpen by remember { mutableStateOf(false) }
    var titleEdit by remember { mutableStateOf<String?>(null) }
    var showModels by remember { mutableStateOf(false) }
    val scheme = MaterialTheme.colorScheme
    val model = settings.findModelById(modelId)
    val chipLabel = if (model == null) "选择模型" else rhDshShortModelName(model.displayName.ifBlank { model.modelId })
    val htmlMode = if (me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.isReady) {
        val skin by me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.store.stateFlow.collectAsStateWithLifecycle()
        skin.htmlModeEnabled
    } else {
        false
    }

    Box(Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .statusBarsPadding()
                .padding(horizontal = 12.dp, vertical = 6.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            RhDshCircleKey(
                contentDescription = "会话列表",
                onClick = onMenuClick,
                onLongClick = { menuOpen = true },
            ) {
                Icon(HugeIcons.Menu03, contentDescription = null, modifier = Modifier.size(22.dp), tint = scheme.onSurface)
            }

            Row(
                modifier = Modifier
                    .weight(1f)
                    .height(44.dp)
                    .then(rhDshGlass(RoundedCornerShape(22.dp), shadow = 5.dp))
                    .clickable { menuOpen = true }
                    .padding(horizontal = 16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column {
                    Text(
                        text = title,
                        fontSize = 15.sp,
                        lineHeight = 19.5.sp,
                        fontWeight = FontWeight.Medium,
                        color = scheme.onSurface,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(
                            Modifier
                                .size(6.dp)
                                .clip(CircleShape)
                                .background(if (loading) Color(0xFFFF9F0A) else Color(0xFF34C759))
                        )
                        Spacer(Modifier.size(5.dp))
                        Text(
                            text = statusLabel,
                            fontSize = 11.sp,
                            lineHeight = 13.sp,
                            color = scheme.onSurfaceVariant,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }

            Box(
                modifier = Modifier
                    .height(44.dp)
                    .then(rhDshGlass(RoundedCornerShape(22.dp), shadow = 5.dp)), // rh341
                contentAlignment = Alignment.Center,
            ) {
                Row(
                    modifier = Modifier.padding(start = 12.dp, end = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    RhDshSparkle(side = 14.dp, color = scheme.primary)
                    Spacer(Modifier.size(5.dp))
                    Text(
                        text = chipLabel,
                        fontSize = 13.sp,
                        color = scheme.onSurface,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.widthIn(max = 116.dp),
                    )
                    Spacer(Modifier.size(4.dp))
                    RhDshChevron(side = 16.dp, color = scheme.onSurfaceVariant)
                }
                // 原生选择器：透明承接点击，面板/搜索/分组/收藏全部沿用原版
                ModelSelector(
                    modelId = modelId,
                    providers = settings.providers,
                    onSelect = onSelectModel,
                    type = ModelType.CHAT,
                    onlyIcon = true,
                    modifier = Modifier
                        .fillMaxSize()
                        .alpha(0.01f),
                )
            }

            RhDshCircleKey(contentDescription = "新建对话", onClick = onNewChat) {
                RhDshNewChatGlyph(color = scheme.onSurface)
            }
        }

        DropdownMenu(expanded = menuOpen, onDismissRequest = { menuOpen = false }) {
            DropdownMenuItem(
                text = { Text("编辑标题") },
                onClick = {
                    menuOpen = false
                    titleEdit = title
                },
            )
            DropdownMenuItem(
                text = { Text(if (previewMode) "退出预览模式" else "预览模式") },
                onClick = {
                    menuOpen = false
                    onTogglePreview()
                },
            )
            DropdownMenuItem(
                text = { Text("导入分享会话") },
                onClick = {
                    menuOpen = false
                    onImportSharedConversation()
                },
            )
            if (htmlMode) {
                DropdownMenuItem(
                    text = { Text("退出 HTML 皮肤") },
                    onClick = {
                        menuOpen = false
                        me.rerere.rikkahub.data.ai.tools.local.ChatHtmlSkinGlobal.store.setMode(false)
                    },
                )
            }
        }
    }

    val editing = titleEdit
    if (editing != null) {
        AlertDialog(
            onDismissRequest = { titleEdit = null },
            title = { Text("编辑标题") },
            text = {
                OutlinedTextField(
                    value = editing,
                    onValueChange = { titleEdit = it },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            },
            confirmButton = {
                TextButton(onClick = {
                    onUpdateTitle(editing)
                    titleEdit = null
                }) { Text("保存") }
            },
            dismissButton = {
                TextButton(onClick = { titleEdit = null }) { Text("取消") }
            },
        )
    }

    if (showModels) {
        RhDshModelSheet(
            settings = settings,
            current = modelId,
            onDismiss = { showModels = false },
            onSelect = {
                showModels = false
                onSelectModel(it)
            },
        )
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun RhDshModelSheet(
    settings: Settings,
    current: Uuid?,
    onDismiss: () -> Unit,
    onSelect: (Model) -> Unit,
) {
    val rows = remember(settings.providers) {
        settings.providers
            .filter { it.enabled }
            .flatMap { provider -> provider.models.filter { it.type == ModelType.CHAT }.map { provider.name to it } }
    }
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(Modifier.fillMaxWidth().padding(bottom = 24.dp)) {
            Text(
                text = "选择模型",
                fontSize = 20.sp,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(horizontal = 20.dp, vertical = 8.dp),
            )
            LazyColumn(Modifier.fillMaxWidth()) {
                items(rows) { row ->
                    val providerName = row.first
                    val m = row.second
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onSelect(m) }
                            .padding(horizontal = 20.dp, vertical = 12.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text(
                                text = m.displayName,
                                fontSize = 15.sp,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                            Text(
                                text = providerName,
                                fontSize = 12.sp,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                maxLines = 1,
                            )
                        }
                        if (m.id == current) {
                            Text("当前", fontSize = 12.sp, color = MaterialTheme.colorScheme.primary)
                        }
                    }
                }
            }
        }
    }
}

// ---------------------------------------------------------------- usage model

data class RhDshUsage(
    val contextUsed: Int = 0,
    val contextLimit: Int? = null,
    val systemTokens: Int = 0,
    val toolTokens: Int = 0,
    val messageTokens: Int = 0,
    val inputTokens: Int = 0,
    val outputTokens: Int = 0,
    val cacheHitRate: Float? = null,
    val turns: Int = 0,
    val outputTps: Float? = null, // rhTps345
) {
    val fraction: Float
        get() {
            val limit = contextLimit ?: return 0f
            if (limit <= 0) return 0f
            return (contextUsed.toFloat() / limit.toFloat()).coerceIn(0f, 1f)
        }
}

@Composable
fun rememberRhDshUsage(conversation: Conversation, modelIdentifier: String?): RhDshUsage {
    val resolver = koinInject<ModelContextLengthResolver>()
    val limit by produceState<Int?>(initialValue = null, modelIdentifier) {
        value = runCatching { resolver.resolve(modelIdentifier, null) }.getOrNull()
    }
    val messages = conversation.currentMessages
    return remember(messages, limit) { rhDshComputeUsage(messages, limit) }
}

private fun rhDshComputeUsage(messages: List<UIMessage>, limit: Int?): RhDshUsage {
    var input = 0
    var output = 0
    var cached = 0
    var turns = 0
    var lastPrompt = 0
    var lastTps: Float? = null // rhTps345
    var textChars = 0
    var toolChars = 0
    messages.forEach { message ->
        if (message.role == MessageRole.USER) turns += 1
        val usage = message.usage
        if (usage != null) {
            // rhUsageTotal342: 优先逐步骤累计；旧消息累计为 0 时回退到最后一步
            input += if (message.totalPromptTokens > 0) message.totalPromptTokens else usage.promptTokens
            output += if (message.totalCompletionTokens > 0) message.totalCompletionTokens else usage.completionTokens
            cached += usage.cachedTokens
            if (usage.promptTokens > 0) lastPrompt = usage.promptTokens
        }
        if (message.role == MessageRole.ASSISTANT) { // rhTps345
            val millis = message.generationMillis
            if (millis != null && millis > 0L && usage != null && usage.completionTokens > 0) {
                lastTps = usage.completionTokens * 1000f / millis
            }
        }
        message.parts.forEach { part ->
            if (part is UIMessagePart.Text) {
                textChars += part.text.length
            } else if (part is UIMessagePart.Tool) {
                toolChars += part.input.length
            }
        }
    }
    val messageTokens = textChars / 4
    val toolTokens = toolChars / 4
    val used = if (lastPrompt > 0) lastPrompt else messageTokens + toolTokens
    val systemTokens = (used - messageTokens - toolTokens).coerceAtLeast(0)
    val rate = if (input > 0) cached.toFloat() / input.toFloat() else null
    return RhDshUsage(
        contextUsed = used,
        contextLimit = limit,
        systemTokens = systemTokens,
        toolTokens = toolTokens,
        messageTokens = messageTokens,
        inputTokens = input,
        outputTokens = output,
        cacheHitRate = rate,
        turns = turns,
        outputTps = lastTps, // rhTps345
    )
}

fun rhDshFormatTokens(n: Int): String {
    if (n < 10000) {
        val digits = n.toString()
        val sb = StringBuilder()
        for (i in digits.indices) {
            if (i > 0 && (digits.length - i) % 3 == 0) sb.append(',')
            sb.append(digits[i])
        }
        return sb.toString()
    }
    val w = n.toDouble() / 10000.0
    val v = (w * 10).roundToInt() / 10.0
    val text = if (v == v.toInt().toDouble()) v.toInt().toString() else v.toString()
    return text + " 万"
}

fun rhDshPercent(fraction: Float): String {
    if (fraction > 0f && fraction < 0.01f) return "<1%"
    return (fraction * 100f).roundToInt().toString() + "%"
}

private fun rhTps345Label(tps: Float): String { // rhTps345
    val v = (tps * 10f).roundToInt() / 10.0
    val text = if (v == v.toInt().toDouble()) v.toInt().toString() else v.toString()
    return " · 输出 " + text + " tok/s"
}

@Composable
private fun rhDshTone(fraction: Float): Color {
    val scheme = MaterialTheme.colorScheme
    return when {
        fraction > 0.85f -> scheme.error
        fraction >= 0.6f -> Color(0xFFE8A317)
        else -> scheme.primary
    }
}

// ---------------------------------------------------------------- composer keys

@Composable
fun RhDshContextRing(usage: RhDshUsage, onClick: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    val fraction = usage.fraction
    val tone = rhDshTone(fraction)
    Row(
        modifier = Modifier
            .height(40.dp)
            .clip(RoundedCornerShape(20.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Canvas(Modifier.size(15.dp)) {
            val stroke = 2.2.dp.toPx()
            val inset = stroke / 2f
            val arcSize = Size(size.width - stroke, size.height - stroke)
            drawArc(
                color = scheme.onSurface.copy(alpha = 0.12f),
                startAngle = 0f,
                sweepAngle = 360f,
                useCenter = false,
                topLeft = Offset(inset, inset),
                size = arcSize,
                style = Stroke(width = stroke, cap = StrokeCap.Round),
            )
            drawArc(
                color = tone,
                startAngle = -90f,
                sweepAngle = fraction.coerceAtLeast(0.02f) * 360f,
                useCenter = false,
                topLeft = Offset(inset, inset),
                size = arcSize,
                style = Stroke(width = stroke, cap = StrokeCap.Round),
            )
        }
        Spacer(Modifier.size(5.dp))
        Text(
            text = if (usage.contextLimit == null) "—" else rhDshPercent(fraction),
            fontSize = 11.sp,
            fontWeight = FontWeight.Medium,
            color = if (fraction >= 0.6f) tone else scheme.onSurfaceVariant,
        )
    }
}

@OptIn(ExperimentalFoundationApi::class)
@Composable
fun RhDshSendKey(loading: Boolean, enabled: Boolean, onSend: () -> Unit, onLongSend: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    val bg = when {
        loading -> scheme.errorContainer
        enabled -> scheme.primary
        else -> scheme.onSurface.copy(alpha = 0.12f)
    }
    val fg = when {
        loading -> scheme.onErrorContainer
        enabled -> scheme.onPrimary
        else -> scheme.onSurface.copy(alpha = 0.38f)
    }
    Box(
        modifier = Modifier
            .size(40.dp)
            .clip(CircleShape)
            .background(bg)
            .combinedClickable(
                enabled = enabled || loading,
                onClick = onSend,
                onLongClick = onLongSend,
            ),
        contentAlignment = Alignment.Center,
    ) {
        if (loading) {
            Icon(HugeIcons.Cancel01, contentDescription = "停止", modifier = Modifier.size(20.dp), tint = fg)
        } else {
            Icon(HugeIcons.ArrowUp02, contentDescription = "发送", modifier = Modifier.size(22.dp), tint = fg)
        }
    }
}

@Composable
fun RhDshPlusKey(
    allowAudioVideo: Boolean,
    onTakePicture: () -> Unit,
    onPickImage: () -> Unit,
    onPickVideo: () -> Unit,
    onPickAudio: () -> Unit,
    onPickFile: () -> Unit,
    onMoreClick: () -> Unit = {},
    capabilities: (@Composable () -> Unit)? = null,
) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        Box(
            modifier = Modifier
                .size(40.dp)
                .clip(CircleShape)
                .background(rhDshKeyTint())
                .clickable { expanded = true },
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = HugeIcons.Add01,
                contentDescription = "更多",
                modifier = Modifier.size(22.dp),
                tint = MaterialTheme.colorScheme.onSurface,
            )
        }
        DropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
            modifier = Modifier.widthIn(min = 240.dp, max = 340.dp),
        ) {
            DropdownMenuItem(
                text = { Text(stringResource(R.string.take_picture)) },
                leadingIcon = { Icon(HugeIcons.Camera01, contentDescription = null) },
                onClick = {
                    expanded = false
                    onTakePicture()
                },
            )
            DropdownMenuItem(
                text = { Text(stringResource(R.string.photo)) },
                leadingIcon = { Icon(HugeIcons.Image02, contentDescription = null) },
                onClick = {
                    expanded = false
                    onPickImage()
                },
            )
            if (allowAudioVideo) {
                DropdownMenuItem(
                    text = { Text(stringResource(R.string.video)) },
                    leadingIcon = { Icon(HugeIcons.Video01, contentDescription = null) },
                    onClick = {
                        expanded = false
                        onPickVideo()
                    },
                )
                DropdownMenuItem(
                    text = { Text(stringResource(R.string.audio)) },
                    leadingIcon = { Icon(HugeIcons.MusicNote03, contentDescription = null) },
                    onClick = {
                        expanded = false
                        onPickAudio()
                    },
                )
            }
            DropdownMenuItem(
                text = { Text(stringResource(R.string.upload_file)) },
                leadingIcon = { Icon(HugeIcons.Files02, contentDescription = null) },
                onClick = {
                    expanded = false
                    onPickFile()
                },
            )
            DropdownMenuItem(
                text = { Text("文件与工具") },
                leadingIcon = { Icon(HugeIcons.Files02, contentDescription = null) },
                onClick = {
                    expanded = false
                    onMoreClick()
                },
            )
            val caps = capabilities // rh343: 能力入口统一到「文件与工具」面板
            if (caps != null) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 8.dp, vertical = 4.dp),
                    horizontalArrangement = Arrangement.spacedBy(4.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    caps()
                }
            }
        }
    }
}

// ---------------------------------------------------------------- usage sheet

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RhDshUsageSheet(usage: RhDshUsage, provider: ProviderSetting?, onDismiss: () -> Unit) {
    val scheme = MaterialTheme.colorScheme
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            Modifier
                .fillMaxWidth()
                .padding(start = 20.dp, end = 20.dp, bottom = 28.dp)
        ) {
            Text("用量", fontSize = 22.sp, fontWeight = FontWeight.Bold, color = scheme.onSurface)
            Spacer(Modifier.height(18.dp))

            Text("上下文", fontSize = 13.sp, color = scheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            Surface(
                shape = RoundedCornerShape(20.dp),
                color = scheme.surfaceContainerLow,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Column(Modifier.fillMaxWidth().padding(16.dp)) {
                    Row(verticalAlignment = Alignment.Bottom) {
                        Text(
                            text = rhDshPercent(usage.fraction),
                            fontSize = 26.sp,
                            fontWeight = FontWeight.Medium,
                            color = if (usage.fraction >= 0.6f) rhDshTone(usage.fraction) else scheme.onSurface,
                        )
                        Spacer(Modifier.weight(1f))
                        Text(
                            text = if (usage.contextLimit == null) "—" else rhDshFormatTokens(usage.contextUsed) + " / " + rhDshFormatTokens(usage.contextLimit),
                            fontSize = 12.sp,
                            color = scheme.onSurfaceVariant,
                        )
                    }
                    Spacer(Modifier.height(10.dp))
                    Box(
                        Modifier
                            .fillMaxWidth()
                            .height(6.dp)
                            .clip(RoundedCornerShape(3.dp))
                            .background(scheme.onSurface.copy(alpha = 0.08f))
                    ) {
                        Box(
                            Modifier
                                .fillMaxWidth(usage.fraction.coerceAtLeast(0.02f))
                                .height(6.dp)
                                .clip(RoundedCornerShape(3.dp))
                                .background(rhDshTone(usage.fraction))
                        )
                    }
                    Spacer(Modifier.height(10.dp))
                    Text(
                        text = "系统 " + rhDshFormatTokens(usage.systemTokens) +
                            " · 工具 " + rhDshFormatTokens(usage.toolTokens) +
                            " · 消息 " + rhDshFormatTokens(usage.messageTokens),
                        fontSize = 12.sp,
                        color = scheme.onSurfaceVariant,
                    )
                }
            }

            Spacer(Modifier.height(18.dp))
            Text("本对话", fontSize = 13.sp, color = scheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            Surface(
                shape = RoundedCornerShape(20.dp),
                color = scheme.surfaceContainerLow,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Column(Modifier.fillMaxWidth().padding(16.dp)) {
                    Row(Modifier.fillMaxWidth()) {
                        RhDshStat("输入", rhDshFormatTokens(usage.inputTokens))
                        RhDshStat("输出", rhDshFormatTokens(usage.outputTokens))
                        RhDshStat("缓存命中", usage.cacheHitRate?.let { rhDshPercent(it) } ?: "—")
                    }
                    Spacer(Modifier.height(10.dp))
                    Text(
                        text = "共 " + usage.turns.toString() + " 轮" +
                            (usage.outputTps?.let { rhTps345Label(it) } ?: "") +
                            " · 输入含缓存命中",
                        fontSize = 12.sp,
                        color = scheme.onSurfaceVariant,
                    )
                }
            }

            Spacer(Modifier.height(18.dp))
            Text((provider?.name ?: "供应商") + " 余额", fontSize = 13.sp, color = scheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            Surface(
                shape = RoundedCornerShape(20.dp),
                color = scheme.surfaceContainerLow,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Column(Modifier.fillMaxWidth().padding(16.dp)) {
                    if (provider is ProviderSetting.OpenAI && provider.balanceOption.enabled) {
                        ProviderBalanceText(
                            providerSetting = provider,
                            style = MaterialTheme.typography.bodyMedium,
                            color = scheme.onSurface,
                        )
                    } else {
                        Text("填写 API Key 后可查询余额", fontSize = 14.sp, color = scheme.onSurfaceVariant)
                    }
                }
            }
        }
    }
}

@Composable
private fun RowScope.RhDshStat(label: String, value: String) {
    Column(Modifier.weight(1f)) {
        Text(value, fontSize = 18.sp, fontWeight = FontWeight.Medium, color = MaterialTheme.colorScheme.onSurface)
        Spacer(Modifier.height(2.dp))
        Text(label, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

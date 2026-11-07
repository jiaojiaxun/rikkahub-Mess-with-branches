package me.rerere.rikkahub.ui.pages.assistant.detail

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LargeFlexibleTopAppBar
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.input.nestedscroll.nestedScroll
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.util.fastForEach
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import me.rerere.hugeicons.HugeIcons
import me.rerere.hugeicons.stroke.Add01
import me.rerere.hugeicons.stroke.ArrowDown01
import me.rerere.hugeicons.stroke.ArrowUp01
import me.rerere.hugeicons.stroke.Delete01
import me.rerere.hugeicons.stroke.Message02
import me.rerere.hugeicons.stroke.PencilEdit01
import me.rerere.hugeicons.stroke.QuillWrite01
import me.rerere.rikkahub.R
import me.rerere.rikkahub.data.model.Assistant
import me.rerere.rikkahub.data.model.AssistantMemory
import me.rerere.rikkahub.ui.components.nav.BackButton
import me.rerere.rikkahub.ui.components.ui.CardGroup
import me.rerere.rikkahub.ui.components.ui.RikkaConfirmDialog
import me.rerere.rikkahub.ui.hooks.EditStateContent
import me.rerere.rikkahub.ui.hooks.useEditState
import me.rerere.rikkahub.ui.theme.CustomColors
import org.koin.androidx.compose.koinViewModel
import org.koin.core.parameter.parametersOf

// rhShortMemUI + rhMemPolish240: 精致化记忆管理页 + 工具调用介绍卡(只显示使用中的那一个)
@Composable
fun AssistantMemoryPage(id: String) {
    val vm: AssistantDetailVM = koinViewModel(
        parameters = {
            parametersOf(id)
        }
    )
    val assistant by vm.assistant.collectAsStateWithLifecycle()
    val memories by vm.memories.collectAsStateWithLifecycle()
    val conversationTitles by vm.conversationTitles.collectAsStateWithLifecycle() // rhShortMemUI
    val scrollBehavior = TopAppBarDefaults.exitUntilCollapsedScrollBehavior()

    Scaffold(
        topBar = {
            LargeFlexibleTopAppBar(
                title = {
                    Text(stringResource(R.string.assistant_page_tab_memory))
                },
                navigationIcon = {
                    BackButton()
                },
                scrollBehavior = scrollBehavior,
                colors = CustomColors.topBarColors,
            )
        },
        modifier = Modifier.nestedScroll(scrollBehavior.nestedScrollConnection),
        containerColor = CustomColors.topBarColors.containerColor,
    ) { innerPadding ->
        AssistantMemoryContent(
            innerPadding = innerPadding,
            assistant = assistant,
            memories = memories,
            conversationTitles = conversationTitles,
            onUpdateAssistant = { vm.update(it) },
            onDeleteMemory = { vm.deleteMemory(it) },
            onAddMemory = { vm.addMemory(it) },
            onUpdateMemory = { vm.updateMemory(it) }
        )
    }
}

@Composable
private fun AssistantMemoryContent(
    innerPadding: PaddingValues,
    assistant: Assistant,
    memories: List<AssistantMemory>,
    conversationTitles: Map<String, String>,
    onUpdateAssistant: (Assistant) -> Unit,
    onAddMemory: (AssistantMemory) -> Unit,
    onUpdateMemory: (AssistantMemory) -> Unit,
    onDeleteMemory: (AssistantMemory) -> Unit,
) {
    val memoryDialogState = useEditState<AssistantMemory> {
        if (it.id == 0) {
            onAddMemory(it)
        } else {
            onUpdateMemory(it)
        }
    }
    var pendingDeleteMemory by remember { mutableStateOf<AssistantMemory?>(null) }
    val collapsedGroups = remember { mutableStateMapOf<String, Boolean>() }

    // 记忆编辑/新建对话框(短期模式新建时支持选择归属会话)
    memoryDialogState.EditStateContent { memory, update ->
        AlertDialog(
            onDismissRequest = {
                memoryDialogState.dismiss()
            },
            title = {
                Text(
                    if (memory.id == 0) {
                        if (assistant.enableShortMemory) "添加短期记忆" else "添加长期记忆"
                    } else {
                        stringResource(R.string.assistant_page_manage_memory_title)
                    }
                )
            },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    if (assistant.enableShortMemory && memory.id == 0 && conversationTitles.isNotEmpty()) {
                        Text(
                            text = "归属会话",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .horizontalScroll(rememberScrollState()),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            conversationTitles.entries.take(15).forEach { (cid, title) ->
                                FilterChip(
                                    selected = memory.conversationId == cid,
                                    onClick = { update(memory.copy(conversationId = cid)) },
                                    label = {
                                        Text(
                                            text = title.ifBlank { "未命名会话" },
                                            maxLines = 1,
                                            overflow = TextOverflow.Ellipsis,
                                        )
                                    },
                                )
                            }
                        }
                    } else if (assistant.enableShortMemory && memory.conversationId.isNotBlank()) {
                        Surface(
                            shape = RoundedCornerShape(8.dp),
                            color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.6f),
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(6.dp),
                            ) {
                                Icon(
                                    imageVector = HugeIcons.Message02,
                                    contentDescription = null,
                                    modifier = Modifier.size(14.dp),
                                    tint = MaterialTheme.colorScheme.onSecondaryContainer,
                                )
                                Text(
                                    text = conversationTitles[memory.conversationId]?.ifBlank { null }
                                        ?: stringResource(R.string.assistant_page_memory_unknown_conversation),
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSecondaryContainer,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis,
                                )
                            }
                        }
                    }
                    OutlinedTextField(
                        value = memory.content,
                        onValueChange = {
                            update(memory.copy(content = it))
                        },
                        label = {
                            Text(stringResource(R.string.assistant_page_manage_memory_title))
                        },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 3,
                        maxLines = 8,
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        memoryDialogState.confirm()
                    },
                    enabled = memory.content.isNotBlank() &&
                        (!assistant.enableShortMemory || memory.conversationId.isNotBlank()),
                ) {
                    Text(stringResource(R.string.assistant_page_save))
                }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        memoryDialogState.dismiss()
                    }
                ) {
                    Text(stringResource(R.string.assistant_page_cancel))
                }
            }
        )
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 16.dp)
            .padding(innerPadding)
            .imePadding(),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        CardGroup {
            item(
                headlineContent = { Text(stringResource(R.string.assistant_page_memory)) },
                supportingContent = {
                    Text(
                        text = stringResource(R.string.assistant_page_memory_desc),
                    )
                },
                trailingContent = {
                    Switch(
                        checked = assistant.enableMemory,
                        onCheckedChange = {
                            onUpdateAssistant(
                                assistant.copy(
                                    // rhShortMemUI: 长期/短期互斥
                                    enableMemory = it,
                                    enableShortMemory = if (it) false else assistant.enableShortMemory
                                )
                            )
                        }
                    )
                }
            )
            // rhShortMemUI: 短期记忆(会话私有), 与长期记忆互斥
            item(
                headlineContent = { Text(stringResource(R.string.assistant_page_short_memory)) },
                supportingContent = {
                    Text(
                        text = stringResource(R.string.assistant_page_short_memory_desc),
                    )
                },
                trailingContent = {
                    Switch(
                        checked = assistant.enableShortMemory,
                        onCheckedChange = {
                            onUpdateAssistant(
                                assistant.copy(
                                    enableShortMemory = it,
                                    enableMemory = if (it) false else assistant.enableMemory,
                                    useGlobalMemory = if (it) false else assistant.useGlobalMemory
                                )
                            )
                        }
                    )
                }
            )
            item(
                headlineContent = { Text(stringResource(R.string.assistant_page_global_memory)) },
                supportingContent = {
                    Text(
                        text = stringResource(R.string.assistant_page_global_memory_desc),
                    )
                },
                trailingContent = {
                    Switch(
                        checked = assistant.useGlobalMemory,
                        onCheckedChange = {
                            onUpdateAssistant(
                                assistant.copy(
                                    useGlobalMemory = it
                                )
                            )
                        },
                        enabled = assistant.enableMemory
                    )
                }
            )
            item(
                headlineContent = { Text(stringResource(R.string.assistant_page_recent_chats)) },
                supportingContent = {
                    Text(
                        text = stringResource(R.string.assistant_page_recent_chats_desc),
                    )
                },
                trailingContent = {
                    Switch(
                        checked = assistant.enableRecentChatsReference,
                        onCheckedChange = {
                            onUpdateAssistant(
                                assistant.copy(
                                    enableRecentChatsReference = it
                                )
                            )
                        }
                    )
                }
            )
            item(
                headlineContent = { Text(stringResource(R.string.assistant_page_time_reminder)) },
                supportingContent = {
                    Text(
                        text = stringResource(R.string.assistant_page_time_reminder_desc),
                    )
                },
                trailingContent = {
                    Switch(
                        checked = assistant.enableTimeReminder,
                        onCheckedChange = {
                            onUpdateAssistant(
                                assistant.copy(
                                    enableTimeReminder = it
                                )
                            )
                        }
                    )
                }
            )
        }

        // rhMemPolish240: 工具调用介绍卡片 —— 严格只显示当前使用中的那一种模式(未开启任何记忆时不显示)
        if (assistant.enableShortMemory || assistant.enableMemory) {
            val isShort = assistant.enableShortMemory
            ActiveMemoryToolIntroCard(
                isShortTerm = isShort,
                useGlobal = assistant.useGlobalMemory && !isShort,
            )
        }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 8.dp, vertical = 2.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween,
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Text(
                    text = stringResource(R.string.assistant_page_manage_memory_title),
                    style = MaterialTheme.typography.titleMedium,
                )
                Surface(
                    shape = RoundedCornerShape(999.dp),
                    color = MaterialTheme.colorScheme.primaryContainer,
                ) {
                    Text(
                        text = "${memories.size} 条",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onPrimaryContainer,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                    )
                }
            }

            val defaultConvId = conversationTitles.keys.firstOrNull().orEmpty()
            val canAdd = !assistant.enableShortMemory || defaultConvId.isNotBlank()
            if (canAdd) {
                IconButton(
                    onClick = {
                        memoryDialogState.open(
                            AssistantMemory(
                                id = 0,
                                content = "",
                                conversationId = if (assistant.enableShortMemory) defaultConvId else "",
                            )
                        )
                    },
                ) {
                    Icon(
                        imageVector = HugeIcons.Add01,
                        contentDescription = null
                    )
                }
            }
        }

        if (assistant.enableShortMemory) {
            // rhShortMemUI + rhMemPolish240: 短期记忆按会话分组卡片化展示
            val groupedShortMemories = memories.groupBy { it.conversationId }
            if (groupedShortMemories.isEmpty()) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CustomColors.cardColorsOnSurfaceContainer,
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(20.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(6.dp),
                    ) {
                        Icon(
                            imageVector = HugeIcons.Message02,
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.size(24.dp),
                        )
                        Text(
                            text = stringResource(R.string.assistant_page_short_memory_empty),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            groupedShortMemories.forEach { (convId, convMemories) ->
                val isCollapsed = collapsedGroups[convId] == true
                val convTitle = conversationTitles[convId]?.takeIf { it.isNotBlank() }
                    ?: stringResource(R.string.assistant_page_memory_unknown_conversation)
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    colors = CustomColors.cardColorsOnSurfaceContainer,
                ) {
                    Column(modifier = Modifier.fillMaxWidth()) {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { collapsedGroups[convId] = !isCollapsed }
                                .padding(horizontal = 14.dp, vertical = 10.dp),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            Icon(
                                imageVector = HugeIcons.Message02,
                                contentDescription = null,
                                modifier = Modifier.size(16.dp),
                                tint = MaterialTheme.colorScheme.primary,
                            )
                            Text(
                                text = convTitle,
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.Medium,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                                modifier = Modifier.weight(1f),
                            )
                            Surface(
                                shape = RoundedCornerShape(999.dp),
                                color = MaterialTheme.colorScheme.secondaryContainer,
                            ) {
                                Text(
                                    text = "${convMemories.size} 条",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSecondaryContainer,
                                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                                )
                            }
                            IconButton(
                                onClick = {
                                    memoryDialogState.open(AssistantMemory(0, "", convId))
                                },
                                modifier = Modifier.size(32.dp),
                            ) {
                                Icon(
                                    imageVector = HugeIcons.Add01,
                                    contentDescription = null,
                                    modifier = Modifier.size(18.dp),
                                )
                            }
                            Icon(
                                imageVector = if (isCollapsed) HugeIcons.ArrowDown01 else HugeIcons.ArrowUp01,
                                contentDescription = null,
                                modifier = Modifier.size(16.dp),
                                tint = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        AnimatedVisibility(visible = !isCollapsed) {
                            Column(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .padding(start = 12.dp, end = 12.dp, bottom = 12.dp),
                                verticalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.4f))
                                convMemories.fastForEach { memory ->
                                    key(memory.id) {
                                        MemoryItem(
                                            memory = memory,
                                            onEditMemory = {
                                                memoryDialogState.open(it)
                                            },
                                            onDeleteMemory = {
                                                pendingDeleteMemory = it
                                            }
                                        )
                                    }
                                }
                            }
                        }
                    }
                }
            }
        } else {
            if (memories.isEmpty()) {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CustomColors.cardColorsOnSurfaceContainer,
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(20.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text(
                            text = "暂无长期记忆",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            memories.fastForEach { memory ->
                key(memory.id) {
                    MemoryItem(
                        memory = memory,
                        onEditMemory = {
                            memoryDialogState.open(it)
                        },
                        onDeleteMemory = {
                            pendingDeleteMemory = it
                        }
                    )
                }
            }
        }
    }

    RikkaConfirmDialog(
        show = pendingDeleteMemory != null,
        title = stringResource(R.string.confirm_delete),
        confirmText = stringResource(R.string.confirm),
        dismissText = stringResource(R.string.cancel),
        onConfirm = {
            pendingDeleteMemory?.let(onDeleteMemory)
            pendingDeleteMemory = null
        },
        onDismiss = { pendingDeleteMemory = null },
        text = {
            Text(
                text = pendingDeleteMemory?.content.orEmpty(),
                maxLines = 8,
                overflow = TextOverflow.Ellipsis
            )
        }
    )
}

/**
 * rhMemPolish240: 当前启用记忆模式的工具调用介绍卡 —— 只显示正在使用的那一种模式
 */
@Composable
private fun ActiveMemoryToolIntroCard(
    isShortTerm: Boolean,
    useGlobal: Boolean,
) {
    val containerColor = if (isShortTerm) {
        MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.55f)
    } else {
        MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.55f)
    }
    val accentColor = if (isShortTerm) {
        MaterialTheme.colorScheme.secondary
    } else {
        MaterialTheme.colorScheme.primary
    }
    val modeTitle = when {
        isShortTerm -> "短期记忆工具（memory_tool · 会话私有）"
        useGlobal -> "长期记忆工具（memory_tool · 全局共享）"
        else -> "长期记忆工具（memory_tool · 助手级公共）"
    }
    val modeDesc = if (isShortTerm) {
        "调用介绍：AI 仅在当前对话内通过 memory_tool(create / edit / delete) 记录临时上下文与会话设定；记忆与具体会话绑定，其他对话无法访问。"
    } else {
        "调用介绍：AI 通过 memory_tool(create / edit / delete) 记录跨对话的长期偏好与重要事实；该助手下的所有会话均可共享访问这些记忆。"
    }

    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = containerColor),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Icon(
                    imageVector = HugeIcons.QuillWrite01,
                    contentDescription = null,
                    modifier = Modifier.size(16.dp),
                    tint = accentColor,
                )
                Text(
                    text = modeTitle,
                    style = MaterialTheme.typography.labelLarge,
                    color = accentColor,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                Surface(
                    shape = RoundedCornerShape(999.dp),
                    color = accentColor.copy(alpha = 0.15f),
                ) {
                    Text(
                        text = "使用中",
                        style = MaterialTheme.typography.labelSmall,
                        color = accentColor,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                    )
                }
            }
            Text(
                text = modeDesc,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun MemoryItem(
    memory: AssistantMemory,
    onEditMemory: (AssistantMemory) -> Unit,
    onDeleteMemory: (AssistantMemory) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceContainerLow
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                Text(
                    text = memory.content,
                    maxLines = 5,
                    overflow = TextOverflow.Ellipsis,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            IconButton(
                onClick = { onEditMemory(memory) },
                modifier = Modifier.size(36.dp),
            ) {
                Icon(HugeIcons.PencilEdit01, null, modifier = Modifier.size(18.dp))
            }
            IconButton(
                onClick = { onDeleteMemory(memory) },
                modifier = Modifier.size(36.dp),
            ) {
                Icon(
                    HugeIcons.Delete01,
                    stringResource(R.string.assistant_page_delete),
                    modifier = Modifier.size(18.dp),
                )
            }
        }
    }
}
